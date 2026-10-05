import logging
import os
import sys

# Nível de log padrão: INFO (obtido do settings ou variável de ambiente)
def _get_log_level() -> str:
    try:
        from core.config import settings
        return getattr(settings, "LOG_LEVEL", "INFO").upper()
    except Exception:
        return os.getenv("LOG_LEVEL", "INFO").upper()

LOG_LEVEL = _get_log_level()

def setup_logger(name: str = "sales_core") -> logging.Logger:
    logger = logging.getLogger(name)
    
    # Evita adicionar múltiplos handlers se o logger já foi configurado
    if not logger.handlers:
        logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

logger = setup_logger()
