"""
Módulo de Exceções Customizadas do Ecossistema de Vendas.
Define hierarquias claras de exceções de Domínio, Infraestrutura e Segurança,
evitando o acoplamento precoce com frameworks HTTP nas camadas internas.
"""

class AppException(Exception):
    """Exceção base de toda a aplicação."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ----------------- EXCEÇÕES DE DOMÍNIO -----------------

class DomainException(AppException):
    """Exceção base para regras de negócio e invariantes do domínio."""
    pass


class LeadNotFoundError(DomainException):
    """Lançada quando uma operação requer um lead que não existe no sistema."""
    pass


class LeadOptedOutError(DomainException):
    """Lançada quando uma operação tenta interagir com um lead que solicitou opt-out."""
    pass


class InvalidPhoneNumberError(DomainException):
    """Lançada quando o número de telefone não atende aos requisitos mínimos de validação."""
    pass


class TransbordoStateError(DomainException):
    """Lançada quando ocorre uma transição inválida de controle no transbordo."""
    pass


# ----------------- EXCEÇÕES DE INFRAESTRUTURA -----------------

class InfrastructureException(AppException):
    """Exceção base para falhas em serviços de infraestrutura (banco, cache, gateways)."""
    pass


class BufferOperationError(InfrastructureException):
    """Lançada quando operações de leitura ou limpeza atômica no Redis falham."""
    pass


class ExternalGatewayError(InfrastructureException):
    """Lançada quando um provedor externo (Uazapi, OpenAI) falha criticamente."""
    pass


# ----------------- EXCEÇÕES DE SEGURANÇA -----------------

class SecurityException(AppException):
    """Exceção base para violações de segurança e acesso não autorizado."""
    pass


class UnauthorizedWebhookError(SecurityException):
    """Lançada quando a validação de assinatura ou segredo do webhook falha."""
    pass
