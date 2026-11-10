"""
Repositório de Acesso a Dados para Configurações Operacionais.
Gerencia a persistência e recuperação do payload singleton de regras comerciais.
"""

from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.settings import ConfiguracaoOperacional
from core.logger import logger

DEFAULT_OPERACAO_SETTINGS: Dict[str, Any] = {
    "produtos": [
        {
            "id": "agente_whatsapp",
            "nome": "Agentes Personalizados de IA (Prioridade 1)",
            "descricao": "Agentes de IA construídos sob medida para vendas, cobranças, agendamentos e atendimento 24/7 no WhatsApp da empresa",
            "modelo_comercial": "Sob Consulta na Conversa com o Time",
            "qualificacao_minima": "Operação com atendimento no WhatsApp que precisa devolver tempo à equipe e não perder leads fora de horário",
            "diretriz_venda": "Prioridade 1: destacar que um agente treinado com o conteúdo do cliente responde na hora, 24h, e só chama alguém do time quando precisa de gente.",
            "preco_base_mensal": 3500.0,
            "taxa_setup": 1500.0,
            "ativo": True,
        },
        {
            "id": "chat_inteligentte",
            "nome": "Chat Inteligentte — CRM para WhatsApp (Prioridade 2)",
            "descricao": "CRM ligado ao WhatsApp, com cada contato, estágio e histórico em um lugar só",
            "modelo_comercial": "Sob Consulta na Conversa com o Time",
            "qualificacao_minima": "Equipes precisando organizar quem já foi atendido e manter histórico e estágio em um só lugar",
            "diretriz_venda": "Prioridade 2: apresentar quando o cliente não sabe quem já foi atendido ou perde o histórico.",
            "preco_base_mensal": 1800.0,
            "taxa_setup": 800.0,
            "ativo": True,
        },
        {
            "id": "send_inteligentte",
            "nome": "Send Inteligentte — Disparador API Oficial (Prioridade 3)",
            "descricao": "Disparo pela API oficial da Meta, sem risco de bloqueio, com a resposta caindo no mesmo atendimento",
            "modelo_comercial": "Sob Consulta na Conversa com o Time",
            "qualificacao_minima": "Empresas que querem avisar ou reativar a base com segurança pela API Oficial da Meta",
            "diretriz_venda": "Prioridade 3: apresentar quando o lead quiser avisar ou reativar a base sem mandar um por um e sem risco de bloqueio.",
            "preco_base_mensal": 2500.0,
            "taxa_setup": 1000.0,
            "ativo": True,
        },
        {
            "id": "demand_ai",
            "nome": "Dashboard de Atendimento / Projetos por Demanda (Prioridade 4)",
            "descricao": "Painel com volume, tempo de resposta e onde o contato trava, além de projetos e integrações sob medida",
            "modelo_comercial": "Sob Consulta na Conversa com o Time",
            "qualificacao_minima": "Operações que não sabem quanto atendem nem onde perdem, ou demandas com mais de um ponto",
            "diretriz_venda": "Prioridade 4: apresentar Dashboard quando não souber métricas do atendimento, ou Diagnóstico quando houver dois ou mais pontos.",
            "preco_base_mensal": 4200.0,
            "taxa_setup": 2000.0,
            "ativo": True,
        },
    ],
    "cadencia": {
        "max_tentativas": 3,
        "intervalo_horas": 6,
        "intervalos_toques": [2.0, 6.0, 12.0],
        "apenas_dias_uteis": True,
        "respeitar_horario_comercial": True,
    },
    "horario_comercial": {
        "inicio_hora": 8,
        "fim_hora": 18,
        "dias_semana": [0, 1, 2, 3, 4],
        "fuso_horario": "America/Sao_Paulo",
    },
    "pacing": {
        "delay_base_ms": 1500,
        "intervalo_entre_baloes_seg": 1.8,
        "simular_digitacao": True,
        "limiar_proativo": 10,
        "limiar_decisivo": 20,
        "limiar_max_finops": 30,
    },
    "debounce_segundos": 8.0,
    "modo_24h_inbound": True,
    "ia_silenciada_global": False,
    "mensagem_inatividade": "Vou encerrar por aqui para não te encher. Se fizer sentido mais para frente, é só chamar.",
}


class SettingsRepository:
    """Repositório de persistência para as configurações operacionais dinâmicas."""

    @staticmethod
    async def get_by_chave(db: AsyncSession, chave: str = "geral") -> Optional[ConfiguracaoOperacional]:
        """Recupera a configuração persistida pela chave."""
        stmt = select(ConfiguracaoOperacional).where(ConfiguracaoOperacional.chave == chave)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def salvar_ou_atualizar(
        db: AsyncSession,
        novos_dados: Dict[str, Any],
        chave: str = "geral"
    ) -> ConfiguracaoOperacional:
        """Cria ou atualiza atomicamente as configurações da operação."""
        config = await SettingsRepository.get_by_chave(db, chave)
        if not config:
            config = ConfiguracaoOperacional(chave=chave, dados=dict(novos_dados))
            db.add(config)
        else:
            dados_atuais = dict(config.dados or {})
            dados_atuais.update(novos_dados)
            config.dados = dados_atuais

        await db.commit()
        await db.refresh(config)
        logger.info(f"[SETTINGS REPO] ⚙️ Configurações '{chave}' atualizadas com sucesso no banco.")
        return config
