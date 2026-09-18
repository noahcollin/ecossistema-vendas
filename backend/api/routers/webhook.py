import asyncio
import json
from fastapi import APIRouter, Header, Query, HTTPException, status, Depends

from core.database import AsyncSessionLocal
from core.logger import logger
from core.config import settings
from core.utils import higienizar_nome_perfil, normalizar_telefone
from repositories.lead_repository import LeadRepository
from services.lead_service import LeadService
import models
import schemas
from services import ai_service, uazapi_service, buffer_service, media_service, agents

router = APIRouter(prefix="/webhook", tags=["Webhook (Uazapi)"])

# Janela de espera para agrupar mensagens picadas do cliente (em segundos)
DEBOUNCE_SECONDS = settings.DEBOUNCE_SECONDS

# Semáforo Global de Concorrência de IA (Proteção contra Thundering Herd / Rate Limits)
SEMAFORO_CONCORRENCIA_IA = asyncio.Semaphore(settings.CONCURRENCY_SEMAPHORE_LIMIT)

async def validar_webhook_secret(
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
    secret: str | None = Query(None)
):
    """
    Valida a autenticidade da requisição do webhook.
    Se WEBHOOK_SECRET_TOKEN estiver configurado no .env, exige o segredo correspondente.
    Se não configurado (vazio), permite a requisição mantendo compatibilidade de testes/desenvolvimento.
    """
    if settings.WEBHOOK_SECRET_TOKEN:
        token_fornecido = x_webhook_secret or secret
        if not token_fornecido or token_fornecido != settings.WEBHOOK_SECRET_TOKEN:
            logger.warning("[SEGURANÇA WEBHOOK] 🛑 Acesso não autorizado ao webhook: token inválido ou ausente.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Acesso não autorizado: Token secreto do webhook inválido ou ausente."
            )

