import logging
from typing import Dict, Any

from .base_handler import BaseMessageHandler


class StickerMessageHandler(BaseMessageHandler):
    """
    Обработчик сообщений со стикерами.
    """
    
    def can_handle(self, message: Dict[str, Any]) -> bool:
        """
        Проверяет, содержит ли сообщение стикер.
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            True, если сообщение содержит стикер
        """
        return 'sticker' in message
    
    def handle(self, data: Dict[str, Any]) -> bool:
        """
        Обрабатывает сообщение со стикером.
        
        Args:
            data: Данные сообщения
            
        Returns:
            True, если сообщение было успешно обработано
        """
        # Извлекаем необходимые данные
        message = data['message']
        metadata = self.format_message_metadata(message)
        sticker = message['sticker']
        
        # Извлекаем информацию о стикере
        file_id = sticker.get('file_id', '')
        emoji = sticker.get('emoji', '')
        is_animated = sticker.get('is_animated', False)
        is_video = sticker.get('is_video', False)
        set_name = sticker.get('set_name', '')
        
        # Определяем тип стикера
        sticker_type = "видео-стикер" if is_video else "анимированный стикер" if is_animated else "стикер"
        
        # Формируем описание стикера
        sticker_info = f"{sticker_type} [{emoji}, набор: {set_name}]"
            
        # Форматируем сообщение для логирования и хранения
        sticker_msg = f"\nchat: {metadata['chat_title']} | {metadata['username']}: {sticker_info} (delivered and read {metadata['date']})"
        
        # Добавляем сообщение в Redis и inbox
        self.add_message_to_redis(sticker_msg)
        self.store_inbox_message(sticker_msg)
        
        # Обрабатываем приватное сообщение от сотрудника
        if hasattr(self.agent.toolset, "staff_tool") and message['chat']['type'] == 'private' and metadata['username']:
            # Создаем staff telegram username с префиксом @
            staff_telegram = f"@{metadata['username']}"
            
            # Подготавливаем текст для пересылки
            forward_text = f"[Стикер: {emoji}]"
            
            # Обрабатываем уведомление и пересылаем сообщение в тред со стикером
            if self.handle_staff_notification(
                staff_telegram, 
                forward_text,
                media_type="sticker",
                file_id=file_id
            ):
                return True
        
        # Создаем задачу для обработки стикера
        task_description = f"Нужно обработать стикер от {metadata['username']}: {emoji}"
        
        self.create_task_for_message(metadata['username'], task_description)
        
        return True
