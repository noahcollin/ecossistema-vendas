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

    # Guardião de Velocidade Conversacional & FinOps Anti-Loop (Autonomous Closer Drive)
    PACING_THRESHOLD_PROACTIVE: int = 10   # Inicia postura ativa de fechamento (Seu Zé toma as rédeas)
    PACING_THRESHOLD_DECISIVE: int = 20    # Chamada conclusiva amigável (fechamento direto ou descarte)
    PACING_THRESHOLD_MAX: int = 30         # Trava FinOps: encerramento cordial e desqualificação autônoma
    
    # Modo de Teste / Sandbox e Filtro de Segurança
    SANDBOX_MODE: bool = True
    WHITELIST_PHONE_SUFFIX: str = "91923098"
    
    # Segurança de Entrada e Webhook
    WEBHOOK_SECRET_TOKEN: str = ""  # Se definido, exige X-Webhook-Secret ou ?token=
    CORS_ORIGINS: str = "*"  # Origens permitidas separadas por vírgula (ex: 'https://painel.com,http://localhost:3000')
    
    # Logging do Sistema
    LOG_LEVEL: str = "INFO"

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
    MODEL_AUDITOR: str = "gpt-4o-mini"
    MODEL_WHISPER: str = "whisper-1"
    
    # Parâmetros de Rede e Timeouts
    UAZAPI_TIMEOUT_SECONDS: float = 15.0
    OPENAI_TIMEOUT_SECONDS: float = 30.0
    OPENAI_MAX_RETRIES: int = 2

    # Motor de Cadência e Follow-Up Cronometrado (Fase 2 do PRD - RF11 e RF12)
    FOLLOWUP_ENABLED: bool = True
    FOLLOWUP_INTERVAL_1_HOURS: float = 2.0
    FOLLOWUP_INTERVAL_2_HOURS: float = 24.0
    FOLLOWUP_INTERVAL_3_HOURS: float = 72.0
    FOLLOWUP_WORKER_POLL_INTERVAL_SECONDS: int = 30
    BUSINESS_HOURS_START: str = "08:30"
    BUSINESS_HOURS_END: str = "18:30"
    BUSINESS_HOURS_SATURDAY_START: str = "09:00"
    BUSINESS_HOURS_SATURDAY_END: str = "12:30"

    # Blindagem Anti-Ban e Human Pacing (Escalonamento Temporal de Follow-ups)
    FOLLOWUP_PACING_MIN_SECONDS: float = 30.0   # Respiro mínimo entre mensagens sucessivas no worker
    FOLLOWUP_PACING_MAX_SECONDS: float = 60.0   # Respiro máximo entre mensagens sucessivas no worker
    FOLLOWUP_JITTER_STEP_MINUTES: float = 3.0   # Espaçamento entre leads acumulados na reabertura
    FOLLOWUP_SIMULAR_DIGITACAO: bool = True     # Simula 'digitando...' antes do envio

    # Transbordo Humano e Gestão de Exceções (Seção 6 e RF10 do PRD)
    SUPERVISOR_PHONE: str = ""                  # Telefone WhatsApp da equipe/supervisor para alertas
    TRANSBORDO_WEBHOOK_URL: str = ""             # Webhook externo para alertas (Slack, Discord, CRM)
    TRANSBORDO_VIP_VALOR_MIN: float = 10000.0    # Gatilho de alto valor para transbordo consultivo VIP
    TRANSBORDO_ENVIAR_MENSAGEM_CLIENTE: bool = False  # False para simulação humana 100% invisível ao cliente
    TRANSBORDO_INACTIVITY_TIMEOUT_MINUTES: int = 60  # Tempo de inatividade humana antes da IA reassumir o lead

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instância única (Singleton) consumida por todo o backend
settings = Settings()
