from typing import Optional
from datetime import datetime, timezone
import httpx

from core.logger import logger
from core.config import settings
from integrations.uazapi import client as uazapi_service
import models
import schemas


class TransbordoNotifier:
    """
    Gateway de notificações externas para transbordo humano.
    Responsável exclusivo pela formatação de templates e despacho
    via WhatsApp (supervisor) e Webhook HTTP (sistemas externos).
    """

    @staticmethod
    def formatar_alerta_supervisor(
        lead: models.Lead,
        motivo: str,
        analise: Optional[schemas.LeadAnalysisOutput] = None
    ) -> str:
        """Formata o texto de alerta do WhatsApp com link direto wa.me."""
        tel_limpo = "".join(filter(str.isdigit, lead.telefone or ""))
        link_wa = f"https://wa.me/{tel_limpo}" if tel_limpo else "N/A"

        valor_fmt = (
            f"R$ {lead.valor_estimado:,.2f}"
            if lead.valor_estimado is not None
            else "Não informado"
        )
        nome_exibicao = lead.nome or "Não identificado"
        resumo_perfil = lead.resumo_perfil or "Sem resumo prévio registrado."
        origem = f"{lead.origem_canal or 'WHATSAPP_DIRETO'} ({getattr(lead.tipo_entrada, 'value', lead.tipo_entrada)})"

        return (
            f"🚨 *ALERTA DE TRANSBORDO HUMANO - NOVO ATENDIMENTO* 🚨\n\n"
            f"👤 *Cliente:* {nome_exibicao} ({lead.telefone})\n"
            f"📊 *Etapa:* {lead.etapa_funil.value} | *Temperatura:* {lead.temperatura.value}\n"
            f"💰 *Valor Estimado:* {valor_fmt}\n"
            f"🎯 *Origem:* {origem}\n"
            f"⚠️ *Motivo do Transbordo:* {motivo}\n\n"
            f"📝 *Resumo do Perfil:*\n"
            f"{resumo_perfil}\n\n"
            f"🔗 *Link Direto WhatsApp:*\n"
            f"{link_wa}\n\n"
            f"⚡ *Ação Necessária:*\n"
            f"Abra a conversa no WhatsApp Web ou clique no link acima para dar sequência ao atendimento."
        )

    @classmethod
    async def notificar_equipe(
        cls,
        lead: Optional[models.Lead] = None,
        motivo: str = "",
        analise: Optional[schemas.LeadAnalysisOutput] = None,
        texto_alerta: Optional[str] = None,
        dados_lead: Optional[dict] = None
    ) -> None:
        """Despacha notificações para o supervisor (WhatsApp) e webhook externo de forma assíncrona e desacoplada do ORM."""
        if not texto_alerta and lead is not None:
            try:
                texto_alerta = cls.formatar_alerta_supervisor(lead, motivo, analise)
            except Exception as e:
                logger.error(f"[NOTIFIER ERRO] Falha ao formatar alerta do supervisor: {e}")

        # 1. Envio WhatsApp ao Supervisor
        if settings.SUPERVISOR_PHONE and texto_alerta:
            try:
                res = await uazapi_service.enviar_mensagem(
                    telefone=settings.SUPERVISOR_PHONE,
                    texto=texto_alerta,
                    delay_ms=1000
                )
                logger.info(f"[NOTIFIER] 📲 Alerta enviado via WhatsApp ao supervisor: {res.get('status')}")
            except Exception as exc:
                logger.error(f"[NOTIFIER ERRO] Falha ao enviar WhatsApp ao supervisor: {exc}")
        else:
            logger.warning("[NOTIFIER] ⚠️ SUPERVISOR_PHONE não configurado. Alerta gravado em log.")

        # 2. Webhook HTTP Externo Opcional
        if settings.TRANSBORDO_WEBHOOK_URL:
            try:
                payload = {
                    "evento": "TRANSBORDO_HUMANO",
                    "lead_id": dados_lead.get("lead_id") if dados_lead else getattr(lead, "id", None),
                    "nome": dados_lead.get("nome") if dados_lead else getattr(lead, "nome", None),
                    "telefone": dados_lead.get("telefone") if dados_lead else getattr(lead, "telefone", None),
                    "etapa_funil": dados_lead.get("etapa_funil") if dados_lead else (lead.etapa_funil.value if hasattr(lead, "etapa_funil") else None),
                    "temperatura": dados_lead.get("temperatura") if dados_lead else (lead.temperatura.value if hasattr(lead, "temperatura") else None),
                    "valor_estimado": dados_lead.get("valor_estimado") if dados_lead else getattr(lead, "valor_estimado", None),
                    "motivo": motivo,
                    "resumo_perfil": dados_lead.get("resumo_perfil") if dados_lead else getattr(lead, "resumo_perfil", None),
                    "criado_em": datetime.now(timezone.utc).isoformat()
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(settings.TRANSBORDO_WEBHOOK_URL, json=payload)
                logger.info(f"[NOTIFIER] 🌐 Webhook despachado para {settings.TRANSBORDO_WEBHOOK_URL}")
            except Exception as exc:
                logger.error(f"[NOTIFIER ERRO] Falha ao despachar webhook: {exc}")
