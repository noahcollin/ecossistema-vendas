from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import logger
from repositories.lead_repository import LeadRepository
from integrations.redis import buffer as buffer_service
import agents
import models
import schemas
from services.followup_service import FollowupService

class LeadService:
    """
    Camada de serviço de negócio para gerenciamento de Leads e suas interações.
    Orquestra regras de negócio, repositório de dados e limpeza de buffers em cache.
    """

    @staticmethod
    async def criar_lead(db: AsyncSession, lead_in: schemas.LeadCreate) -> models.Lead:
        """Cria um novo lead manualmente."""
        novo_lead = await LeadRepository.create(
            db=db,
            nome=lead_in.nome,
            telefone=lead_in.telefone,
            tipo_entrada=lead_in.tipo_entrada,
            origem_canal=lead_in.origem_canal,
            etapa_funil=lead_in.etapa_funil,
            desfecho=lead_in.desfecho,
            valor_estimado=lead_in.valor_estimado
        )
        logger.info(f"[LEADS SERVICE] Lead criado: {novo_lead.nome} ({novo_lead.telefone})")
        return novo_lead

    @staticmethod
    async def listar_leads(db: AsyncSession) -> List[models.Lead]:
        """Recupera todos os leads cadastrados."""
        return await LeadRepository.list_all(db)

    @staticmethod
    async def deletar_lead(db: AsyncSession, lead_id: int) -> None:
        """
        Deleta um Lead e todo o seu histórico de mensagens do banco de dados (exclusão em cascata)
        e limpa seu buffer pendente no Redis.
        """
        lead = await LeadRepository.get_by_id(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        tel = lead.telefone
        await LeadRepository.delete_interactions_by_lead_id(db, lead_id)
        await LeadRepository.delete_lead(db, lead)
        await buffer_service.obter_e_limpar_buffer(tel)

        logger.info(f"[LEADS SERVICE] 🗑️ Lead e histórico apagados com sucesso (ID: {lead_id}, Tel: {tel})")

    @staticmethod
    async def limpar_historico_conversa(db: AsyncSession, lead_id: int) -> Dict[str, Any]:
        """
        Apaga as mensagens trocadas com o Lead, reiniciando para NOVO_CONTATO
        e zerando memórias de longo prazo (resumo_perfil, dados_qualificacao, tags, motivo_perda).
        """
        lead = await LeadRepository.get_by_id(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead não encontrado")

        await LeadRepository.delete_interactions_by_lead_id(db, lead_id)
        
        # 🛑 Cancela follow-ups agendados da conversa anterior para evitar disparos zumbis
        await FollowupService.cancelar_followups_pendentes(db, lead_id, models.StatusFollowup.ABORTADO)

        lead.etapa_funil = models.EtapaFunil.NOVO_CONTATO
        lead.desfecho = models.DesfechoLead.EM_ANDAMENTO
        lead.controle = models.ControleAtendimento.PILOTO_IA
        lead.temperatura = models.TemperaturaLead.FRIO
        lead.motivo_perda = None
        lead.valor_estimado = None
        lead.tags = []
        lead.opt_out = False
        lead.resumo_perfil = None
        lead.dados_qualificacao = None
        lead.dossie_comercial = None
        await db.commit()

        await buffer_service.obter_e_limpar_buffer(lead.telefone)

        logger.info(
            f"[LEADS SERVICE] 🧹 Histórico de conversa e memória de longo prazo limpos para Lead ID {lead_id} ({lead.telefone})"
        )
        return {
            "status": "historico_limpo",
            "lead_id": lead_id,
            "etapa_funil": models.EtapaFunil.NOVO_CONTATO.value,
            "desfecho": models.DesfechoLead.EM_ANDAMENTO.value,
            "memoria_resetada": True
        }


    @staticmethod
    async def resetar_lead_por_telefone(db: AsyncSession, telefone: str) -> Dict[str, Any]:
        """
        Busca o lead pelo número de telefone de forma segura (>= 8 dígitos)
        e executa reset completo: apaga interações, cadastro e buffer residual no Redis.
        """
        digitos = "".join(filter(str.isdigit, telefone))
        if len(digitos) < 8:
            raise HTTPException(
                status_code=400,
                detail="O número para reset deve conter no mínimo 8 dígitos para evitar exclusões acidentais ou ambíguas."
            )

        lead = await LeadRepository.find_by_phone_digits(db, telefone, digitos)
        if not lead:
            await buffer_service.obter_e_limpar_buffer(telefone)
            return {"status": "lead_nao_existia", "telefone": telefone}

        lead_id = lead.id
        tel_completo = lead.telefone

        await LeadRepository.delete_interactions_by_lead_id(db, lead_id)
        await LeadRepository.delete_lead(db, lead)
        await buffer_service.obter_e_limpar_buffer(tel_completo)

        logger.info(f"[LEADS SERVICE] 💥 Reset completo realizado para o número {tel_completo} (Lead ID: {lead_id})")
        return {"status": "reset_sucesso", "lead_id": lead_id, "telefone": tel_completo}

    @staticmethod
    async def listar_interacoes(db: AsyncSession, lead_id: int) -> List[Dict[str, Any]]:
        """Lista o histórico de mensagens ordenado cronologicamente."""
        interacoes = await LeadRepository.get_interactions(db, lead_id)
        return [
            {
                "id": i.id,
                "origem": i.origem.value,
                "texto": i.texto,
                "data": i.criado_em.isoformat()
            }
            for i in interacoes
        ]

    @staticmethod
    async def gerar_dossie_lead(db: AsyncSession, lead_id: int) -> models.Lead:
        """
        Executa a auditoria retrospectiva completa da jornada do Lead através do
        DealAuditorAgent e persiste o Dossiê Comercial estruturado no banco de dados.
        """
        lead = await LeadRepository.get_by_id(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead não encontrado para geração de dossiê.")

        interacoes = await LeadRepository.get_interactions(db, lead_id)
        dossie = await agents.auditar_jornada_lead(lead, interacoes)

        dossie_dict = dossie.model_dump() if hasattr(dossie, "model_dump") else dict(dossie)
        lead_atualizado = await LeadRepository.salvar_dossie(db, lead, dossie_dict)
        logger.info(f"[LEADS SERVICE] 📋 Dossiê Comercial gerado e salvo para Lead ID {lead_id} ({lead.telefone})")
        return lead_atualizado

