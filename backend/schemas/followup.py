"""
Esquemas Pydantic para o Motor de Cadência e Follow-Up.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from models import EtapaFunil, StatusFollowup


class FollowupAgendadoResponse(BaseModel):
    """Serialização de agendamento de follow-up."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    etapa_funil: EtapaFunil
    tentativa: int
    agendado_para: datetime
    status: StatusFollowup
    mensagem_disparada: Optional[str] = None
    criado_em: Optional[datetime] = None
    atualizado_em: Optional[datetime] = None
