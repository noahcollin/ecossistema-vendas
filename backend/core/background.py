"""
Gerenciador Centralizado de Tarefas Assíncronas em Segundo Plano (Background Tasks).
Mantém referências fortes (strong references) às tasks ativas para impedir coleta prematura
pelo Garbage Collector do Python (CPython asyncio hazard) e garante rastreamento de exceções.
"""

import asyncio
from typing import Any, Coroutine
from core.logger import logger

_ACTIVE_TASKS: set[asyncio.Task[Any]] = set()


def _on_task_done(task: asyncio.Task[Any]) -> None:
    """Callback disparado ao término da task para limpeza de referência e auditoria de falhas."""
    _ACTIVE_TASKS.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            f"[BACKGROUND TASK ERRO] ❌ Exceção não tratada na tarefa '{task.get_name()}': {exc}",
            exc_info=exc,
        )


def spawn_background_task(
    coro: Coroutine[Any, Any, Any],
    *,
    name: str | None = None,
) -> asyncio.Task[Any]:
    """
    Agenda uma corrotina em segundo plano mantendo referência forte até sua conclusão.
    Registra automaticamente erros inesperados nos logs estruturados da aplicação.
    """
    task = asyncio.create_task(coro, name=name)
    _ACTIVE_TASKS.add(task)
    task.add_done_callback(_on_task_done)
    return task


def get_active_background_tasks_count() -> int:
    """Retorna o total de tasks em segundo plano ativas no momento."""
    return len(_ACTIVE_TASKS)


async def drain_background_tasks(timeout: float = 5.0) -> None:
    """Aguarda graciosamente as tasks em voo durante o encerramento (graceful shutdown)."""
    if not _ACTIVE_TASKS:
        return
    pending = list(_ACTIVE_TASKS)
    logger.info(f"[SHUTDOWN] ⏳ Aguardando conclusão de {len(pending)} tarefa(s) em segundo plano...")
    _, still_running = await asyncio.wait(pending, timeout=timeout)
    for task in still_running:
        task.cancel()