async def disparar_auditoria_background(lead_id: int):
    """
    Executa a auditoria em background sem bloquear o fluxo do webhook nem o WhatsApp.
    """
    try:
        async with AsyncSessionLocal() as bg_db:
            await LeadService.gerar_dossie_lead(bg_db, lead_id)
    except Exception as exc:
        logger.error(f"[AUDITOR BACKGROUND ERRO] Falha ao gerar dossiê em background para Lead ID {lead_id}: {exc}")


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
        
        # 3. Retira todas as mensagens acumuladas no Redis
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
                if texto_mastigado and texto_mastigado.strip():
                    mensagens_processadas.append(texto_mastigado.strip())
            except Exception as e:
                logger.error(f"[DEBOUNCE ERRO] Falha ao normalizar item: {e}")
                if str(item).strip():
                    mensagens_processadas.append(str(item).strip())
                
        if not mensagens_processadas:
            logger.info(f"[DEBOUNCE] Nenhuma mensagem válida com conteúdo para processar de {telefone}")
            return

        texto_consolidado = "\n".join(mensagens_processadas)
        
        # 🛡️ Proteção contra estouro de contexto e payloads gigantescos
        if len(texto_consolidado) > 8000:
            logger.warning(f"[PAYLOAD GIGANTE] Mensagem de {telefone} truncada de {len(texto_consolidado)} para 8000 caracteres.")
            texto_consolidado = texto_consolidado[:8000] + "\n[... texto truncado por exceder o limite de segurança ...]"

        logger.info(f"[CLIENTE] 🗨️ Mensagem Consolidada ({len(mensagens_processadas)} partes):\n{texto_consolidado}")
        
        # 6. Persiste no Banco de Dados e Invoca a IA
        async with AsyncSessionLocal() as db:
            # Verifica ou cadastra Lead
            lead_existente = await LeadRepository.get_by_phone(db, telefone)
            
            nome_validado = higienizar_nome_perfil(nome_contato)
            nome_salvar = nome_validado or (nome_contato if nome_contato != "Desconhecido" else None)

            if not lead_existente:
                lead_existente = await LeadRepository.create(
                    db=db,
                    telefone=telefone,
                    nome=nome_salvar,
                    tipo_entrada=models.TipoEntradaLead.INBOUND,
                    origem_canal="WHATSAPP_DIRETO",
                    etapa_funil=models.EtapaFunil.NOVO_CONTATO,
                    desfecho=models.DesfechoLead.EM_ANDAMENTO,
                    controle=models.ControleAtendimento.PILOTO_IA,
                    temperatura=models.TemperaturaLead.FRIO
                )
                logger.info(f"[LEAD NOVO] ✨ Novo lead cadastrado: {telefone} ({nome_salvar or 'Sem nome'}) | Entrada: INBOUND | Etapa: NOVO_CONTATO")
            else:
                # Atualiza o nome do lead se antes estava desconhecido e agora temos um válido
                if nome_validado and (not lead_existente.nome or lead_existente.nome == "Desconhecido"):
                    lead_existente.nome = nome_validado
                    await db.commit()
                    logger.info(f"[LEAD NOME] 🏷️ Nome do lead atualizado no banco: {nome_validado}")

            # 🛡️ TRAVA LGPD: Se o cliente já solicitou opt-out, ignora qualquer envio futuro
            if lead_existente.opt_out:
                logger.info(f"[LGPD OPT-OUT] 🛑 Mensagem de {telefone} ignorada pois o cliente está descadastrado.")
                return

            # Salva o bloco unificado de mensagens do cliente
            await LeadRepository.add_interaction(
                db=db,
                lead_id=lead_existente.id,
                origem=models.InteracaoOrigem.CLIENTE,
                texto=texto_consolidado
            )

            # 🛡️ TRAVA TRANSBORDO: Se o atendimento já foi passado para humano, a IA não responde
            if lead_existente.controle in [models.ControleAtendimento.TRANSBORDO_SOLICITADO, models.ControleAtendimento.HUMANO_ASSUMIU]:
                logger.info(f"[TRANSBORDO HUMANO ATIVO] 👤 Mensagem de {telefone} arquivada. IA em pausa para atendimento humano ({lead_existente.controle.value}).")
                return

            # Notifica o WhatsApp com status 'digitando...' apenas se o lead for atendido pela IA
            await uazapi_service.enviar_presenca(telefone, presenca="composing", delay_ms=25000)
            
            # Puxa apenas a janela configurada das mensagens imediatas mais recentes
            historico_recente = await LeadRepository.get_recent_interactions(
                db=db,
                lead_id=lead_existente.id,
                limit=settings.JANELA_HISTORICO_RECENTE
            )
            
            # 🧠 Execução dos Agentes protegida pelo Semáforo de Concorrência Global
            async with SEMAFORO_CONCORRENCIA_IA:
                # 🧠 AGENTE 1: Analista de Inteligência Comercial (gpt-4o-mini)
                # Avalia a conversa e classifica as 4 Dimensões de Vendas com Structured Outputs
                analise = await agents.analisar_lead_e_fsm(
                    lead=lead_existente,
                    historico_recente=historico_recente,
                    nova_mensagem=texto_consolidado
                )

                # 🛑 TRATAMENTO DE OPT-OUT DETECTADO
                if analise.opt_out_detectado:
                    lead_existente.opt_out = True
                    lead_existente.desfecho = models.DesfechoLead.PERDIDO
                    lead_existente.motivo_perda = "Descadastro / Opt-out LGPD"
                    await db.commit()

                    resposta_despedida = "Entendido com certeza. Suas preferências de contato foram atualizadas e não enviaremos mais mensagens por aqui. Agradecemos a atenção e ficamos à disposição caso precise no futuro!"
                    await LeadRepository.add_interaction(db, lead_existente.id, models.InteracaoOrigem.IA, resposta_despedida)
                    await uazapi_service.enviar_mensagem(telefone, resposta_despedida, delay_ms=1000)
                    logger.info(f"[LGPD OPT-OUT] 🛑 Lead {telefone} descadastrado com sucesso. Atendimento finalizado.")
                    return

                # 🚨 TRATAMENTO DE TRANSBORDO HUMANO
                if analise.transbordo_sugerido:
                    lead_existente.controle = models.ControleAtendimento.TRANSBORDO_SOLICITADO
                    logger.warning(
                        f"[TRANSBORDO ACIONADO] 🚨 Lead {telefone} entrou em transbordo humano! "
                        f"Justificativa: {analise.justificativa}"
                    )
                
                # Atualiza canal de origem se identificado pela IA e se o canal atual for padrão
                if analise.origem_canal_detectada:
                    if not lead_existente.origem_canal or lead_existente.origem_canal == "WHATSAPP_DIRETO":
                        lead_existente.origem_canal = analise.origem_canal_detectada
                        logger.info(f"[CANAL IDENTIFICADO] 🎯 Origem do lead {telefone} atualizada para: {analise.origem_canal_detectada}")

                # Atualiza e persiste as 4 Dimensões de Vendas
                lead_existente.etapa_funil = analise.etapa_sugerida
                lead_existente.desfecho = analise.desfecho_sugerido
                lead_existente.temperatura = analise.temperatura_sugerida
                lead_existente.resumo_perfil = analise.resumo_perfil
                lead_existente.dados_qualificacao = (
                    analise.dados_qualificacao.model_dump()
                    if hasattr(analise.dados_qualificacao, "model_dump")
                    else analise.dados_qualificacao
                )
                if analise.motivo_perda:
                    lead_existente.motivo_perda = analise.motivo_perda
                if analise.valor_estimado is not None:
                    lead_existente.valor_estimado = analise.valor_estimado
                if analise.tags_sugeridas:
                    tags_atuais = set(lead_existente.tags or [])
                    tags_atuais.update(analise.tags_sugeridas)
                    lead_existente.tags = list(tags_atuais)

                await db.commit()

                # 🔍 DISPARO DA AUDITORIA EXECUTIVA EM SEGUNDO PLANO
                # Se entrou em transbordo ou encerrou a oportunidade (GANHO/PERDIDO), audita a história completa
                precisa_auditoria = (
                    analise.transbordo_sugerido or
                    analise.desfecho_sugerido in [models.DesfechoLead.GANHO, models.DesfechoLead.PERDIDO]
                )
                if precisa_auditoria:
                    asyncio.create_task(disparar_auditoria_background(lead_existente.id))
                
                # 📋 LOG DA FICHA MULTIDIMENSIONAL (ENVIADA DO ANALYZER PARA O CLOSER)
                valor_fmt = f"R$ {lead_existente.valor_estimado:,.2f}" if lead_existente.valor_estimado else "Não informado"
                logger.info(
                    f"\n{'='*60}\n"
                    f"📋 [ANALYZER ➔ CLOSER] FICHA MULTIDIMENSIONAL DO LEAD:\n"
                    f"• Cliente: {lead_existente.nome or 'Anônimo'} ({telefone})\n"
                    f"• Etapa do Funil: {lead_existente.etapa_funil.value}\n"
                    f"• Desfecho: {lead_existente.desfecho.value}\n"
                    f"• Controle: {lead_existente.controle.value}\n"
                    f"• Temperatura: {lead_existente.temperatura.value}\n"
                    f"• Valor Estimado: {valor_fmt}\n"
                    f"• Tags: {lead_existente.tags}\n"
                    f"• Motivo Perda: {lead_existente.motivo_perda or 'Nenhum'}\n"
                    f"• Ficha / Resumo do Perfil:\n{lead_existente.resumo_perfil}\n"
                    f"• Dados Estruturados (JSON): {lead_existente.dados_qualificacao}\n"
                    f"{'='*60}"
                )
                
                # 🤖 AGENTE 2: Vendedor Consultivo 'Seu Zé' (Com FinOps / Roteamento Dinâmico)
                # Recebe a Ficha do Lead + Etapa do Funil + Contexto Imediato
                nome_ia = lead_existente.nome or nome_contato
                resposta_ia = await agents.gerar_resposta_vendedor(
                    nome_cliente_bruto=nome_ia,
                    ficha_resumo=lead_existente.resumo_perfil,
                    etapa_funil=lead_existente.etapa_funil,
                    historico_recente=historico_recente
                )
                
                # Salva a resposta da IA no histórico com a origem correta IA
                await LeadRepository.add_interaction(
                    db=db,
                    lead_id=lead_existente.id,
                    origem=models.InteracaoOrigem.IA,
                    texto=resposta_ia
                )

                # Dispara a resposta final via Uazapi com readchat ativo
                await uazapi_service.enviar_mensagem(telefone, resposta_ia, delay_ms=2000)
                logger.info(f"[CICLO COMPLETO] ✅ Atendimento finalizado com sucesso para {telefone} (Etapa: {lead_existente.etapa_funil.value} | Desfecho: {lead_existente.desfecho.value})")

    except Exception as e:
        logger.error(f"[DEBOUNCE ERRO] ❌ Falha crítica no processamento de {telefone}: {e}", exc_info=True)



