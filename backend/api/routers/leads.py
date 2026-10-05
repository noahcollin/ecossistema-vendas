from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from core.database import get_db
from services.lead_service import LeadService
from services.transbordo_service import TransbordoService
from services.followup_service import FollowupService
import schemas

router = APIRouter(prefix="/leads", tags=["Leads"])

@router.get("/transbordo/pendentes", response_model=List[schemas.LeadResponse])
async def listar_leads_em_transbordo(db: AsyncSession = Depends(get_db)):
    """Lista todos os leads que estão aguardando intervenção ou em atendimento humano."""
    return await TransbordoService.listar_pendentes(db)

@router.post("/{lead_id}/transbordo/assumir", response_model=schemas.LeadResponse)
async def assumir_transbordo(
    lead_id: int,
    body: schemas.TransbordoAssumirRequest = schemas.TransbordoAssumirRequest(),
    db: AsyncSession = Depends(get_db)
):
    """
    O atendente humano assume a condução direta da conversa:
    - Atualiza controle para HUMANO_ASSUMIU;
    - Mantém a IA 100% silenciada;
    - Cancela quaisquer follow-ups automáticos.
    """
    return await TransbordoService.assumir_atendimento(db, lead_id, body.atendente or "Especialista")

@router.post("/{lead_id}/transbordo/devolver", response_model=schemas.LeadResponse)
async def devolver_transbordo(
    lead_id: int,
    body: schemas.TransbordoDevolverRequest = schemas.TransbordoDevolverRequest(),
    db: AsyncSession = Depends(get_db)
):
    """
    O atendente humano conclui o atendimento e devolve o controle para a IA:
    - Atualiza controle para PILOTO_IA;
    - Registra opcionalmente uma diretriz de equipe para orientar a IA;
    - Opcionalmente atualiza etapa_funil e valor_estimado corrigidos pelo atendente;
    - A IA volta a responder na próxima interação do cliente.
    """
    return await TransbordoService.devolver_para_ia(
        db,
        lead_id,
        diretriz_ia=body.diretriz_ia,
        etapa_sugerida=body.etapa_sugerida,
        valor_estimado=body.valor_estimado
    )

@router.post("/{lead_id}/transbordo/solicitar", response_model=schemas.LeadResponse)
async def solicitar_transbordo_manual(
    lead_id: int,
    body: schemas.TransbordoSolicitarRequest = schemas.TransbordoSolicitarRequest(),
    db: AsyncSession = Depends(get_db)
):
    """Aciona transbordo humano manual sob demanda diretamente do painel/CRM."""
    return await TransbordoService.solicitar_transbordo_manual(db, lead_id, motivo=body.motivo)

@router.post("/{lead_id}/transbordo/mensagem", response_model=schemas.MensagemHumanaResponse)
async def enviar_mensagem_humana(
    lead_id: int,
    body: schemas.MensagemHumanaManualRequest,
    db: AsyncSession = Depends(get_db)
):
    """Envia uma mensagem humana através do Dashboard e grava como InteracaoOrigem.HUMANO."""
    interacao = await TransbordoService.enviar_mensagem_humana_painel(
        db, lead_id, body.texto, body.atendente or "Atendente"
    )
    return {
        "status": "enviado",
        "interacao_id": interacao.id,
        "origem": interacao.origem.value,
        "texto": interacao.texto,
        "data": interacao.criado_em.isoformat()
    }

@router.post("/", response_model=schemas.LeadResponse, status_code=status.HTTP_201_CREATED)
async def criar_lead(lead: schemas.LeadCreate, db: AsyncSession = Depends(get_db)):
    """Cria um novo cliente (Lead) manualmente."""
    return await LeadService.criar_lead(db, lead)

@router.get("/", response_model=List[schemas.LeadResponse])
async def listar_leads(db: AsyncSession = Depends(get_db)):
    """Lista todos os clientes (Leads) cadastrados."""
    return await LeadService.listar_leads(db)

@router.get("/{lead_id}", response_model=schemas.LeadResponse)
async def obter_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Recupera os detalhes de um Lead específico pelo seu ID."""
    return await LeadService.obter_lead(db, lead_id)

@router.delete("/{lead_id}", status_code=204)
async def deletar_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Deleta um Lead e todo o seu histórico de mensagens do banco de dados (exclusão em cascata).
    """
    await LeadService.deletar_lead(db, lead_id)
    return

@router.delete("/{lead_id}/interacoes", status_code=200)
async def limpar_historico_conversa(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Apaga apenas as mensagens trocadas com o Lead, mantendo o cadastro do cliente.
    Útil para fazer a IA 'esquecer' a conversa e reiniciar um diálogo do zero.
    """
    return await LeadService.limpar_historico_conversa(db, lead_id)

@router.delete("/reset/por-telefone/{telefone}", status_code=200)
async def resetar_lead_por_telefone(telefone: str, db: AsyncSession = Depends(get_db)):
    """
    Busca o lead pelo número de telefone (mínimo de 8 dígitos)
    e deleta tanto o cadastro quanto todo o histórico de mensagens e buffers.
    """
    return await LeadService.resetar_lead_por_telefone(db, telefone)

@router.get("/{lead_id}/interacoes", response_model=List[schemas.InteracaoResponse])
async def listar_interacoes(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Lista o histórico de conversas (Interações) de um cliente."""
    return await LeadService.listar_interacoes(db, lead_id)

@router.post("/{lead_id}/auditar", response_model=schemas.LeadResponse)
async def auditar_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Aciona o Agente Auditor de Negócios (DealAuditorAgent) para gerar
    o Dossiê Comercial Executivo completo do lead sob demanda.
    """
    return await LeadService.gerar_dossie_lead(db, lead_id)

@router.get("/{lead_id}/followups", response_model=List[schemas.FollowupAgendadoResponse])
async def listar_followups_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Lista todos os agendamentos de follow-up (cadência temporal) do lead."""
    return await FollowupService.listar_por_lead(db, lead_id)


