import logging
from typing import Dict, Any

from .base_handler import BaseMessageHandler


class PhotoMessageHandler(BaseMessageHandler):
    """
    Обработчик сообщений с фотографиями.
    """
    
    def can_handle(self, message: Dict[str, Any]) -> bool:
        """
        Проверяет, содержит ли сообщение фотографию.
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            True, если сообщение содержит фотографию
        """
        return 'photo' in message
    
    def handle(self, data: Dict[str, Any]) -> bool:
        """
        Обрабатывает сообщение с фотографией.
        
        Args:
            data: Данные сообщения
            
        Returns:
            True, если сообщение было успешно обработано
        """
        # Извлекаем необходимые данные
        message = data['message']
        metadata = self.format_message_metadata(message)
        
        # Для фото берем самую большую версию (последнюю в массиве)
        photo = message['photo'][-1]
        file_id = photo.get('file_id', '')
        file_size = photo.get('file_size', 0)
        caption = message.get('caption', '')
        
        # Формируем описание фото
        photo_info = f"фото [{file_size} байт]"
        if caption:
            photo_info += f" с подписью: {caption}"
            
        # Форматируем сообщение для логирования и хранения
        photo_msg = f"\nchat: {metadata['chat_title']} | {metadata['username']}: {photo_info} (delivered and read {metadata['date']})"
        
        # Добавляем сообщение в Redis и inbox
        self.add_message_to_redis(photo_msg)
        self.store_inbox_message(photo_msg)
        
        # Обрабатываем приватное сообщение от сотрудника
        if hasattr(self.agent.toolset, "staff_tool") and message['chat']['type'] == 'private' and metadata['username']:
            # Создаем staff telegram username с префиксом @
            staff_telegram = f"@{metadata['username']}"
            
            # Подготавливаем текст для пересылки
            forward_text = f"[Фото]"
            if caption:
                forward_text += f"\nПодпись: {caption}"
            
            # Обрабатываем уведомление и пересылаем сообщение в тред с фото
            if self.handle_staff_notification(
                staff_telegram, 
                forward_text,
                media_type="photo",
                file_id=file_id
            ):
                return True
        
        # Создаем задачу для обработки фото
        task_description = f"Нужно обработать фото от {metadata['username']}"
        if caption:
            task_description += f" с подписью: {caption}"
        
        self.create_task_for_message(metadata['username'], task_description)
        
        return True
