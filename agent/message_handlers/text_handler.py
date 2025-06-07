import logging
from typing import Dict, Any

from .base_handler import BaseMessageHandler


class TextMessageHandler(BaseMessageHandler):
    """
    Обработчик текстовых сообщений.
    """
    
    def can_handle(self, message: Dict[str, Any]) -> bool:
        """
        Проверяет, содержит ли сообщение текст.
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            True, если сообщение содержит текст
        """
        return 'text' in message and message['text']
    
    def handle(self, data: Dict[str, Any]) -> bool:
        """
        Обрабатывает текстовое сообщение.
        
        Args:
            data: Данные сообщения
            
        Returns:
            True, если сообщение было успешно обработано
        """
        # Извлекаем необходимые данные
        message = data['message']
        metadata = self.format_message_metadata(message)
        text = message['text']
        
        # Форматируем сообщение для логирования и хранения
        msg = f"\nchat: {metadata['chat_title']} | {metadata['username']}: {text} (delivered and read {metadata['date']})"
        
        # Добавляем сообщение в Redis и inbox
        self.add_message_to_redis(msg)
        self.store_inbox_message(msg)
        
        # Обрабатываем приватное сообщение от сотрудника
        if hasattr(self.agent.toolset, "staff_tool") and message['chat']['type'] == 'private' and metadata['username']:
            # Создаем staff telegram username с префиксом @
            staff_telegram = f"@{metadata['username']}"
            
            # Обрабатываем уведомление и пересылаем сообщение в тред
            if self.handle_staff_notification(staff_telegram, text):
                return True
        
        # Создаем задачу для ответа на сообщение
        self.create_task_for_message(
            metadata['username'],
            f"Нужно ответить на сообщение от {metadata['username']}: {text}"
        )
        
        return True
