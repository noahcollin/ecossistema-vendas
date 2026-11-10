"""
Serviço de Domínio para Gestão de Configurações Operacionais Dinâmicas ("Sala de Máquinas").
Orquestra o ciclo de vida das regras comerciais, catálogo de produtos, pacing,
cadência de follow-up, horários comerciais e governança (Kill-Switch e Expurgo Redis),
sincronizando cache L1 em memória, cache L2 no Redis e persistência no PostgreSQL.
"""

import copy
import json
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logger import logger
from core.protocols import CacheBufferProtocol
from integrations.redis.buffer import redis_client
from integrations.redis.gateway import default_redis_buffer_gateway
from repositories.settings_repository import SettingsRepository, DEFAULT_OPERACAO_SETTINGS
from schemas.settings import (
    OperacaoSettingsResponse,
    OperacaoSettingsUpdate,
    KillSwitchResponse,
    RedisPurgeResponse,
)

REDIS_KEY_SETTINGS = "config:operacao_geral"


def _hidratar_com_defaults(dados: dict[str, Any] | None) -> dict[str, Any]:
    """
    Garante compatibilidade retroativa mesclando payloads do banco com os novos defaults,
    e migra automaticamente registros legados ('Seu Zé' / 'ecossistema_full' / '[2, 24, 72]')
    para a nova operação oficial do Eli Gentil (Inteligentte Lab).
    """
    base = copy.deepcopy(DEFAULT_OPERACAO_SETTINGS)
    if not dados:
        return base
    for chave, valor in dados.items():
        if isinstance(valor, dict) and isinstance(base.get(chave), dict):
            mesclado = dict(base[chave])
            mesclado.update(valor)
            base[chave] = mesclado
        elif valor is not None:
            base[chave] = valor

    # Migração automática de registros legados ('Seu Zé' ou catálogo antigo)
    msg_inat = str(base.get("mensagem_inatividade") or "")
    if "Seu Zé" in msg_inat:
        base["mensagem_inatividade"] = DEFAULT_OPERACAO_SETTINGS["mensagem_inatividade"]

    produtos = base.get("produtos") or []
    ids_produtos = {p.get("id") for p in produtos if isinstance(p, dict)}
    if ids_produtos & {"ecossistema_full", "agente_crm", "agente_whatsapp", "demand_ai"}:
        base["produtos"] = copy.deepcopy(DEFAULT_OPERACAO_SETTINGS["produtos"])

    cadencia = base.get("cadencia")
    if isinstance(cadencia, dict) and (
        cadencia.get("intervalos_toques") == [2.0, 24.0, 72.0]
        or cadencia.get("intervalo_horas") == 24
    ):
        cadencia["intervalos_toques"] = [2.0, 6.0, 12.0]
        cadencia["intervalo_horas"] = 6

    if base.get("debounce_segundos") == 4.5:
        base["debounce_segundos"] = 8.0

    return base


