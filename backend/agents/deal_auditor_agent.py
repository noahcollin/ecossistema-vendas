"""
Módulo do Agente Auditor de Negócios (DealAuditorAgent).
Realiza a análise retrospectiva completa da conversa do cliente e produz
o Dossiê Executivo de Vendas (Win/Loss Analysis, O que agradou/desagradou,
dica de ouro para o atendimento humano e feedback para a empresa).
"""

import json
from typing import List, Optional
from core.openai_client import openai_client
from core.logger import logger
from core.config import settings
import models
import schemas
from .prompts import PROMPT_SISTEMA_AUDITOR

async def auditar_jornada_lead(
    lead: models.Lead,
    historico_completo: List[models.Interacao]
) -> schemas.DossieComercialOutput:
    """
    Executa a auditoria completa da jornada do lead através do GPT-4o-mini
    com Structured Outputs (garantia 100% de tipagem Pydantic V2).
    """
    try:
        # Formata o histórico cronológico de todas as mensagens
        mensagens_formatadas = []
        for interacao in historico_completo:
            remetente = "Cliente" if interacao.origem == models.InteracaoOrigem.CLIENTE else "Vendedor (IA)"
            mensagens_formatadas.append(f"{remetente}: {interacao.texto}")

        dialogo_completo = "\n".join(mensagens_formatadas) if mensagens_formatadas else "Nenhuma mensagem registrada."

        dados_qualif = lead.dados_qualificacao or {}
        resumo_atual = lead.resumo_perfil or "Sem resumo prévio."
        valor_fmt = f"R$ {lead.valor_estimado:,.2f}" if (hasattr(lead, "valor_estimado") and lead.valor_estimado is not None) else "Não informado"
        
        prompt_usuario = f"""
[DADOS ATUAIS DO CLIENTE NO BANCO]
Nome: {lead.nome or 'Não identificado'}
Telefone: {lead.telefone}
Tipo de Entrada: {lead.tipo_entrada.value if hasattr(lead, 'tipo_entrada') and lead.tipo_entrada else 'INBOUND'}
Canal de Origem: {lead.origem_canal if hasattr(lead, 'origem_canal') and lead.origem_canal else 'WHATSAPP_DIRETO'}
Etapa do Funil Atual: {lead.etapa_funil.value if hasattr(lead, 'etapa_funil') and lead.etapa_funil else 'N/A'}
Desfecho Atual: {lead.desfecho.value if hasattr(lead, 'desfecho') and lead.desfecho else 'N/A'}
Controle Atual: {lead.controle.value if hasattr(lead, 'controle') and lead.controle else 'N/A'}
Temperatura Atual: {lead.temperatura.value if hasattr(lead, 'temperatura') and lead.temperatura else 'N/A'}
Motivo de Perda Atual: {lead.motivo_perda or 'Nenhum'}
Valor Estimado do Deal: {valor_fmt}
Tags Registradas: {lead.tags or []}

[FICHA DO LEAD / MEMÓRIA ACUMULADA]
{resumo_atual}

[DADOS ESTRUTURADOS DE QUALIFICAÇÃO]
{json.dumps(dados_qualif, ensure_ascii=False)}

[HISTÓRICO COMPLETO DA CONVERSA]
{dialogo_completo}
"""

        resposta = await openai_client.beta.chat.completions.parse(
            model=settings.MODEL_ANALYZER,
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA_AUDITOR},
                {"role": "user", "content": prompt_usuario}
            ],
            response_format=schemas.DossieComercialOutput,
            temperature=0.2
        )

        dossie = resposta.choices[0].message.parsed
        if dossie is None:
            raise ValueError("OpenAI retornou dossiê nulo no parsing.")

        if not dossie.tipo_entrada:
            dossie.tipo_entrada = lead.tipo_entrada.value if hasattr(lead, 'tipo_entrada') and lead.tipo_entrada else "INBOUND"
        if not dossie.origem_canal:
            dossie.origem_canal = lead.origem_canal if hasattr(lead, 'origem_canal') and lead.origem_canal else "WHATSAPP_DIRETO"

        logger.info(
            f"[AUDITOR COMERCIAL] 📋 Dossiê gerado para {lead.telefone} ({lead.nome or 'Anônimo'}) | "
            f"Desfecho: {dossie.resultado_final.desfecho.value} | Canal: {dossie.origem_canal} | "
            f"Nota IA: {dossie.nota_atendimento_ia}/10 | Reativação: {dossie.potencial_reativacao}"
        )
        return dossie

    except Exception as e:
        logger.error(f"[AUDITOR COMERCIAL ERRO] ❌ Falha ao auditar lead {lead.telefone}: {e}", exc_info=True)
        # Fallback defensivo e resiliente
        desfecho_padrao = lead.desfecho if hasattr(lead, "desfecho") and lead.desfecho else models.DesfechoLead.EM_ANDAMENTO
        tipo_entrada_padrao = lead.tipo_entrada.value if hasattr(lead, "tipo_entrada") and lead.tipo_entrada else "INBOUND"
        origem_padrao = lead.origem_canal if hasattr(lead, "origem_canal") and lead.origem_canal else "WHATSAPP_DIRETO"
        return schemas.DossieComercialOutput(
            historia_do_lead=lead.resumo_perfil or f"Cliente {lead.telefone} em atendimento.",
            o_que_agradou=["Atendimento automatizado inicial"],
            pontos_de_atrito_e_queixas=[],
            resultado_final=schemas.DossieResultado(
                desfecho=desfecho_padrao,
                motivo_raiz=lead.motivo_perda,
                concorrente_citado=None,
                diferencial_decisivo=None
            ),
            estrategia_utilizada="Atendimento comercial padrão",
            nota_atendimento_ia=7.0,
            feedback_para_o_negocio="Manter acompanhamento com a equipe comercial.",
            proximo_passo=schemas.DossieProximoPasso(
                acao_sugerida="Verificar histórico diretamente no WhatsApp",
                quando_retomar="Em horário comercial",
                dica_de_ouro="Acolha o cliente pelo nome e entenda se restou alguma dúvida."
            ),
            potencial_reativacao="MEDIO",
            tipo_entrada=tipo_entrada_padrao,
            origem_canal=origem_padrao
        )
