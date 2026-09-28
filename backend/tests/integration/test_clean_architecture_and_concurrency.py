"""
Testes Automatizados de Arquitetura Limpa, Concorrência e Resiliência:
1. Validação do Script Lua Atômico no Redis (LUA_OBTER_E_LIMPAR).
2. Validação da Camada de Repositório (LeadRepository).
3. Validação da Camada de Serviço (LeadService).
4. Validação da Proteção contra Deletações Indiscriminadas (< 8 dígitos).
5. Validação do Singleton com Connection Pool do Uazapi.
"""

import asyncio
import os
import sys
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
from core.config import settings
from repositories.lead_repository import LeadRepository
from services.lead_service import LeadService
from integrations.redis import buffer as buffer_service
from integrations.uazapi.client import get_uazapi_client, close_uazapi_client
import models
import schemas

async def test_redis_lua_atomic_concurrency():
    print("\n--- [1/5] Testando Script Lua Atômico no Redis ---")
    tel_teste = "+5583988880001"
    
    # 1. Garante que o buffer está limpo
    await buffer_service.obter_e_limpar_buffer(tel_teste)
    
    # 2. Adiciona mensagens sequenciais
    t1 = await buffer_service.adicionar_mensagem(tel_teste, "Mensagem 1")
    t2 = await buffer_service.adicionar_mensagem(tel_teste, "Mensagem 2")
    t3 = await buffer_service.adicionar_mensagem(tel_teste, "Mensagem 3")
    
    assert t3 > t2 >= t1, "Tokens de tempo nanosegundos devem ser monotonicamente crescentes"
    
    # 3. Verifica debounce
    assert not await buffer_service.verificar_se_e_ultima(tel_teste, t1)
    assert not await buffer_service.verificar_se_e_ultima(tel_teste, t2)
    assert await buffer_service.verificar_se_e_ultima(tel_teste, t3)
    
    # 4. Obtém e limpa via Lua de forma atômica
    mensagens = await buffer_service.obter_e_limpar_buffer(tel_teste)
    assert mensagens == ["Mensagem 1", "Mensagem 2", "Mensagem 3"]
    
    # 5. Buffer subsequente deve estar vazio
    mensagens_vazias = await buffer_service.obter_e_limpar_buffer(tel_teste)
    assert mensagens_vazias == []
    print("✅ Script Lua atômico e debounce por nanosegundos validados com sucesso!")

async def test_lead_repository():
    print("\n--- [2/5] Testando LeadRepository ---")
    async with AsyncSessionLocal() as db:
        tel = "+5583988880002"
        # Cleanup
        existente = await LeadRepository.get_by_phone(db, tel)
        if existente:
            await LeadRepository.delete_interactions_by_lead_id(db, existente.id)
            await LeadRepository.delete_lead(db, existente)
            
        # Create
        lead = await LeadRepository.create(db, telefone=tel, nome="Cliente Repo", status=models.LeadStatus.NOVO)
        assert lead.id is not None
        assert lead.nome == "Cliente Repo"
        
        # Get by ID
        lead_por_id = await LeadRepository.get_by_id(db, lead.id)
        assert lead_por_id is not None
        assert lead_por_id.telefone == tel
        
        # Add interactions
        i1 = await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, "Olá!")
        i2 = await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.IA, "Como posso ajudar?")
        
        # Get interactions
        interacoes = await LeadRepository.get_interactions(db, lead.id)
        assert len(interacoes) == 2
        assert interacoes[0].texto == "Olá!"
        assert interacoes[1].texto == "Como posso ajudar?"
        
        # Recent interactions
        recentes = await LeadRepository.get_recent_interactions(db, lead.id, limit=1)
        assert len(recentes) == 1
        assert recentes[0].texto == "Como posso ajudar?"
        
        # Clean interactions
        deleted_count = await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        assert deleted_count == 2
        
        # Delete lead
        await LeadRepository.delete_lead(db, lead)
        assert await LeadRepository.get_by_id(db, lead.id) is None
        print("✅ LeadRepository validado com sucesso!")

