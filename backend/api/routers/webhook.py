import asyncio
import json
from fastapi import APIRouter
from sqlalchemy.future import select

from core.database import AsyncSessionLocal
from core.logger import logger
import models
import schemas
from services import ai_service, uazapi_service, buffer_service, media_service

router = APIRouter(prefix="/webhook", tags=["Webhook (Uazapi)"])

# Janela de espera para agrupar mensagens picadas do cliente (em segundos)
DEBOUNCE_SECONDS = 4.5

async def processar_lote_debounce(telefone: str, nome_contato: str, timestamp_disparo: float):
    """
    Tarefa em background que aguarda a janela de digitação do cliente.
    Se o cliente mandar novas mensagens no intervalo, este timer é cancelado.
    Quando o cliente parar de digitar, processa todas as mensagens de uma vez.
    """
    try:
        # 1. Aguarda a janela de debounce (cliente digitando mensagens picadas)
        await asyncio.sleep(DEBOUNCE_SECONDS)
        
        # 2. Verifica se houve novas mensagens após esta tarefa
        eh_ultima = await buffer_service.verificar_se_e_ultima(telefone, timestamp_disparo)
        if not eh_ultima:
            logger.info(f"[DEBOUNCE] ⏳ Nova mensagem detectada para {telefone}. Descartando lote anterior.")
            return
            
        logger.info(f"[DEBOUNCE] 🚀 Cliente {telefone} parou de digitar por {DEBOUNCE_SECONDS}s. Consolidando lote completo...")
        
        # 3. Notifica o WhatsApp imediatamente com status 'digitando...'
        await uazapi_service.enviar_presenca(telefone, presenca="composing", delay_ms=30000)
        
        # 4. Retira todas as mensagens acumuladas no Redis
        mensagens_raw = await buffer_service.obter_e_limpar_buffer(telefone)
        if not mensagens_raw:
            logger.warning(f"[DEBOUNCE] Nenhuma mensagem encontrada no buffer de {telefone}")
            return
            
        # 5. Normaliza cada item do lote (visão de fotos/figurinhas ocorre AQUI, sem atrasar o debounce)
        mensagens_processadas = []
        for item in mensagens_raw:
            try:
                dados_item = json.loads(item) if (isinstance(item, str) and item.startswith("{")) else {"text": item}
                msg_obj = schemas.UazapiMessage(**dados_item)
                texto_mastigado = await media_service.normalizar_mensagem_para_texto(msg_obj)
                mensagens_processadas.append(texto_mastigado)
            except Exception as e:
                logger.error(f"[DEBOUNCE ERRO] Falha ao normalizar item: {e}")
                mensagens_processadas.append(str(item))
                
        texto_consolidado = "\n".join(mensagens_processadas)
        logger.info(f"[CLIENTE] 🗨️ Mensagem Consolidada ({len(mensagens_processadas)} partes):\n{texto_consolidado}")
        
        # 6. Persiste no Banco de Dados e Invoca a IA
        async with AsyncSessionLocal() as db:
            # Verifica ou cadastra Lead
            query = select(models.Lead).where(models.Lead.telefone == telefone)
            resultado = await db.execute(query)
            lead_existente = resultado.scalars().first()
            
            if not lead_existente:
                novo_lead = models.Lead(nome=nome_contato, telefone=telefone)
                db.add(novo_lead)
                await db.commit()
                await db.refresh(novo_lead)
                lead_existente = novo_lead
                logger.info(f"[LEAD] 🔥 Novo lead cadastrado: {nome_contato} ({telefone})")
                
            # Salva o bloco unificado de mensagens do cliente
            nova_interacao = models.Interacao(
                lead_id=lead_existente.id,
                origem=models.InteracaoOrigem.CLIENTE,
                texto=texto_consolidado
            )
            db.add(nova_interacao)
            await db.commit()
            
            # Puxa o histórico completo do Lead para a IA ler
            query_historico = select(models.Interacao).where(
                models.Interacao.lead_id == lead_existente.id
            ).order_by(models.Interacao.criado_em)
            resultado_historico = await db.execute(query_historico)
            historico_completo = resultado_historico.scalars().all()
            
            # Invoca a IA (OpenAI GPT-4o)
            resposta_ia = await ai_service.gerar_resposta_vendedor(nome_contato, historico_completo)
            
            # Salva a resposta da IA no histórico
            interacao_sistema = models.Interacao(
                lead_id=lead_existente.id,
                origem=models.InteracaoOrigem.SISTEMA,
                texto=resposta_ia
            )
            db.add(interacao_sistema)
            await db.commit()
            
            # Dispara a resposta final via Uazapi com readchat ativo
            await uazapi_service.enviar_mensagem(telefone, resposta_ia, delay_ms=2000)
            logger.info(f"[CICLO COMPLETO] ✅ Atendimento finalizado com sucesso para {telefone}")

    except Exception as e:
        logger.error(f"[DEBOUNCE ERRO] ❌ Falha crítica no processamento de {telefone}: {e}", exc_info=True)


@router.post("/uazapi")
async def webhook_uazapi(payload: schemas.UazapiPayload):
    """
    Webhook Receptivo: Enfileira mensagens recebidas no buffer Redis
    em menos de 5ms e responde 200 OK imediatamente para evitar gargalos na Uazapi.
    """
    try:
        if not payload.chat or not payload.chat.phone:
            return {"status": "ignorado", "motivo": "sem telefone"}
            
        telefone = payload.chat.phone
        nome_contato = payload.chat.name or (payload.message.senderName if payload.message else "Desconhecido")
        
        # 🛡️ TRAVA DE SEGURANÇA (MODO TESTE): Apenas o seu número recebe resposta do agente
        apenas_digitos = "".join(filter(str.isdigit, telefone))
        if not apenas_digitos.endswith("91923098"):
            logger.info(f"[SEGURANÇA] 🛑 Mensagem de {telefone} ({nome_contato}) ignorada (fora da whitelist de teste).")
            return {"status": "ignorado", "motivo": "numero_fora_da_whitelist_de_teste"}
        
        # Enfileira os dados da mensagem imediatamente no Redis (sem esperar visão ou downloads)
        dados_msg = payload.message.model_dump() if payload.message else {"text": "[Mensagem vazia]"}
        timestamp_disparo = await buffer_service.adicionar_mensagem(telefone, json.dumps(dados_msg))
        
        # Dispara background task para aguardar a janela de debounce
        asyncio.create_task(processar_lote_debounce(telefone, nome_contato, timestamp_disparo))
        
        # Responde à Uazapi em milissegundos
        return {"status": "enfileirado_com_debounce", "telefone": telefone}
        
    except Exception as e:
        logger.error(f"[WEBHOOK ERRO] ❌ Erro ao receber webhook: {e}")
        return {"status": "erro", "detalhe": str(e)}
