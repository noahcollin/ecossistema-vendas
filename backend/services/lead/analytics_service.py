"""
Serviço de Inteligência Comercial e Analytics de Vendas (Clean Architecture / DDD).
Processa agregações do repositório, calcula taxas de conversão, ticket médio,
e compõe os DTOs para o Dashboard Executivo.
"""

from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.analytics_repository import AnalyticsRepository
import schemas


class AnalyticsService:
    """
    Camada de serviço especializada para consolidação de métricas comerciais do Lead.
    Aplica regras de negócio para cálculo de conversão, ranking de perdas e ROI de canais.
    """

    @classmethod
    async def obter_visao_geral(cls, db: AsyncSession) -> schemas.DashboardOverviewResponse:
        """
        Consolida os 5 blocos analíticos em um único payload veloz para a home do Dashboard.
        """
        financeiro = await cls.obter_metricas_financeiras(db)
        funil = await cls.obter_metricas_funil(db)
        aquisicao = await cls.obter_metricas_aquisicao(db)
        perdas = await cls.obter_metricas_perdas(db)
        conversas = await cls.obter_metricas_conversas(db)

        totais_dados = await AnalyticsRepository.obter_totais_e_financeiro(db)
        total_leads = totais_dados.get("total_leads", 0)

        return schemas.DashboardOverviewResponse(
            gerado_em=datetime.now(timezone.utc).replace(tzinfo=None),
            total_leads_cadastrados=total_leads,
            financeiro=financeiro,
            funil=funil,
            aquisicao=aquisicao,
            perdas=perdas,
            conversas=conversas,
        )

    @staticmethod
    async def obter_metricas_financeiras(db: AsyncSession) -> schemas.FinanceiroKPIs:
        """
        Calcula os indicadores financeiros de pipeline, receita ganha e conversão.
        """
        dados = await AnalyticsRepository.obter_totais_e_financeiro(db)

        total_ganhos = dados.get("total_ganhos", 0)
        total_perdidos = dados.get("total_perdidos", 0)
        receita_ganha = dados.get("receita_ganha_reais", 0.0)
        pipeline_ativo = dados.get("pipeline_ativo_reais", 0.0)
        valor_perdido = dados.get("valor_perdido_reais", 0.0)
        total_em_andamento = dados.get("total_em_andamento", 0)

        # Ticket médio = Receita ganha / Quantidade de vendas
        ticket_medio = (receita_ganha / total_ganhos) if total_ganhos > 0 else 0.0

        # Taxa de conversão sobre negócios finalizados (Ganhos / (Ganhos + Perdidos))
        total_finalizados = total_ganhos + total_perdidos
        taxa_conversao = ((total_ganhos / total_finalizados) * 100.0) if total_finalizados > 0 else 0.0

        return schemas.FinanceiroKPIs(
            pipeline_ativo_reais=round(pipeline_ativo, 2),
            receita_ganha_reais=round(receita_ganha, 2),
            valor_perdido_reais=round(valor_perdido, 2),
            ticket_medio_reais=round(ticket_medio, 2),
            total_leads_ganhos=total_ganhos,
            total_leads_perdidos=total_perdidos,
            total_leads_em_andamento=total_em_andamento,
            taxa_conversao_pct=round(taxa_conversao, 1),
        )

    @staticmethod
    async def obter_metricas_funil(db: AsyncSession) -> schemas.FunilKPIs:
        """
        Calcula a distribuição percentual e volumétrica por etapa e temperatura.
        """
        dados = await AnalyticsRepository.obter_distribuicao_funil(db)

        etapas_raw = dados.get("etapas", [])
        temp_raw = dados.get("temperaturas", [])
        leads_quentes = dados.get("leads_quentes_count", 0)

        total_etapas = sum(item["quantidade"] for item in etapas_raw)
        total_temp = sum(item["quantidade"] for item in temp_raw)

        por_etapa = [
            schemas.EtapaFunilDistribuicao(
                etapa=item["etapa"],
                quantidade=item["quantidade"],
                valor_total_reais=round(item["valor_total_reais"], 2),
                percentual_base=round((item["quantidade"] / total_etapas * 100.0), 1) if total_etapas > 0 else 0.0,
            )
            for item in etapas_raw
        ]

        por_temperatura = [
            schemas.TemperaturaDistribuicao(
                temperatura=item["temperatura"],
                quantidade=item["quantidade"],
                percentual=round((item["quantidade"] / total_temp * 100.0), 1) if total_temp > 0 else 0.0,
            )
            for item in temp_raw
        ]

        return schemas.FunilKPIs(
            por_etapa=por_etapa,
            por_temperatura=por_temperatura,
            leads_quentes_count=leads_quentes,
        )

    @staticmethod
    async def obter_metricas_aquisicao(db: AsyncSession) -> schemas.AquisicaoKPIs:
        """
        Calcula a conversão e receita por canal de captação e tipo de entrada.
        """
        dados = await AnalyticsRepository.obter_metricas_aquisicao(db)

        canais_raw = dados.get("canais", [])
        tipos_raw = dados.get("tipos_entrada", [])

        por_canal: List[schemas.CanalOrigemItem] = []
        canal_campeao_receita: Optional[str] = None
        maior_receita = -1.0

        canal_campeao_conversao: Optional[str] = None
        maior_taxa_conv = -1.0

        for item in canais_raw:
            total_canal = item["total_leads"]
            ganhos_canal = item["leads_ganhos"]
            receita_canal = item["receita_reais"]
            taxa_conv = ((ganhos_canal / total_canal) * 100.0) if total_canal > 0 else 0.0

            por_canal.append(
                schemas.CanalOrigemItem(
                    origem_canal=item["origem_canal"],
                    total_leads=total_canal,
                    leads_ganhos=ganhos_canal,
                    receita_reais=round(receita_canal, 2),
                    taxa_conversao_pct=round(taxa_conv, 1),
                )
            )

            if receita_canal > maior_receita and receita_canal > 0:
                maior_receita = receita_canal
                canal_campeao_receita = item["origem_canal"]

            if taxa_conv > maior_taxa_conv and ganhos_canal > 0:
                maior_taxa_conv = taxa_conv
                canal_campeao_conversao = item["origem_canal"]

        por_tipo = [
            schemas.TipoEntradaItem(
                tipo_entrada=item["tipo_entrada"],
                total_leads=item["total_leads"],
                leads_ganhos=item["leads_ganhos"],
                receita_reais=round(item["receita_reais"], 2),
                taxa_conversao_pct=round(
                    ((item["leads_ganhos"] / item["total_leads"] * 100.0) if item["total_leads"] > 0 else 0.0), 1
                ),
            )
            for item in tipos_raw
        ]

        return schemas.AquisicaoKPIs(
            por_canal=por_canal,
            por_tipo_entrada=por_tipo,
            canal_campeao_receita=canal_campeao_receita,
            canal_campeao_conversao=canal_campeao_conversao,
        )

    @staticmethod
    async def obter_metricas_perdas(db: AsyncSession, limite: int = 10) -> schemas.PerdasKPIs:
        """
        Processa o ranking de perdas e calcula o impacto percentual de cada objeção.
        """
        dados = await AnalyticsRepository.obter_ranking_perdas(db, limite=limite)

        total_descartes = dados.get("total_descartes", 0)
        ranking_raw = dados.get("motivos_ranking", [])

        motivos_ranking: List[schemas.MotivoPerdaItem] = [
            schemas.MotivoPerdaItem(
                motivo=item["motivo"],
                quantidade=item["quantidade"],
                valor_perdido_reais=round(item["valor_perdido_reais"], 2),
                percentual_do_total=round(
                    (item["quantidade"] / total_descartes * 100.0) if total_descartes > 0 else 0.0, 1
                ),
            )
            for item in ranking_raw
        ]

        principal_motivo = motivos_ranking[0].motivo if motivos_ranking else None

        return schemas.PerdasKPIs(
            total_descartes=total_descartes,
            motivos_ranking=motivos_ranking,
            principal_motivo=principal_motivo,
        )

    @staticmethod
    async def obter_metricas_conversas(db: AsyncSession) -> schemas.ConversasKPIs:
        """
        Processa métricas de mensagens e a taxa de resgate dos follow-ups.
        """
        dados = await AnalyticsRepository.obter_metricas_conversas_e_followup(db)

        vol_raw = dados.get("volume_mensagens", {})
        fu_raw = dados.get("eficacia_followup", {})

        total_disparados = fu_raw.get("total_disparados", 0)
        total_resgatados = fu_raw.get("total_resgatados_por_resposta", 0)

        # Taxa de resgate = Leads que voltaram a responder após o follow-up / total disparados
        taxa_resgate = ((total_resgatados / total_disparados) * 100.0) if total_disparados > 0 else 0.0

        volume = schemas.VolumeMensagensItem(
            total_mensagens=vol_raw.get("total_mensagens", 0),
            mensagens_clientes=vol_raw.get("mensagens_clientes", 0),
            mensagens_operacao=vol_raw.get("mensagens_operacao", 0),
        )

        eficacia = schemas.FollowupEficaciaKPIs(
            total_agendados=fu_raw.get("total_agendados", 0),
            total_disparados=total_disparados,
            total_resgatados_por_resposta=total_resgatados,
            total_congelados_cadencia=fu_raw.get("total_congelados_cadencia", 0),
            taxa_resgate_pct=round(taxa_resgate, 1),
        )

        return schemas.ConversasKPIs(
            volume_mensagens=volume,
            eficacia_followup=eficacia,
        )
