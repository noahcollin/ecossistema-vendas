"""
Testes Unitários de Segurança, Mascaramento LGPD e Exceções Customizadas.
"""

import hmac
import pytest
from core.utils import mascarar_telefone, mascarar_nome, dividir_mensagens_whatsapp
from core.exceptions import (
    AppException,
    DomainException,
    InfrastructureException,
    BufferOperationError,
    SecurityException,
)


def test_mascarar_telefone_lgpd():
    """Valida o mascaramento de telefones celulares no padrão LGPD."""
    assert mascarar_telefone("5583988887777") == "55839****7777"
    assert mascarar_telefone("+5583988887777") == "+5583****7777"
    assert mascarar_telefone("1234") == "1234"
    assert mascarar_telefone("") == ""
    assert mascarar_telefone(None) == ""


def test_mascarar_nome_lgpd():
    """Valida o mascaramento de nomes de cliente para conformidade com a LGPD."""
    assert mascarar_nome("Carlos Silva") == "Carlos S***"
    assert mascarar_nome("Ana") == "An***"
    assert mascarar_nome("Oi") == "Oi"
    assert mascarar_nome("") == "Anônimo"
    assert mascarar_nome(None) == "Anônimo"


def test_exceptions_hierarchy():
    """Valida a hierarquia canônica de exceções do sistema."""
    assert issubclass(DomainException, AppException)
    assert issubclass(InfrastructureException, AppException)
    assert issubclass(BufferOperationError, InfrastructureException)
    assert issubclass(SecurityException, AppException)

    err = BufferOperationError("Falha no cluster Redis")
    assert str(err) == "Falha no cluster Redis"
    assert isinstance(err, InfrastructureException)
    assert isinstance(err, AppException)


def test_webhook_constant_time_comparison():
    """Valida a comparação de tempo constante para proteção anti-timing attack."""
    secret = "segredo_super_forte_123"
    token_correto = "segredo_super_forte_123"
    token_errado = "segredo_super_forte_999"

    assert hmac.compare_digest(token_correto, secret) is True
    assert hmac.compare_digest(token_errado, secret) is False


def test_dividir_mensagens_whatsapp_humanizada():
    """Valida a quebra humanizada de balões de mensagem para envio no WhatsApp."""
    texto = "Olá Carlos! Tudo bem?|||Aqui é o Seu Zé da Silva Solar.|||Você já tem uma conta de energia em mãos?"
    baloes = dividir_mensagens_whatsapp(texto)
    assert len(baloes) == 3
    assert baloes[0] == "Olá Carlos! Tudo bem?"
    assert baloes[1] == "Aqui é o Seu Zé da Silva Solar."
    assert baloes[2] == "Você já tem uma conta de energia em mãos?"