class SettingsService:
    """Regras de negócio e cache vivo para leitura, atualização e governança operacional."""

    _cache_memoria: OperacaoSettingsResponse = OperacaoSettingsResponse(
        **_hidratar_com_defaults(None)
    )

    @classmethod
    def obter_cache_memoria(cls) -> OperacaoSettingsResponse:
        """
        Retorna instantaneamente (O(1), sem I/O bloqueante) o snapshot vivo das configurações.
        Consumido por agentes de IA, políticas de horário comercial e orquestrador inbound.
        """
        return cls._cache_memoria

    @classmethod
    def esta_ia_silenciada(cls) -> bool:
        """Retorna True se o Kill-Switch global da operação autônoma estiver ativo."""
        return bool(cls._cache_memoria.ia_silenciada_global)

    @classmethod
    def _sincronizar_runtime(cls, resposta: OperacaoSettingsResponse) -> None:
        """
        Atualiza o snapshot L1 em memória e sincroniza os atributos reais de `core.config.settings`
        para que todos os workers e serviços reflitam imediatamente as decisões do gestor.
        """
        cls._cache_memoria = resposta

        try:
            settings.DEBOUNCE_SECONDS = float(resposta.debounce_segundos)

            hc = resposta.horario_comercial
            settings.BUSINESS_HOURS_START = f"{int(hc.inicio_hora):02d}:00"
            settings.BUSINESS_HOURS_END = f"{int(hc.fim_hora):02d}:00"

            cad = resposta.cadencia
            toques = list(cad.intervalos_toques or [])
            if len(toques) >= 1:
                settings.FOLLOWUP_INTERVAL_1_HOURS = float(toques[0])
            elif cad.intervalo_horas:
                settings.FOLLOWUP_INTERVAL_1_HOURS = float(cad.intervalo_horas)
            if len(toques) >= 2:
                settings.FOLLOWUP_INTERVAL_2_HOURS = float(toques[1])
            if len(toques) >= 3:
                settings.FOLLOWUP_INTERVAL_3_HOURS = float(toques[2])

            pacing = resposta.pacing
            settings.FOLLOWUP_SIMULAR_DIGITACAO = bool(pacing.simular_digitacao)
            settings.PACING_THRESHOLD_PROACTIVE = int(pacing.limiar_proativo)
            settings.PACING_THRESHOLD_DECISIVE = int(pacing.limiar_decisivo)
            settings.PACING_THRESHOLD_MAX = int(pacing.limiar_max_finops)
        except Exception as e:
            logger.warning(f"[SETTINGS SERVICE] Falha ao sincronizar runtime settings: {e}")

    @classmethod
    async def obter_configuracoes(cls, db: AsyncSession) -> OperacaoSettingsResponse:
        """
        Retorna as configurações ativas da operação.
        Utiliza cache L2 no Redis, sincroniza cache L1 em memória e faz seed automático no PostgreSQL.
        """
        # 1. Tenta recuperar do Redis (sub-millisecond)
        try:
            cached_raw = await redis_client.get(REDIS_KEY_SETTINGS)
            if cached_raw:
                dados_cache = _hidratar_com_defaults(json.loads(cached_raw))
                resposta = OperacaoSettingsResponse(**dados_cache)
                cls._sincronizar_runtime(resposta)
                return resposta
        except Exception as e:
            logger.warning(f"[SETTINGS SERVICE] Cache Redis indisponível para leitura: {e}")

        # 2. Busca no PostgreSQL
        config_db = await SettingsRepository.get_by_chave(db, chave="geral")

        # 3. Seed automático inicial se o banco estiver vazio
        if not config_db:
            logger.info("[SETTINGS SERVICE] ⚙️ Nenhuma configuração encontrada. Realizando seed inicial com defaults.")
            config_db = await SettingsRepository.salvar_ou_atualizar(
                db=db,
                novos_dados=copy.deepcopy(DEFAULT_OPERACAO_SETTINGS),
                chave="geral"
            )

        dados = _hidratar_com_defaults(dict(config_db.dados or {}))
        dados["atualizado_em"] = config_db.atualizado_em

        # Popula cache L2 no Redis
        try:
            await redis_client.set(REDIS_KEY_SETTINGS, json.dumps(dados, default=str), ex=3600)
        except Exception as e:
            logger.warning(f"[SETTINGS SERVICE] Falha ao gravar cache no Redis: {e}")

        resposta = OperacaoSettingsResponse(**dados)
        cls._sincronizar_runtime(resposta)
        return resposta

    @classmethod
    async def atualizar_configuracoes(
        cls,
        db: AsyncSession,
        payload: OperacaoSettingsUpdate
    ) -> OperacaoSettingsResponse:
        """
        Atualiza dinamicamente as configurações operacionais da empresa.
        Sincroniza PostgreSQL, cache Redis L2 e runtime L1 em tempo real.
        """
        config_db = await SettingsRepository.get_by_chave(db, chave="geral")
        dados_atuais = _hidratar_com_defaults(
            dict(config_db.dados) if config_db and config_db.dados else None
        )

        # Atualizações parciais preservando valores existentes
        if payload.produtos is not None:
            dados_atuais["produtos"] = [p.model_dump() for p in payload.produtos]

        if payload.cadencia is not None:
            dados_atuais["cadencia"] = payload.cadencia.model_dump()

        if payload.horario_comercial is not None:
            dados_atuais["horario_comercial"] = payload.horario_comercial.model_dump()

        if payload.pacing is not None:
            dados_atuais["pacing"] = payload.pacing.model_dump()

        if payload.debounce_segundos is not None:
            dados_atuais["debounce_segundos"] = payload.debounce_segundos

        if payload.modo_24h_inbound is not None:
            dados_atuais["modo_24h_inbound"] = payload.modo_24h_inbound

        if payload.ia_silenciada_global is not None:
            dados_atuais["ia_silenciada_global"] = payload.ia_silenciada_global

        if payload.mensagem_inatividade is not None:
            dados_atuais["mensagem_inatividade"] = payload.mensagem_inatividade

        # Persiste no PostgreSQL
        config_atualizada = await SettingsRepository.salvar_ou_atualizar(
            db=db,
            novos_dados=dados_atuais,
            chave="geral"
        )

        dados_retorno = _hidratar_com_defaults(dict(config_atualizada.dados or {}))
        dados_retorno["atualizado_em"] = config_atualizada.atualizado_em

        # Atualiza cache L2 no Redis
        try:
            await redis_client.set(REDIS_KEY_SETTINGS, json.dumps(dados_retorno, default=str), ex=3600)
        except Exception as e:
            logger.warning(f"[SETTINGS SERVICE] Falha ao atualizar cache no Redis: {e}")

        resposta = OperacaoSettingsResponse(**dados_retorno)
        cls._sincronizar_runtime(resposta)
        logger.info("[SETTINGS SERVICE] 🚀 Configurações operacionais sincronizadas com sucesso.")
        return resposta

    @classmethod
    async def alternar_kill_switch(
        cls,
        db: AsyncSession,
        silenciar: bool
    ) -> KillSwitchResponse:
        """
        Ativa ou desativa o Kill-Switch global da operação autônoma de IA.
        Quando ativo, todas as mensagens inbound continuam sendo persistidas no banco,
        porém nenhuma resposta autônoma ou follow-up é disparado pela IA.
        """
        atualizado = await cls.atualizar_configuracoes(
            db=db,
            payload=OperacaoSettingsUpdate(ia_silenciada_global=silenciar)
        )
        mensagem = (
            "Kill-Switch ATIVADO: toda operação autônoma da IA foi pausada com segurança."
            if silenciar
            else "Kill-Switch DESATIVADO: operação autônoma da IA retomada normalmente."
        )
        logger.warning(f"[GOVERNANÇA IA] 🛡️ {mensagem}")
        return KillSwitchResponse(
            ia_silenciada_global=atualizado.ia_silenciada_global,
            atualizado_em=atualizado.atualizado_em,
            mensagem=mensagem,
        )

    @classmethod
    async def expurgar_filas_redis(
        cls,
        buffer_gateway: CacheBufferProtocol = default_redis_buffer_gateway
    ) -> RedisPurgeResponse:
        """
        Expurga de forma não-bloqueante todas as filas voláteis de debounce e locks no Redis
        sem afetar leads, interações ou configurações persistidas.
        """
        removidas = await buffer_gateway.expurgar_filas_volateis()
        return RedisPurgeResponse(
            status="sucesso",
            chaves_removidas=removidas,
            mensagem=f"{removidas} chave(s) voláteis de debounce/locks expurgadas do Redis.",
        )

    @classmethod
    def montar_resumo_catalogo_prompt(cls) -> str:
        """
        Formata o catálogo de produtos ativos configurado no Dashboard para injeção dinâmica
        no prompt do Agente ('Eli Gentil'), respeitando a regra de que preço e proposta ficam com o time na conversa de 20 min.
        """
        ativos = [p for p in cls._cache_memoria.produtos if p.ativo]
        if not ativos:
            return ""

        linhas = [
            "PORTFÓLIO ATIVO SINCRONIZADO PELA SALA DE MÁQUINAS (LEMBRETE: Eli Gentil NÃO informa preços nem envia proposta, e NUNCA cita o nome de quem fecha — diga sempre 'meu time' ou 'nosso especialista'):"
        ]
        for prod in ativos:
            partes = [
                f"- {prod.nome} (ID: {prod.id})",
            ]
            if prod.modelo_comercial:
                partes.append(f"Modelo: {prod.modelo_comercial}")
            if prod.qualificacao_minima:
                partes.append(f"Qualificação mínima: {prod.qualificacao_minima}")
            if prod.diretriz_venda:
                partes.append(f"Diretriz tática: {prod.diretriz_venda}")
            elif prod.descricao:
                partes.append(f"Escopo: {prod.descricao}")
            linhas.append(" | ".join(partes))

        return "\n".join(linhas)
