"""
Testes Unitários para a Fragmentação de Balões de Mensagem no WhatsApp.
Valida o comportamento estritamente delimitado pela IA:
- Marcadores explícitos ('|||').
- Quebras de parágrafo ('\\n\\n', '\\r\\n\\r\\n').
- Mensagens sem delimitadores permanecem intactas (sem quebras por palavras/títulos).
- Clamp de segurança (max_baloes).
"""

from core.utils import dividir_mensagens_whatsapp


def test_mensagem_vazia_ou_nula():
    assert dividir_mensagens_whatsapp("") == []
    assert dividir_mensagens_whatsapp("   ") == []
    assert dividir_mensagens_whatsapp(None) == []


def test_texto_sem_delimitadores_permanece_em_balao_unico():
    """
    Se a IA não inseriu '|||' ou quebras de parágrafo '\\n\\n',
    o texto deve permanecer em 1 único balão (sem quebras artificiais por saudações ou palavras).
    """
    texto = (
        "Oi Carlos! Tudo bem? "
        "Passando para saber se você conseguiu dar uma olhada na proposta solar que te enviei ontem. "
        "O que achou?"
    )
    baloes = dividir_mensagens_whatsapp(texto)
    assert len(baloes) == 1
    assert baloes[0] == texto


def test_delimitador_explicito_pipe():
    """Valida divisão estrita pelo marcador '|||' definido pela IA."""
    texto = "Olá Carlos!|||Aqui é o Seu Zé da Silva Solar.|||Você já tem a conta em mãos?"
    baloes = dividir_mensagens_whatsapp(texto)

    assert len(baloes) == 3
    assert baloes[0] == "Olá Carlos!"
    assert baloes[1] == "Aqui é o Seu Zé da Silva Solar."
    assert baloes[2] == "Você já tem a conta em mãos?"


def test_delimitador_paragrafos_duplos_unix():
    """Valida divisão por quebras duplas de parágrafo Unix (\\n\\n)."""
    texto = "Oi Fernando!\n\nSeu consumo mensal é bem alto.\n\nPodemos reduzir até 90% disso. Quer saber como?"
    baloes = dividir_mensagens_whatsapp(texto)

    assert len(baloes) == 3
    assert baloes[0] == "Oi Fernando!"
    assert baloes[1] == "Seu consumo mensal é bem alto."
    assert baloes[2] == "Podemos reduzir até 90% disso. Quer saber como?"


def test_delimitador_paragrafos_duplos_windows_rn():
    """Valida normalização e divisão por quebras duplas de parágrafo Windows (\\r\\n\\r\\n)."""
    texto = "Bom dia Dra. Camila!\r\n\r\nO projeto técnico da sua clínica foi aprovado.\r\n\r\nPodemos agendar a instalação?"
    baloes = dividir_mensagens_whatsapp(texto)

    assert len(baloes) == 3
    assert baloes[0] == "Bom dia Dra. Camila!"
    assert baloes[1] == "O projeto técnico da sua clínica foi aprovado."
    assert baloes[2] == "Podemos agendar a instalação?"


def test_delimitadores_mistos():
    """Valida mensagens que combinam '|||' e '\\n\\n'."""
    texto = "Olá Marcos!|||Aqui está o resumo solicitado.\n\nPodemos agendar uma visita amanhã?"
    baloes = dividir_mensagens_whatsapp(texto)

    assert len(baloes) == 3
    assert baloes[0] == "Olá Marcos!"
    assert baloes[1] == "Aqui está o resumo solicitado."
    assert baloes[2] == "Podemos agendar uma visita amanhã?"


def test_quebras_com_espacos_intermediarios():
    """Valida quebras com espaços e tabulações entre novas linhas (\\n   \\n)."""
    texto = "Primeiro balão\n   \nSegundo balão"
    baloes = dividir_mensagens_whatsapp(texto)

    assert len(baloes) == 2
    assert baloes[0] == "Primeiro balão"
    assert baloes[1] == "Segundo balão"


def test_clamp_max_baloes():
    """Valida o limitador de segurança max_baloes."""
    texto = "B1|||B2|||B3|||B4|||B5|||B6|||B7"
    baloes = dividir_mensagens_whatsapp(texto, max_baloes=4)

    assert len(baloes) == 4
    assert baloes == ["B1", "B2", "B3", "B4"]
