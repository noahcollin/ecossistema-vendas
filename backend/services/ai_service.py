import os
from openai import AsyncOpenAI

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
2. Se o cliente perguntar algo que não seja sobre legumes, diga educadamente que você só entende de plantação.
3. Nunca invente produtos que não estão na lista.
4. Sempre tente puxar assunto para fechar a venda perguntando a quantidade que a pessoa quer.
"""

async def gerar_resposta_vendedor(nome_cliente: str, interacoes: list) -> str:
    """
    Pega o histórico de conversas do banco e gera uma resposta usando GPT-4o.
    """
    try:
        # Montamos a lista de mensagens (Role = system, user, assistant)
        mensagens = [
            {"role": "system", "content": PROMPT_FAZENDEIRO}
        ]
        
        # Formatando o histórico 
        for i in interacoes:
            role = "user" if i.origem.value == "cliente" else "assistant"
            mensagens.append({"role": role, "content": i.texto})
            
        resposta = await client.chat.completions.create(
            model="gpt-4o",
            messages=mensagens,
            temperature=0.7,
            max_tokens=300
        )
        
        return resposta.choices[0].message.content
    except Exception as e:
        print(f"❌ [OPENAI ERRO] {e}")
        return "Opa, deu um probleminha aqui na roça com a internet, sô! Pode repetir?"
