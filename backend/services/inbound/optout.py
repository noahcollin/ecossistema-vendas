"""
Guardião Determinístico de Descadastro e Conformidade LGPD (Fast-Path).
Princípio da Responsabilidade Única (SRP):
Detecta comandos semânticos de recusa e executa o opt-out sem dependência de LLM.
"""

import re
import unicodedata
from sqlalchemy.ext.asyncio import AsyncSession
from core.logger import logger
from core.protocols import WhatsAppGatewayProtocol
from repositories.lead_repository import LeadRepository
import models


class OptOutGuard:
    """
    Guardião Determinístico de Descadastro e Conformidade LGPD (Fast-Path).
    Detecta comandos semânticos de recusa e executa o opt-out sem gastar tokens de LLM.
    """

    PALAVRAS_COMANDO = {"STOP", "PARE", "SAIR", "CANCELAR", "DESCADASTRAR", "DESCADASTRO"}
    FRASES_GATILHO = [
        "NAO QUERO MAIS",
        "REMOVER MEU NUMERO",
        "TIRAR MEU NUMERO",
        "NAO ME MANDE",
        "NAO ENVIE MAIS",
        "CANCELAR MENSAGENS",
        "PARAR DE MANDAR"
    ]
    MENSAGEM_CONFIRMACAO = (
        "Entendido com certeza. Suas preferências de contato foram atualizadas "
        "e não enviaremos mais mensagens por aqui. Agradecemos a atenção e ficamos à disposição caso precise no futuro!"
    )

    @classmethod
    def verificar_comando(cls, texto: str) -> bool:
        """Detecta de forma determinística se a mensagem é uma ordem de descadastro."""
        if not texto:
            return False

        texto_limpo = (
            unicodedata.normalize("NFKD", texto)
            .encode("ASCII", "ignore")
            .decode("utf-8")
            .upper()
            .strip()
        )

        tokens = re.findall(r"\b[A-Z]+\b", texto_limpo)
        if any(token in cls.PALAVRAS_COMANDO for token in tokens):
            return True

        return any(frase in texto_limpo for frase in cls.FRASES_GATILHO)

    @classmethod
    async def executar_optout(
        cls,
        db: AsyncSession,
        lead: models.Lead,
        telefone: str,
        texto_recebido: str,
        whatsapp_gateway: WhatsAppGatewayProtocol
    ) -> None:
        """Executa a persistência de opt-out, cancela follow-ups e envia despedida."""
        from services.cadence import FollowupService

        lead.opt_out = True
        lead.desfecho = models.DesfechoLead.PERDIDO
        lead.motivo_perda = "Descadastro / Opt-out LGPD (Comando Determinístico)"
        await db.commit()

        # Salva interação do cliente
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=texto_recebido
        )

        # Cancela qualquer cadência agendada
        await FollowupService.cancelar_followups_pendentes(db, lead.id, models.StatusFollowup.ABORTADO)

        # Envia confirmação e persiste interação
        await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.IA, cls.MENSAGEM_CONFIRMACAO)
        await whatsapp_gateway.enviar_mensagem(telefone, cls.MENSAGEM_CONFIRMACAO, delay_ms=1000)
        logger.info(f"[LGPD OPT-OUT DETERMINÍSTICO] 🛑 Lead {telefone} descadastrado com sucesso.")
