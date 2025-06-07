import logging
import re
from typing import Dict, Any, List

from .base_handler import BaseMessageHandler


class GenericMessageHandler(BaseMessageHandler):
    """
    Обработчик прочих типов сообщений, которые не обрабатываются специальными обработчиками.
    """
    
    def __init__(self, agent):
        """
        Инициализация обработчика прочих типов сообщений.
        
        Args:
            agent: Экземпляр основного агента
        """
        super().__init__(agent)
        # Список типов сообщений, которые может обрабатывать этот обработчик
        self.supported_types = ['video', 'audio', 'video_note', 'location', 'contact', 'poll', 'game']
    
    def can_handle(self, message: Dict[str, Any]) -> bool:
        """
        Проверяет, может ли данный обработчик обработать сообщение.
        Этот обработчик может обрабатывать различные типы сообщений, 
        которые не обрабатываются другими специализированными обработчиками.
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            True, если обработчик может обработать сообщение
        """
        # Проверяем наличие одного из поддерживаемых типов сообщений
        return any(msg_type in message for msg_type in self.supported_types)
    
    def handle(self, data: Dict[str, Any]) -> bool:
        """
        Обрабатывает сообщение прочего типа.
        
        Args:
            data: Данные сообщения
            
        Returns:
            True, если сообщение было успешно обработано
        """
        # Извлекаем необходимые данные
        message = data['message']
        metadata = self.format_message_metadata(message)
        
        # Определяем тип сообщения
        msg_type = next((key for key in self.supported_types if key in message), 'неизвестный тип')
        file_id = None
        
        # Пытаемся извлечь file_id для медиа-сообщений
        if msg_type in ['video', 'audio', 'video_note']:
            media_object = message.get(msg_type, {})
            file_id = media_object.get('file_id', None)
        
        # Получаем подпись, если доступна
        caption = message.get('caption', '')
        
        # Форматируем информацию о типе сообщения
        type_info = f"{msg_type}"
        if caption:
            type_info += f" с подписью: {caption}"
            
        # Форматируем сообщение для логирования и хранения
        type_msg = f"\nchat: {metadata['chat_title']} | {metadata['username']}: {type_info} (delivered and read {metadata['date']})"
        
        # Добавляем сообщение в Redis и inbox
        self.add_message_to_redis(type_msg)
        self.store_inbox_message(type_msg)
        
        # Обрабатываем приватное сообщение от сотрудника
        if hasattr(self.agent.toolset, "staff_tool") and message['chat']['type'] == 'private' and metadata['username']:
            # Создаем staff telegram username с префиксом @
            staff_telegram = f"@{metadata['username']}"
            
            # Подготавливаем текст для пересылки
            forward_text = f"[{msg_type.capitalize()}]"
            if caption:
                forward_text += f"\nПодпись: {caption}"
            
            # Обрабатываем уведомление и пересылаем сообщение в тред с медиа
            # если у нас есть file_id
            if self.handle_staff_notification(
                staff_telegram, 
                forward_text,
                media_type=msg_type if file_id else None,
                file_id=file_id
            ):
                return True
        
        # Создаем задачу для обработки сообщения
        task_description = f"Нужно обработать {msg_type} от {metadata['username']}"
        if caption:
            task_description += f" с подписью: {caption}"
        
        self.create_task_for_message(metadata['username'], task_description)
        
        return True
