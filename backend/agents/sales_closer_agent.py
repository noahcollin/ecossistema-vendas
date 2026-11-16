import re
from typing import List, Optional
from core.logger import logger
from core.openai_client import openai_client, is_openai_quota_error
from core.config import settings
from core.temporal import TemporalContextProvider
from core.utils import higienizar_nome_perfil
import models
from .prompts import (
    PROMPT_BASE_VENDEDOR,
    ORIENTACOES_POR_ESTAGIO,
    ORIENTACOES_FOLLOWUP,
)


def _obter_contexto_settings_dinamico() -> tuple[str, int]:
    """Obtém o resumo do catálogo vigente e o limite de toques sem acoplamento circular de importação."""
    try:
        from services.settings import SettingsService
        catalogo = SettingsService.montar_resumo_catalogo_prompt()
        max_toques = int(SettingsService.obter_cache_memoria().cadencia.max_tentativas or 3)
        return catalogo, max_toques
    except Exception:
        return "", 3


_MAPA_ORIGEM_LEAD = {
    "META_ADS": "anúncio Meta Ads (clique para WhatsApp)",
    "GOOGLE_SEARCH": "pesquisa Google",
    "SITE_LANDING_PAGE": "site / landing page",
    "INDICACAO": "indicação",
    "WHATSAPP_DIRETO": "contato direto no WhatsApp",
}


def _formatar_origem_lead(origem_canal: Optional[str]) -> str:
    """Converte o código de origem_canal em descrição legível para o prompt do Eli v3."""
    if not origem_canal:
        return "contato direto no WhatsApp"
    chave = str(origem_canal).strip().upper()
    return _MAPA_ORIGEM_LEAD.get(chave, str(origem_canal).strip())


def _montar_prompt_base_vendedor(
    origem_canal: Optional[str] = None,
    horarios_livres: Optional[str] = None,
) -> str:
    """Injeta as variáveis dinâmicas ({data_hora_atual}, {origem_lead}, {horarios_livres}) no PROMPT_BASE_VENDEDOR."""
    data_hora_atual = TemporalContextProvider.formatar_data_hora_atual_prompt()
    origem_lead = _formatar_origem_lead(origem_canal)
    livres = horarios_livres if horarios_livres is not None else TemporalContextProvider.gerar_horarios_livres_prompt()
    return (
        PROMPT_BASE_VENDEDOR
        .replace("{data_hora_atual}", data_hora_atual)
        .replace("{origem_lead}", origem_lead)
        .replace("{horarios_livres}", livres)
    )


def _formatar_dados_ja_sabemos(dados_qualificacao: Optional[dict]) -> str:
    """Formata o resumo explícito do que o Analista já extraiu para evitar perguntas repetidas."""
    if not dados_qualificacao or not isinstance(dados_qualificacao, dict):
        return ""
    ramo = dados_qualificacao.get("ramo_atividade") or dados_qualificacao.get("segmento") or "ainda não"
    canal = dados_qualificacao.get("canal_principal") or dados_qualificacao.get("rede_social") or "ainda não"
    dor = dados_qualificacao.get("dor_principal") or dados_qualificacao.get("necessidade") or "ainda não"
    return f"\nJá sabemos (extraído pelo Analista — não pergunte de novo se já preenchido): ramo = {ramo}, canal = {canal}, dor = {dor}.\n"


_RE_PREFIXO_TS = re.compile(r"^\[\d{2}/\d{2}\s+\d{2}:\d{2}\]\s*")


def _limpar_prefixo_timestamp(texto: str) -> str:
    """Remove eventual prefixo de timestamp '[dd/mm HH:MM] ' copiado pelo modelo ou salvo no histórico."""
    if not texto:
        return ""
    baloes = [_RE_PREFIXO_TS.sub("", b.strip()) for b in texto.split("|||")]
    return "|||".join(b for b in baloes if b)


def formatar_dialogo_para_chat(
    historico_recente: Optional[List[models.Interacao]],
    janela_tamanho: int = 6
) -> List[dict[str, str]]:
    """
    Formata o histórico recente em mensagens para o chat completion da OpenAI,
    distinguindo mensagens do cliente, do consultor humano e notas de sistema,
    sem prefixar timestamps nas falas para evitar que o modelo copie '[dd/mm HH:MM]' na resposta.
    """
    if not historico_recente:
        return []

    mensagens_janela = historico_recente[-janela_tamanho:] if len(historico_recente) > janela_tamanho else historico_recente
    chat_msgs = []
    for interacao in mensagens_janela:
        texto_limpo = _limpar_prefixo_timestamp(interacao.texto or "")
        if interacao.origem == models.InteracaoOrigem.CLIENTE:
            chat_msgs.append({"role": "user", "content": texto_limpo})
        elif interacao.origem == models.InteracaoOrigem.HUMANO:
            chat_msgs.append({
                "role": "assistant",
                "content": f"[Mensagem do Consultor da nossa equipe]: {texto_limpo}"
            })
        elif interacao.origem == models.InteracaoOrigem.SISTEMA:
            chat_msgs.append({
                "role": "system",
                "content": f"[Diretriz Interna de Atendimento]: {texto_limpo}"
            })
        else:
            chat_msgs.append({"role": "assistant", "content": texto_limpo})
    return chat_msgs