async def test_lead_service_and_safety():
    print("\n--- [3/5] Testando LeadService & Proteção de Deleção ---")
    async with AsyncSessionLocal() as db:
        tel = "+5583988880003"
        
        # Limpa caso já exista de execuções anteriores
        existente = await LeadRepository.get_by_phone(db, tel)
        if existente:
            await LeadRepository.delete_interactions_by_lead_id(db, existente.id)
            await LeadRepository.delete_lead(db, existente)
        
        # 1. Criação via serviço
        lead_in = schemas.LeadCreate(nome="Lead Servico", telefone=tel, status=models.LeadStatus.QUALIFICACAO)
        lead = await LeadService.criar_lead(db, lead_in)
        assert lead.id is not None
        
        # 2. Adiciona interação e popula memória
        await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, "Tenho interesse")
        lead.resumo_perfil = "Interesse em usina solar"
        lead.dados_qualificacao = {"consumo": 500}
        await db.commit()
        
        # 3. Limpar histórico
        reset_res = await LeadService.limpar_historico_conversa(db, lead.id)
        assert reset_res["status"] == "historico_limpo"
        assert reset_res["novo_status"] == "NOVO_LEAD"
        
        lead_atualizado = await LeadRepository.get_by_id(db, lead.id)
        assert lead_atualizado.status == models.LeadStatus.NOVO
        assert lead_atualizado.resumo_perfil is None
        assert lead_atualizado.dados_qualificacao is None
        
        # 4. Proteção contra números curtos (< 8 dígitos)
        try:
            await LeadService.resetar_lead_por_telefone(db, "98")
            assert False, "Deveria ter lançado HTTPException para < 8 dígitos"
        except HTTPException as exc:
            assert exc.status_code == 400
            print("   Segurança: reset com número curto (< 8 dígitos) bloqueado com HTTP 400.")
            
        # 5. Reset completo por telefone
        reset_tel = await LeadService.resetar_lead_por_telefone(db, "988880003")
        assert reset_tel["status"] == "reset_sucesso"
        assert await LeadRepository.get_by_id(db, lead.id) is None
        print("✅ LeadService e proteções de segurança validados com sucesso!")

async def test_uazapi_connection_pool():
    print("\n--- [4/5] Testando Connection Pool do Uazapi Service ---")
    client1 = get_uazapi_client()
    client2 = get_uazapi_client()
    
    assert client1 is client2, "get_uazapi_client() deve retornar a mesma instância singleton"
    assert not client1.is_closed, "O pool de conexões HTTP deve estar aberto e ativo"
    print("✅ Singleton e Connection Pool do Uazapi validados com sucesso!")

async def test_schemas_pydantic_v2():
    print("\n--- [5/5] Testando Schemas Pydantic V2 ---")
    lead_resp = schemas.LeadResponse(
        id=1,
        telefone="+5583999999999",
        status=models.LeadStatus.NOVO,
        dados_qualificacao={"cidade": "João Pessoa", "consumo_estimado_reais": 800.0}
    )
    assert lead_resp.id == 1
    assert lead_resp.model_config.get("from_attributes") is True
    
    uazapi_msg = schemas.UazapiMessage(
        text="Olá",
        campo_customizado_uazapi="extra_value"
    )
    assert uazapi_msg.text == "Olá"
    assert getattr(uazapi_msg, "campo_customizado_uazapi") == "extra_value"
    print("✅ Schemas Pydantic V2 e ConfigDict validados com sucesso!")

async def run_all():
    print("="*70)
    print("🚀 EXECUTANDO SUÍTE COMPLETA DE ARQUITETURA LIMPA E CONCORRÊNCIA")
    print("="*70)
    await test_redis_lua_atomic_concurrency()
    await test_lead_repository()
    await test_lead_service_and_safety()
    await test_uazapi_connection_pool()
    await test_schemas_pydantic_v2()
    print("\n" + "="*70)
    print("🎉 TODAS AS 5 SUÍTES DE TESTES ARQUITETURAIS PASSARAM COM SUCESSO!")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(run_all())