@router.post("/uazapi", dependencies=[Depends(validar_webhook_secret)])
@router.post("/whatsapp", dependencies=[Depends(validar_webhook_secret)])
async def webhook_uazapi(payload: schemas.UazapiPayload):
    """
    Webhook Receptivo: Enfileira mensagens recebidas no buffer Redis
    em menos de 5ms e responde 200 OK imediatamente para evitar gargalos na Uazapi.
    Aplica guardas contra loops infinitos (fromMe), grupos (@g.us) e ACKs fantasmas.
    """
    try:
        if not payload.chat or not payload.chat.phone:
            return {"status": "ignorado", "motivo": "sem_telefone"}
            
        telefone_raw = payload.chat.phone

        # 🛑 1. GUARDA ANTI-GRUPO: Ignora qualquer mensagem vinda de grupos do WhatsApp
        if (
            "@g.us" in telefone_raw
            or getattr(payload.chat, "isGroup", False)
            or (payload.message and getattr(payload.message, "isGroup", False))
        ):
            logger.info(f"[WEBHOOK] 🛑 Mensagem de grupo ignorada ({telefone_raw}).")
            return {"status": "ignorado", "motivo": "mensagem_de_grupo"}

        # 🛑 2. GUARDA ANTI-LOOP INFINITO: Ignora mensagens enviadas pelo próprio bot/instância
        if payload.message and getattr(payload.message, "fromMe", False):
            logger.debug(f"[WEBHOOK] 🔄 Mensagem própria ignorada (fromMe=True).")
            return {"status": "ignorado", "motivo": "mensagem_do_proprio_bot"}

        # 🛑 3. GUARDA DE EVENTOS FANTASMAS / ACKs VAZIOS
        if not payload.message:
            return {"status": "ignorado", "motivo": "evento_sem_mensagem"}

        tem_texto = bool(payload.message.text and payload.message.text.strip())
        tem_midia = bool(payload.message.fileURL or payload.message.messageType or payload.message.content)
        if not tem_texto and not tem_midia:
            return {"status": "ignorado", "motivo": "conteudo_vazio"}

        # Normaliza o telefone para formato canônico (+55...)
        telefone = normalizar_telefone(telefone_raw)
        if not telefone or len("".join(filter(str.isdigit, telefone))) < 8:
            return {"status": "ignorado", "motivo": "telefone_invalido"}

        nome_contato = payload.chat.name or (payload.message.senderName if payload.message else "Desconhecido")
        
        # 🛡️ TRAVA DE SEGURANÇA: Se em modo sandbox, apenas o número da whitelist recebe resposta do agente
        if settings.SANDBOX_MODE:
            apenas_digitos = "".join(filter(str.isdigit, telefone))
            if not apenas_digitos.endswith(settings.WHITELIST_PHONE_SUFFIX):
                logger.info(f"[SEGURANÇA] 🛑 Mensagem de {telefone} ({nome_contato}) ignorada (fora da whitelist de teste).")
                return {"status": "ignorado", "motivo": "numero_fora_da_whitelist_de_teste"}
        
        # Enfileira os dados da mensagem imediatamente no Redis (sem esperar visão ou downloads)
        dados_msg = payload.message.model_dump()
        timestamp_disparo = await buffer_service.adicionar_mensagem(telefone, json.dumps(dados_msg))
        
        # Dispara background task para aguardar a janela de debounce
        asyncio.create_task(processar_lote_debounce(telefone, nome_contato, timestamp_disparo))
        
        # Responde à Uazapi em milissegundos
        return {"status": "enfileirado_com_debounce", "telefone": telefone}
        
    except Exception as e:
        logger.error(f"[WEBHOOK ERRO] ❌ Erro ao receber webhook: {e}")
        return {"status": "erro", "detalhe": str(e)}