async def gerar_resposta_vendedor(
    nome_cliente_bruto: str,
    ficha_resumo: Optional[str],
    etapa_funil: Optional[models.EtapaFunil] = None,
    historico_recente: Optional[List[models.Interacao]] = None,
    diretriz_proatividade: Optional[str] = None,
    origem_canal: Optional[str] = None,
    horarios_livres: Optional[str] = None,
    dados_qualificacao: Optional[dict] = None,
    **kwargs
) -> Optional[str]:
    """
    Gera a resposta enxuta e direta do Assistente Comercial ('Eli Gentil') via GPT-4o,
    alimentado pela Ficha do Lead, portfólio oficial da Inteligentte Lab,
    etapa atual da jornada, últimas mensagens imediatas e diretrizes de proatividade.
    """
    try:
        historico_lista = list(historico_recente) if historico_recente else []
        nome_validado = higienizar_nome_perfil(nome_cliente_bruto)

        if nome_validado:
            instrucao_nome = f"\n[NOME_NO_PERFIL]: {nome_validado}"
        else:
            instrucao_nome = "\n[NOME_NO_PERFIL]: Não informado no perfil do WhatsApp."

        etapa_atual = etapa_funil or models.EtapaFunil.QUALIFICACAO
        orientacao_estagio = ORIENTACOES_POR_ESTAGIO.get(etapa_atual, "Conduza a conversa de forma consultiva e empática.")
        ficha_formatada = ficha_resumo.strip() if ficha_resumo else "Primeiro contato, ainda sem dados acumulados."
        bloco_proatividade = f"\n{diretriz_proatividade}\n" if diretriz_proatividade else ""
        bloco_ja_sabemos = _formatar_dados_ja_sabemos(dados_qualificacao)

        catalogo_dinamico, _ = _obter_contexto_settings_dinamico()
        bloco_catalogo = f"\n[{catalogo_dinamico}]\n" if catalogo_dinamico else ""

        prompt_base_injetado = _montar_prompt_base_vendedor(
            origem_canal=origem_canal,
            horarios_livres=horarios_livres,
        )

        bloco_contexto = f"""
{prompt_base_injetado}
{instrucao_nome}
{bloco_catalogo}
[FICHA ATUALIZADA DO CLIENTE - MEMÓRIA DE LONGO PRAZO]
{ficha_formatada}
{bloco_ja_sabemos}
[ESTÁGIO ATUAL DA NEGOCIAÇÃO NO FUNIL]
Etapa: {etapa_atual.value}
Objetivo Desta Etapa: {orientacao_estagio}
{bloco_proatividade}"""

        mensagens = [{"role": "system", "content": bloco_contexto}]
        mensagens.extend(formatar_dialogo_para_chat(historico_lista, settings.JANELA_HISTORICO_RECENTE))

        # Roteamento Dinâmico de Modelos (FinOps)
        if settings.DYNAMIC_MODEL_ROUTING:
            if etapa_atual in [models.EtapaFunil.NOVO_CONTATO, models.EtapaFunil.QUALIFICACAO]:
                modelo_selecionado = settings.MODEL_CLOSER_FAST
            else:
                modelo_selecionado = settings.MODEL_CLOSER_ADVANCED
        else:
            modelo_selecionado = settings.MODEL_CLOSER

        logger.info(
            f"[VENDEDOR] 🧠 {modelo_selecionado} invocado para {nome_validado or 'Cliente'} | "
            f"Etapa: {etapa_atual.value} | Histórico: {len(historico_lista)} msgs imediatas"
        )

        resposta = await openai_client.chat.completions.create(
            model=modelo_selecionado,
            messages=mensagens,
            temperature=0.45,
            max_tokens=300
        )

        conteudo = _limpar_prefixo_timestamp(resposta.choices[0].message.content or "")
        logger.info(f"[VENDEDOR] 🤖 Resposta gerada com sucesso ({len(conteudo)} chars)")
        return conteudo

    except Exception as e:
        if is_openai_quota_error(e):
            logger.critical(
                f"[OPENAI COTA ESGOTADA] 🚨 Créditos da OpenAI esgotados! Silenciando IA para evitar envio de mensagens confusas ao cliente: {e}"
            )
        else:
            logger.error(f"[VENDEDOR ERRO] ❌ Falha na geração da resposta comercial: {e}", exc_info=True)
        return None


