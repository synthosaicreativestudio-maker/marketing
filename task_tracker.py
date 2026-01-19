import asyncio
import logging
from typing import Set, Optional

logger = logging.getLogger(__name__)

class TaskTracker:
    """
    Отслеживает фоновые задачи (asyncio.Task) и логирует их исключения.
    Предотвращает 'silent failures', когда задача падает без следа.
    """
    
    def __init__(self):
        self.tasks: Set[asyncio.Task] = set()
    
    def create_tracked_task(self, coro, name: Optional[str] = None) -> asyncio.Task:
        """
        Создает задачу, отслеживает её и логирует ошибки при завершении.
        
        Args:
            coro: Корутина для запуска
            name: Имя задачи для отладки
            
        Returns:
            asyncio.Task: Созданная задача
        """
        task = asyncio.create_task(coro, name=name)
        self.tasks.add(task)
        task.add_done_callback(self._task_done_callback)
        return task
    
    def _task_done_callback(self, task: asyncio.Task):
        """Вызывается автоматически при завершении задачи."""
        self.tasks.discard(task)
        
        # Проверяем на ошибки
        try:
            if task.cancelled():
                logger.debug(f"Task '{task.get_name()}' was cancelled.")
                return
            
            exception = task.exception()
            if exception:
                logger.error(
                    f"❌ Background task '{task.get_name()}' crashed with exception: {exception}",
                    exc_info=exception
                )
        except Exception as e:
            logger.error(f"Error in task callback for '{task.get_name()}': {e}")
    
    def cancel_all(self):
        """Отменяет все отслеживаемые задачи."""
        logger.info(f"Cancelling {len(self.tasks)} background tasks...")
        for task in self.tasks:
            task.cancel()
    
    def get_running_count(self) -> int:
        """Возвращает количество активных задач."""
        return len(self.tasks)

# Глобальный экземпляр для использования во всем приложении
task_tracker = TaskTracker()
