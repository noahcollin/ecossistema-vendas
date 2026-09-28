"""
Suíte de Testes Automatizados: Timeout de Inatividade Humana e Auto-Retomada da IA
==================================================================================
Valida:
1. Bloqueio correto da IA dentro da janela ativa de intervenção humana (< Timeout).
2. Auto-retomada para PILOTO_IA quando a inatividade humana ultrapassa o limite (> Timeout).
3. Auto-retomada de transbordo esquecido (TRANSBORDO_SOLICITADO sem resposta da equipe).
4. Persistência de tags, logs de auditoria e preservação de contexto no lead.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

# Adiciona o diretório backend ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
from core.config import settings
import models
from repositories.lead_repository import LeadRepository
from services.transbordo_service import TransbordoService
from services.inbound_service import InboundService

TEST_PHONE = "+5583944440001"


async def cleanup_lead(db, phone: str):
    lead = await LeadRepository.get_by_phone(db, phone)
    if lead:
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        await LeadRepository.delete_lead(db, lead)


async def test_1_janela_humana_ativa_mantem_ia_em_pausa():
    print("\n--- [1/3] Testando Janela Ativa (< 60 min): IA Permanece Silenciada ---")
    async with AsyncSessionLocal() as db:
        await cleanup_lead(db, TEST_PHONE)

        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_PHONE,
            nome="Rodrigo Janela Ativa",
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.HUMANO_ASSUMIU,
            tags=["EM_ATENDIMENTO_HUMANO"]
        )

        # Simula resposta do humano há apenas 15 minutos atrás
        momento_15m_atras = (datetime.now(timezone.utc) - timedelta(minutes=15)).replace(tzinfo=None)
        interacao_humana = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.HUMANO,
            texto="Olá Rodrigo! Já estou verificando a sua fatura de energia.",
            criado_em=momento_15m_atras
        )
        db.add(interacao_humana)
        await db.commit()

        # Executa verificação de auto-retomada
        retomou = await TransbordoService.verificar_e_executar_retomada_automatica(db, lead)

        print(f"   • Retomou IA? {retomou}")
        print(f"   • Controle Atual: {lead.controle.value}")

        assert retomou is False, "A IA NÃO deve retomar enquanto o atendente estiver dentro da janela de 60 min!"
        assert lead.controle == models.ControleAtendimento.HUMANO_ASSUMIU
        print("✅ [CENÁRIO 1 APROVADO]: IA permaneceu em silêncio para proteger o vendedor humano.")


async def test_2_timeout_expirado_reassume_piloto_ia():
    print("\n--- [2/3] Testando Timeout Expirado (> 60 min): IA Reassume Controle ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None

        # Simula resposta do humano há 85 minutos atrás (inatividade prolongada)
        momento_85m_atras = (datetime.now(timezone.utc) - timedelta(minutes=85)).replace(tzinfo=None)
        
        # Limpa interações anteriores e insere mensagem antiga do humano
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        interacao_antiga = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.HUMANO,
            texto="Oi Rodrigo, me passe o endereço que calculo o frete.",
            criado_em=momento_85m_atras
        )
        db.add(interacao_antiga)
        await db.commit()

        # O cliente envia uma nova mensagem agora
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto="O endereço é Rua das Acácias, 123. Conseguiu calcular?"
        )

        retomou = await TransbordoService.verificar_e_executar_retomada_automatica(db, lead)

        print(f"   • Retomou IA? {retomou}")
        print(f"   • Novo Controle: {lead.controle.value}")
        print(f"   • Tags: {lead.tags}")
        print(f"   • Resumo Perfil: {lead.resumo_perfil}")

        assert retomou is True, "A IA DEVE reassumir o controle após inatividade humana superior a 60 min!"
        assert lead.controle == models.ControleAtendimento.PILOTO_IA
        assert "EM_ATENDIMENTO_HUMANO" not in (lead.tags or [])
        assert "REQUER_ATENCAO" not in (lead.tags or [])

        # Verifica log de auditoria no histórico
        interacoes = await LeadRepository.get_interactions(db, lead.id)
        textos_sistema = [i.texto for i in interacoes if i.origem == models.InteracaoOrigem.SISTEMA]
        assert any("[AUTO-RETOMADA IA]" in t for t in textos_sistema), "Log de auditoria da auto-retomada deve existir!"
        print("✅ [CENÁRIO 2 APROVADO]: IA reassumiu PILOTO_IA com auditoria e remoção de tags.")


async def test_3_transbordo_solicitado_esquecido_sem_resposta():
    print("\n--- [3/3] Testando Transbordo Solicitado Esquecido Sem Resposta Humana ---")
    async with AsyncSessionLocal() as db:
        await cleanup_lead(db, TEST_PHONE)

        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_PHONE,
            nome="Mariana Sem Resposta",
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.TRANSBORDO_SOLICITADO,
            tags=["REQUER_ATENCAO", "TRANSBORDO"]
        )

        # Transbordo foi solicitado há 90 minutos e nenhum atendente respondeu
        momento_90m_atras = (datetime.now(timezone.utc) - timedelta(minutes=90)).replace(tzinfo=None)
        interacao_transbordo = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.SISTEMA,
            texto="[TRANSBORDO ACIONADO] 🚨 Atendimento escalado para a equipe humana.",
            criado_em=momento_90m_atras
        )
        db.add(interacao_transbordo)
        await db.commit()

        # Mariana manda mensagem perguntando se tem alguém
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto="Tem alguém aí para me atender?"
        )

        retomou = await TransbordoService.verificar_e_executar_retomada_automatica(db, lead)

        print(f"   • Retomou IA? {retomou}")
        print(f"   • Novo Controle: {lead.controle.value}")

        assert retomou is True, "Transbordo sem resposta humana há mais de 60 min deve ser resgatado pela IA!"
        assert lead.controle == models.ControleAtendimento.PILOTO_IA
        assert "REQUER_ATENCAO" not in (lead.tags or [])
        print("✅ [CENÁRIO 3 APROVADO]: Lead esquecido em transbordo resgatado com sucesso pela IA.")


async def main():
    print("=" * 75)
    print("🧪 SUÍTE DE TESTES: AUTO-RETOMADA POR TIMEOUT DE INATIVIDADE HUMANA")
    print("=" * 75)

    await test_1_janela_humana_ativa_mantem_ia_em_pausa()
    await test_2_timeout_expirado_reassume_piloto_ia()
    await test_3_transbordo_solicitado_esquecido_sem_resposta()

    # Limpeza final
    async with AsyncSessionLocal() as db:
        await cleanup_lead(db, TEST_PHONE)

    print("\n" + "=" * 75)
    print("🏆 TODOS OS CENÁRIOS DE AUTO-RETOMADA FORAM APROVADOS COM SUCESSO!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