async def gerar_mensagem_followup(
    nome_cliente_bruto: str,
    ficha_resumo: Optional[str],
    etapa_funil: Optional[models.EtapaFunil],
    tentativa: int,
    historico_recente: Optional[List[models.Interacao]] = None,
    origem_canal: Optional[str] = None,
    horarios_livres: Optional[str] = None,
) -> Optional[str]:
    """
    Gera mensagem de resgate/follow-up direta e sem pedidos de desculpa do Assistente ('Eli Gentil')
    conforme a tentativa na cadência e o histórico prévio (RF11 do PRD).
    """
    try:
        historico_lista = list(historico_recente) if historico_recente else []
        etapa_atual = etapa_funil or models.EtapaFunil.QUALIFICACAO
        nome_validado = higienizar_nome_perfil(nome_cliente_bruto)
        if nome_validado:
            instrucao_nome = f"\n[NOME_NO_PERFIL]: {nome_validado}"
        else:
            instrucao_nome = "\n[NOME_NO_PERFIL]: Não informado no perfil do WhatsApp."

        catalogo_dinamico, max_toques = _obter_contexto_settings_dinamico()

        diretriz_tentativa = ORIENTACOES_FOLLOWUP.get(
            tentativa,
            "Relembre o ponto em aberto com cordialidade e simpatia."
        )

        ficha_formatada = ficha_resumo.strip() if ficha_resumo else "Em processo de qualificação."
        bloco_catalogo = f"\n[{catalogo_dinamico}]\n" if catalogo_dinamico else ""
        prompt_base_injetado = _montar_prompt_base_vendedor(
            origem_canal=origem_canal,
            horarios_livres=horarios_livres,
        )

        bloco_contexto = f"""
{prompt_base_injetado}
{instrucao_nome}
{bloco_catalogo}
[FICHA ATUALIZADA DO CLIENTE - MEMÓRIA DE LONGO PRAZO]
{ficha_formatada}

[CADÊNCIA DE RESGATE / FOLLOW-UP ATIVO - TOQUE {tentativa}/{max_toques}]
Etapa do Funil Onde o Lead Parou: {etapa_atual.value}
Diretriz Deste Toque: {diretriz_tentativa}

INSTRUÇÕES CRÍTICAS DE CADÊNCIA:
1. Jamais seja agressivo ou pareça cobrador. Você é um parceiro comercial consultivo e atencioso.
2. Seja conciso (1 a 3 frases). Lembre que é WhatsApp.
3. Se não for o último toque, termine com uma pergunta leve para estimular a resposta.
4. Se for o último toque ({max_toques}), NÃO force resposta: agradeça e encerre desejando sucesso, deixando claro que a porta continua aberta.
"""

        mensagens = [{"role": "system", "content": bloco_contexto}]
        mensagens.extend(formatar_dialogo_para_chat(historico_lista, settings.JANELA_HISTORICO_RECENTE))

        mensagens.append({
            "role": "system",
            "content": f"[INSTRUÇÃO FINAL]: O cliente parou de responder. Envie a mensagem de Follow-up (Toque {tentativa}/{max_toques}) seguindo estritamente o tom curto e direto do Eli Gentil (1 a 2 linhas, sem pedir desculpas e sem 'oi, sumiu?')."
        })

        if settings.DYNAMIC_MODEL_ROUTING:
            modelo = settings.MODEL_CLOSER_ADVANCED if (etapa_atual in [models.EtapaFunil.NEGOCIACAO, models.EtapaFunil.FECHAMENTO]) else settings.MODEL_CLOSER_FAST
        else:
            modelo = settings.MODEL_CLOSER

        logger.info(
            f"[FOLLOWUP VENDEDOR] ⏳ Gerando Toque {tentativa}/{max_toques} para {nome_validado or 'Cliente'} | "
            f"Modelo: {modelo} | Etapa: {etapa_atual.value}"
        )

        resposta = await openai_client.chat.completions.create(
            model=modelo,
            messages=mensagens,
            temperature=0.7,
            max_tokens=250
        )

        conteudo = _limpar_prefixo_timestamp(resposta.choices[0].message.content or "")
        logger.info(f"[FOLLOWUP VENDEDOR] ✉️ Mensagem gerada com sucesso ({len(conteudo)} chars)")
        return conteudo

    except Exception as e:
        if is_openai_quota_error(e):
            logger.critical(
                f"[OPENAI COTA ESGOTADA - FOLLOWUP] 🚨 Créditos da OpenAI esgotados! Silenciando follow-up: {e}"
            )
        else:
            logger.error(f"[FOLLOWUP VENDEDOR ERRO] ❌ Falha ao gerar mensagem de follow-up: {e}", exc_info=True)
        return None
