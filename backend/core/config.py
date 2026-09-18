"""
Central de Configurações da Aplicação (Twelve-Factor App - Config).
Carrega variáveis de ambiente com validação estrita de tipos via Pydantic Settings.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Banco de Dados PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/ecossistema_vendas"
    SQL_ECHO: bool = False
    
    # Cache e Filas Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Gateway WhatsApp (Uazapi)
    UAZAPI_URL: str = "https://inteligentte.uazapi.com"
    UAZAPI_TOKEN: str = ""
    
    # Provedor de Inteligência Artificial (OpenAI)
    OPENAI_API_KEY: str = ""
    
    # Parâmetros Operacionais e Heurísticas de Negócio
    DEBOUNCE_SECONDS: float = 4.5
    JANELA_HISTORICO_RECENTE: int = 6  # Janela de mensagens imediatas repassadas aos agentes
    JANELA_HISTORICO_MAX: int = 20
    
    # Modo de Teste / Sandbox e Filtro de Segurança
    SANDBOX_MODE: bool = True
    WHITELIST_PHONE_SUFFIX: str = "91923098"
    
    # Segurança de Entrada e Webhook
    WEBHOOK_SECRET_TOKEN: str = ""  # Se definido, exige X-Webhook-Secret ou ?token=
    
    # Parâmetros de Alta Concorrência e Pool do PostgreSQL
    DB_POOL_SIZE: int = 25
    DB_MAX_OVERFLOW: int = 50
    DB_POOL_TIMEOUT: float = 30.0
    DB_POOL_RECYCLE: int = 1800

    # Semáforo Global de Concorrência de IA (Proteção contra Thundering Herd / Rate Limits)
    CONCURRENCY_SEMAPHORE_LIMIT: int = 30

    # Modelos de Inteligência Artificial e FinOps
    MODEL_CLOSER: str = "gpt-4o"
    MODEL_CLOSER_FAST: str = "gpt-4o-mini"        # Usado em NOVO_CONTATO e QUALIFICACAO
    MODEL_CLOSER_ADVANCED: str = "gpt-4o"        # Usado em NEGOCIACAO e FECHAMENTO
    DYNAMIC_MODEL_ROUTING: bool = True          # Roteamento inteligente para redução de custos
    MODEL_ANALYZER: str = "gpt-4o-mini"
    MODEL_WHISPER: str = "whisper-1"
    
    # Parâmetros de Rede e Timeouts
    UAZAPI_TIMEOUT_SECONDS: float = 15.0

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instância única (Singleton) consumida por todo o backend
settings = Settings()
