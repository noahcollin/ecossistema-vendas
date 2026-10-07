"""
Serviço de Domínio para Gestão de Configurações Operacionais Dinâmicas.
Orquestra o ciclo de vida das regras comerciais, catálogo de produtos,
cadência de follow-up e horários comerciais com cache no Redis.
"""

import json
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from repositories.settings_repository import SettingsRepository, DEFAULT_OPERACAO_SETTINGS
from schemas.settings import OperacaoSettingsResponse, OperacaoSettingsUpdate
from integrations.redis.buffer import redis_client
from core.logger import logger
from core.config import settings

REDIS_KEY_SETTINGS = "config:operacao_geral"


class SettingsService:
    """Regras de negócio para leitura e atualização das configurações operacionais."""

    @classmethod
    async def obter_configuracoes(cls, db: AsyncSession) -> OperacaoSettingsResponse:
        """
        Retorna as configurações ativas da operação.
        Utiliza cache L2 no Redis e fallback com seed automático no PostgreSQL.
        """
        # 1. Tenta recuperar do Redis (sub-millisecond)
        try:
            cached_raw = await redis_client.get(REDIS_KEY_SETTINGS)
            if cached_raw:
                dados_cache = json.loads(cached_raw)
                return OperacaoSettingsResponse(**dados_cache)
        except Exception as e:
            logger.warning(f"[SETTINGS SERVICE] Cache Redis indisponível para leitura: {e}")

        # 2. Busca no PostgreSQL
        config_db = await SettingsRepository.get_by_chave(db, chave="geral")
        
        # 3. Seed automático inicial se o banco estiver vazio
        if not config_db:
            logger.info("[SETTINGS SERVICE] ⚙️ Nenhuma configuração encontrada. Realizando seed inicial com defaults.")
            config_db = await SettingsRepository.salvar_ou_atualizar(
                db=db,
                novos_dados=DEFAULT_OPERACAO_SETTINGS,
                chave="geral"
            )

        dados = dict(config_db.dados or {})
        dados["atualizado_em"] = config_db.atualizado_em

        # Popula cache no Redis
        try:
            await redis_client.set(REDIS_KEY_SETTINGS, json.dumps(dados, default=str), ex=3600)
        except Exception as e:
            logger.warning(f"[SETTINGS SERVICE] Falha ao gravar cache no Redis: {e}")

        return OperacaoSettingsResponse(**dados)

    @classmethod
    async def atualizar_configuracoes(
        cls,
        db: AsyncSession,
        payload: OperacaoSettingsUpdate
    ) -> OperacaoSettingsResponse:
        """
        Atualiza dinamicamente as configurações operacionais da empresa.
        Sincroniza PostgreSQL, invalida cache no Redis e atualiza variáveis de runtime.
        """
        config_db = await SettingsRepository.get_by_chave(db, chave="geral")
        dados_atuais = dict(config_db.dados if config_db and config_db.dados else DEFAULT_OPERACAO_SETTINGS)

        # Atualizações parciais preservando valores existentes
        if payload.produtos is not None:
            dados_atuais["produtos"] = [p.model_dump() for p in payload.produtos]

        if payload.cadencia is not None:
            dados_atuais["cadencia"] = payload.cadencia.model_dump()

        if payload.horario_comercial is not None:
            dados_atuais["horario_comercial"] = payload.horario_comercial.model_dump()

        if payload.debounce_segundos is not None:
            dados_atuais["debounce_segundos"] = payload.debounce_segundos

        if payload.mensagem_inatividade is not None:
            dados_atuais["mensagem_inatividade"] = payload.mensagem_inatividade

        # Persiste no PostgreSQL
        config_atualizada = await SettingsRepository.salvar_ou_atualizar(
            db=db,
            novos_dados=dados_atuais,
            chave="geral"
        )

        dados_retorno = dict(config_atualizada.dados)
        dados_retorno["atualizado_em"] = config_atualizada.atualizado_em

        # Invalida e atualiza cache no Redis
        try:
            await redis_client.set(REDIS_KEY_SETTINGS, json.dumps(dados_retorno, default=str), ex=3600)
        except Exception as e:
            logger.warning(f"[SETTINGS SERVICE] Falha ao atualizar cache no Redis: {e}")

        # Sincroniza parâmetros de runtime no objeto settings
        try:
            if "horario_comercial" in dados_retorno:
                hc = dados_retorno["horario_comercial"]
                settings.HORARIO_COMERCIAL_INICIO = hc.get("inicio_hora", settings.HORARIO_COMERCIAL_INICIO)
                settings.HORARIO_COMERCIAL_FIM = hc.get("fim_hora", settings.HORARIO_COMERCIAL_FIM)
                settings.DIAS_UTEIS_SEMANA = hc.get("dias_semana", settings.DIAS_UTEIS_SEMANA)
            if "cadencia" in dados_retorno:
                cad = dados_retorno["cadencia"]
                settings.FOLLOWUP_MAX_TENTATIVAS = cad.get("max_tentativas", settings.FOLLOWUP_MAX_TENTATIVAS)
                settings.FOLLOWUP_INTERVALO_HORAS = cad.get("intervalo_horas", settings.FOLLOWUP_INTERVALO_HORAS)
        except Exception as e:
            logger.warning(f"[SETTINGS SERVICE] Falha ao sincronizar runtime settings: {e}")

        logger.info("[SETTINGS SERVICE] 🚀 Configurações operacionais sincronizadas com sucesso.")
        return OperacaoSettingsResponse(**dados_retorno)
