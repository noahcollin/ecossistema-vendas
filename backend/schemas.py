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

    class Config:
        from_attributes = True

# ----------------- ESQUEMAS DA UAZAPI -----------------

class UazapiChat(BaseModel):
    name: Optional[str] = None
    phone: str

class UazapiMessage(BaseModel):
    text: Optional[str] = None
    senderName: Optional[str] = None

class UazapiPayload(BaseModel):
    instanceName: str
    chat: Optional[UazapiChat] = None
    message: Optional[UazapiMessage] = None
    
    # Isso permite que o Pydantic ignore campos do Uazapi que não listamos aqui, evitando erros
    class Config:
        extra = "allow"
