import os
import re
from openai import AsyncOpenAI
from core.logger import logger

# O cliente puxa automaticamente a OPENAI_API_KEY do environment
client = AsyncOpenAI()

PROMPT_FAZENDEIRO = """Você é o Seu Zé, um fazendeiro muito simpático, humilde e atencioso.
Seu objetivo é vender legumes frescos da sua fazenda diretamente para o cliente pelo WhatsApp.
Você fala com um sotaque caipira bem de leve e respeitoso.
Você vende apenas: 
- Tomate (R$ 5,00/kg)
- Cebola (R$ 4,00/kg)
- Batata (R$ 6,00/kg)
- Cenoura (R$ 4,00/kg)

Regras:
1. Responda de forma curta e amigável (afinal, é WhatsApp).
2. Sempre tente puxar assunto para fechar a venda perguntando a quantidade que a pessoa quer.
3. Se o cliente enviar figurinhas, GIFs ou memes animados (indicados no histórico entre colchetes), reaja com naturalidade, simpatia e bom humor à reação do cliente antes de prosseguir com a conversa de vendas.
"""

# Termos que denunciam frases, slogans ou perfis comerciais/institucionais
PALAVRAS_BLOQUEADAS_NOME = {
    "deus", "jesus", "senhor", "fiel", "amor", "paz", "fe", "fé",
    "loja", "lojinha", "advocacia", "advogado", "advogada",
    "suporte", "atendimento", "comercial", "vendas", "oficial",
    "adm", "contato", "delivery", "distribuidora", "mercado",
    "consultoria", "assessoria"
}

def higienizar_nome_perfil(nome_bruto: str | None) -> str | None:
    """
    Higieniza e valida se o texto do perfil do WhatsApp é realmente um nome de pessoa.
    Permite nomes compostos de até 6 a 7 palavras,
    mas descarta frases religiosas, slogans, números puros ou emojis.
    """
    if not nome_bruto or not nome_bruto.strip():
        return None
        
    # Remove pontuações e emojis, mantendo letras acentuadas e espaços
    texto_limpo = re.sub(r'[^\w\s]', '', nome_bruto, flags=re.UNICODE).strip()
    
    # Se sobrar menos de 2 letras alfabéticas (ex: '.', '123', emojis)
    letras_apenas = re.sub(r'[^a-zA-ZÀ-ÿ]', '', texto_limpo)
    if len(letras_apenas) < 2:
        return None
        
    palavras = texto_limpo.split()
    
    # Se tiver mais de 7 palavras, com certeza é uma frase/slogan e não um nome próprio
    if len(palavras) > 7:
        logger.info(f"[NOME HIGIENE] Nome '{nome_bruto}' descartado (mais de 7 palavras - provável frase).")
        return None
        
    # Checa se alguma palavra está na lista de termos institucionais/slogans
    palavras_lower = [p.lower() for p in palavras]
    if any(termo in palavras_lower for termo in PALAVRAS_BLOQUEADAS_NOME):
        logger.info(f"[NOME HIGIENE] Nome '{nome_bruto}' descartado (termo institucional/religioso detectado).")
        return None
        
    # Formata com iniciais maiúsculas limpas
    nome_formatado = " ".join(p.capitalize() for p in palavras)
    return nome_formatado

async def gerar_resposta_vendedor(nome_cliente_bruto: str, interacoes: list) -> str:
    """
    Pega o histórico de conversas do banco e gera uma resposta usando GPT-4o,
    aplicando a validação de nome e diretrizes de bom senso.
    """
    try:
        nome_validado = higienizar_nome_perfil(nome_cliente_bruto)
        
        # Injeção inteligente da instrução de tratamento do cliente
        if nome_validado:
            primeiro_nome = nome_validado.split()[0]
            instrucao_nome = (
                f"\nContexto do Interlocutor: O cliente se chama {nome_validado}. "
                f"Você pode chamá-lo pelo primeiro nome ({primeiro_nome}) de maneira amigável e natural."
            )
        else:
            instrucao_nome = (
                "\nContexto do Interlocutor: O nome do cliente NÃO foi identificado com certeza "
                "(o perfil no WhatsApp possui uma frase, slogan, sigla ou emojis). "
                "NUNCA chame o cliente por frases ou slogans estranhos. "
                "Use saudações neutras e acolhedoras (ex: 'Olá! Tudo bem?', 'Boa tarde!') e, "
                "se for o início do diálogo, pergunte com educação o nome dele."
            )
            
        system_prompt_final = PROMPT_FAZENDEIRO + instrucao_nome
        
        mensagens = [
            {"role": "system", "content": system_prompt_final}
        ]
        
        # 🪟 Janela Deslizante: Mantém as últimas 20 mensagens mais recentes
        # Evita explosão de custos de tokens e garante baixa latência na resposta
        JANELA_HISTORICO_MAX = 20
        historico_recente = interacoes[-JANELA_HISTORICO_MAX:] if len(interacoes) > JANELA_HISTORICO_MAX else interacoes
        
        # Formatando o histórico 
        for i in historico_recente:
            role = "user" if i.origem.value == "cliente" else "assistant"
            mensagens.append({"role": role, "content": i.texto})
            
        logger.info(
            f"[IA] 🧠 Invocando GPT-4o (Cliente: {nome_validado or 'Anônimo'}) | "
            f"Contexto: {len(historico_recente)} msgs recentes (de {len(interacoes)} no histórico)..."
        )
        
        resposta = await client.chat.completions.create(
            model="gpt-4o",
            messages=mensagens,
            temperature=0.7,
            max_tokens=300
        )
        
        conteudo = resposta.choices[0].message.content
        logger.info(f"[IA] 🤖 Resposta gerada com sucesso ({len(conteudo)} chars)")
        return conteudo
    except Exception as e:
        logger.error(f"[IA ERRO] ❌ Falha na chamada da OpenAI: {e}")
        return "Opa, deu um probleminha aqui na roça com a internet, sô! Pode repetir?"
