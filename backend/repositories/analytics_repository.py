"""
Repositório de Consultas Analíticas e Agregações de Business Intelligence (CQRS).
Executa consultas com GROUP BY, SUM e COUNT nativas no banco de dados para alta performance.
"""

from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, desc

import models


class AnalyticsRepository:
    """
    Camada de persistência analítica (Data Mapper de Leitura Agregada).
    Isola consultas pesadas de BI do repositório transacional de leads.
    """

    @staticmethod
    async def obter_totais_e_financeiro(db: AsyncSession) -> Dict[str, Any]:
        """
        Calcula o total de leads e métricas financeiras consolidadas (Pipeline e Receita).
        """
        # Contagem total de leads
        query_total = select(func.count(models.Lead.id))
        total_leads = (await db.execute(query_total)).scalar() or 0

        # Agregações financeiras por desfecho
        query_financeiro = select(
            models.Lead.desfecho,
            func.count(models.Lead.id).label("quantidade"),
            func.coalesce(func.sum(models.Lead.valor_estimado), 0.0).label("valor_total"),
        ).group_by(models.Lead.desfecho)

        resultado = await db.execute(query_financeiro)
        linhas = resultado.all()

        pipeline_ativo = 0.0
        receita_ganha = 0.0
        valor_perdido = 0.0
        total_ganhos = 0
        total_perdidos = 0
        total_em_andamento = 0

        for desfecho, qtd, valor in linhas:
            if desfecho == models.DesfechoLead.EM_ANDAMENTO:
                pipeline_ativo += float(valor)
                total_em_andamento += int(qtd)
            elif desfecho == models.DesfechoLead.GANHO:
                receita_ganha += float(valor)
                total_ganhos += int(qtd)
            elif desfecho in [models.DesfechoLead.PERDIDO, models.DesfechoLead.CONGELADO_CADENCIA]:
                valor_perdido += float(valor)
                total_perdidos += int(qtd)

        return {
            "total_leads": total_leads,
            "pipeline_ativo_reais": pipeline_ativo,
            "receita_ganha_reais": receita_ganha,
            "valor_perdido_reais": valor_perdido,
            "total_ganhos": total_ganhos,
            "total_perdidos": total_perdidos,
            "total_em_andamento": total_em_andamento,
        }

    @staticmethod
    async def obter_distribuicao_funil(db: AsyncSession) -> Dict[str, Any]:
        """
        Retorna a distribuição de leads por etapa do funil e por temperatura comercial.
        """
        # Distribuição por etapa do funil
        query_etapas = select(
            models.Lead.etapa_funil,
            func.count(models.Lead.id).label("quantidade"),
            func.coalesce(func.sum(models.Lead.valor_estimado), 0.0).label("valor_total"),
        ).group_by(models.Lead.etapa_funil)

        resultado_etapas = await db.execute(query_etapas)
        etapas_data = [
            {
                "etapa": etapa,
                "quantidade": int(qtd),
                "valor_total_reais": float(valor),
            }
            for etapa, qtd, valor in resultado_etapas.all()
        ]

        # Distribuição por temperatura
        query_temp = select(
            models.Lead.temperatura,
            func.count(models.Lead.id).label("quantidade"),
        ).group_by(models.Lead.temperatura)

        resultado_temp = await db.execute(query_temp)
        temp_data = [
            {
                "temperatura": temp,
                "quantidade": int(qtd),
            }
            for temp, qtd in resultado_temp.all()
        ]

        # Contagem de leads quentes prioritários
        query_quentes = select(func.count(models.Lead.id)).where(
            models.Lead.temperatura == models.TemperaturaLead.QUENTE
        )
        leads_quentes_count = (await db.execute(query_quentes)).scalar() or 0

        return {
            "etapas": etapas_data,
            "temperaturas": temp_data,
            "leads_quentes_count": leads_quentes_count,
        }

    @staticmethod
    async def obter_metricas_aquisicao(db: AsyncSession) -> Dict[str, Any]:
        """
        Retorna o ROI e eficácia por canal de origem e tipo de entrada (Inbound vs Outbound).
        """
        # Agrupamento por canal de origem
        query_canais = select(
            models.Lead.origem_canal,
            func.count(models.Lead.id).label("total_leads"),
            func.coalesce(func.sum(case((models.Lead.desfecho == models.DesfechoLead.GANHO, 1), else_=0)), 0).label("leads_ganhos"),
            func.coalesce(
                func.sum(case((models.Lead.desfecho == models.DesfechoLead.GANHO, models.Lead.valor_estimado), else_=0.0)),
                0.0
            ).label("receita_reais"),
        ).group_by(models.Lead.origem_canal)

        resultado_canais = await db.execute(query_canais)
        canais_data = [
            {
                "origem_canal": canal or "WHATSAPP_DIRETO",
                "total_leads": int(total),
                "leads_ganhos": int(ganhos),
                "receita_reais": float(receita),
            }
            for canal, total, ganhos, receita in resultado_canais.all()
        ]

        # Agrupamento por tipo de entrada
        query_tipo = select(
            models.Lead.tipo_entrada,
            func.count(models.Lead.id).label("total_leads"),
            func.coalesce(func.sum(case((models.Lead.desfecho == models.DesfechoLead.GANHO, 1), else_=0)), 0).label("leads_ganhos"),
            func.coalesce(
                func.sum(case((models.Lead.desfecho == models.DesfechoLead.GANHO, models.Lead.valor_estimado), else_=0.0)),
                0.0
            ).label("receita_reais"),
        ).group_by(models.Lead.tipo_entrada)

        resultado_tipo = await db.execute(query_tipo)
        tipo_data = [
            {
                "tipo_entrada": tipo,
                "total_leads": int(total),
                "leads_ganhos": int(ganhos),
                "receita_reais": float(receita),
            }
            for tipo, total, ganhos, receita in resultado_tipo.all()
        ]

        return {
            "canais": canais_data,
            "tipos_entrada": tipo_data,
        }

    @staticmethod
    async def obter_ranking_perdas(db: AsyncSession, limite: int = 10) -> Dict[str, Any]:
        """
        Agrega os principais motivos de perda e descarte classificados pela IA.
        """
        query_ranking = (
            select(
                models.Lead.motivo_perda,
                func.count(models.Lead.id).label("quantidade"),
                func.coalesce(func.sum(models.Lead.valor_estimado), 0.0).label("valor_perdido"),
            )
            .where(models.Lead.desfecho.in_([models.DesfechoLead.PERDIDO, models.DesfechoLead.CONGELADO_CADENCIA]))
            .group_by(models.Lead.motivo_perda)
            .order_by(desc(func.count(models.Lead.id)))
            .limit(limite)
        )

        resultado = await db.execute(query_ranking)
        ranking = [
            {
                "motivo": str(motivo) if (motivo and str(motivo).strip()) else "Não Especificado",
                "quantidade": int(qtd),
                "valor_perdido_reais": float(valor),
            }
            for motivo, qtd, valor in resultado.all()
        ]

        # Total de descartes
        query_total = select(func.count(models.Lead.id)).where(
            models.Lead.desfecho.in_([models.DesfechoLead.PERDIDO, models.DesfechoLead.CONGELADO_CADENCIA])
        )
        total_descartes = (await db.execute(query_total)).scalar() or 0

        return {
            "total_descartes": total_descartes,
            "motivos_ranking": ranking,
        }

    @staticmethod
    async def obter_metricas_conversas_e_followup(db: AsyncSession) -> Dict[str, Any]:
        """
        Calcula o volume de mensagens no WhatsApp e a taxa de resgate da cadência de follow-up.
        """
        # Volume de mensagens
        query_msgs = select(
            models.Interacao.origem,
            func.count(models.Interacao.id).label("quantidade")
        ).group_by(models.Interacao.origem)

        resultado_msgs = await db.execute(query_msgs)
        msgs_map = {origem: int(qtd) for origem, qtd in resultado_msgs.all()}

        total_msgs = sum(msgs_map.values())
        msgs_cliente = msgs_map.get(models.InteracaoOrigem.CLIENTE, 0)
        msgs_operacao = msgs_map.get(models.InteracaoOrigem.IA, 0) + msgs_map.get(models.InteracaoOrigem.HUMANO, 0)

        # Eficácia da cadência temporal de follow-up
        query_fu = select(
            models.FollowupAgendado.status,
            func.count(models.FollowupAgendado.id).label("quantidade")
        ).group_by(models.FollowupAgendado.status)

        resultado_fu = await db.execute(query_fu)
        fu_map = {status: int(qtd) for status, qtd in resultado_fu.all()}

        total_agendados = sum(fu_map.values())
        total_disparados = fu_map.get(models.StatusFollowup.DISPARADO, 0)
        total_resgatados = fu_map.get(models.StatusFollowup.CANCELADO_POR_RESPOSTA, 0)

        # Leads congelados por cadência esgotada (3 toques)
        query_congelados = select(func.count(models.Lead.id)).where(
            models.Lead.desfecho == models.DesfechoLead.CONGELADO_CADENCIA
        )
        total_congelados = (await db.execute(query_congelados)).scalar() or 0

        return {
            "volume_mensagens": {
                "total_mensagens": total_msgs,
                "mensagens_clientes": msgs_cliente,
                "mensagens_operacao": msgs_operacao,
            },
            "eficacia_followup": {
                "total_agendados": total_agendados,
                "total_disparados": total_disparados,
                "total_resgatados_por_resposta": total_resgatados,
                "total_congelados_cadencia": total_congelados,
            }
        }
