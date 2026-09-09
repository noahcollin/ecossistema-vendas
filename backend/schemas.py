from pydantic import BaseModel
from typing import Optional
from models import LeadStatus

# Esquema para quando o cliente nos envia dados (não exigimos ID, é automático)
class LeadCreate(BaseModel):
    nome: Optional[str] = None
    telefone: str

# Esquema para quando devolvemos os dados pro cliente (inclui tudo, até a data)
class LeadResponse(BaseModel):
    id: int
    nome: Optional[str]
    telefone: str
    status: LeadStatus

    # Isso permite que o Pydantic entenda diretamente o formato que vem do Banco de Dados
    class Config:
        from_attributes = True
