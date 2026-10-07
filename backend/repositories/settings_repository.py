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
            "nome": "Agente Autônomo WhatsApp 24h",
            "descricao": "Atendimento receptivo, qualificação e agendamento automático 24/7",
            "preco_base_mensal": 3500.0,
            "taxa_setup": 1500.0,
            "ativo": True,
        },
        {
            "id": "chat_inteligentte",
            "nome": "Chatbot Híbrido Triagem & Atendimento",
            "descricao": "Solução híbrida para distribuição de filas com transbordo humano",
            "preco_base_mensal": 1800.0,
            "taxa_setup": 800.0,
            "ativo": True,
        },
        {
            "id": "demand_ai",
            "nome": "Motor de Prospecção Outbound Inteligente",
            "descricao": "Cadência ativa outbound com geração e qualificação de listas",
            "preco_base_mensal": 4200.0,
            "taxa_setup": 2000.0,
            "ativo": True,
        },
    ],
    "cadencia": {
        "max_tentativas": 3,
        "intervalo_horas": 24,
        "apenas_dias_uteis": True,
        "respeitar_horario_comercial": True,
    },
    "horario_comercial": {
        "inicio_hora": 8,
        "fim_hora": 18,
        "dias_semana": [0, 1, 2, 3, 4],
        "fuso_horario": "America/Sao_Paulo",
    },
    "debounce_segundos": 4.5,
    "mensagem_inatividade": "Olá! Notei que não conseguimos avançar no momento. Ficamos à disposição quando fizer sentido para você!",
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
            config = ConfiguracaoOperacional(chave=chave, dados=novos_dados)
            db.add(config)
        else:
            # Mescla mantendo a integridade
            dados_atuais = dict(config.dados or {})
            dados_atuais.update(novos_dados)
            config.dados = dados_atuais

        await db.commit()
        await db.refresh(config)
        logger.info(f"[SETTINGS REPO] ⚙️ Configurações '{chave}' atualizadas com sucesso no banco.")
        return config
