import logging
from typing import Dict, Any

from .base_handler import BaseMessageHandler


class AnimationMessageHandler(BaseMessageHandler):
    """
    Обработчик сообщений с анимациями (GIF).
    """
    
    def can_handle(self, message: Dict[str, Any]) -> bool:
        """
        Проверяет, содержит ли сообщение анимацию.
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            True, если сообщение содержит анимацию
        """
        return 'animation' in message
    
    def handle(self, data: Dict[str, Any]) -> bool:
        """
        Обрабатывает сообщение с анимацией.
        
        Args:
            data: Данные сообщения
            
        Returns:
            True, если сообщение было успешно обработано
        """
        # Извлекаем необходимые данные
        message = data['message']
        metadata = self.format_message_metadata(message)
        animation = message['animation']
        
        # Извлекаем информацию об анимации
        file_id = animation.get('file_id', '')
        file_name = animation.get('file_name', 'animation.gif')
        duration = animation.get('duration', 0)
        width = animation.get('width', 0)
        height = animation.get('height', 0)
        caption = message.get('caption', '')
        
        # Формируем описание анимации
        anim_info = f"анимация [{file_name}, {duration}с, {width}x{height}]"
        if caption:
            anim_info += f" с подписью: {caption}"
            
        # Форматируем сообщение для логирования и хранения
        anim_msg = f"\nchat: {metadata['chat_title']} | {metadata['username']}: {anim_info} (delivered and read {metadata['date']})"
        
        # Добавляем сообщение в Redis и inbox
        self.add_message_to_redis(anim_msg)
        self.store_inbox_message(anim_msg)
        
        # Обрабатываем приватное сообщение от сотрудника
        if hasattr(self.agent.toolset, "staff_tool") and message['chat']['type'] == 'private' and metadata['username']:
            # Создаем staff telegram username с префиксом @
            staff_telegram = f"@{metadata['username']}"
            
            # Подготавливаем текст для пересылки
            forward_text = f"[Анимация: {file_name}, {duration}с]"
            if caption:
                forward_text += f"\nПодпись: {caption}"
            
            # Обрабатываем уведомление и пересылаем сообщение в тред с анимацией
            if self.handle_staff_notification(
                staff_telegram, 
                forward_text,
                media_type="animation",
                file_id=file_id
            ):
                return True
        
        # Создаем задачу для обработки анимации
        task_description = f"Нужно обработать анимацию от {metadata['username']}: {file_name}"
        if caption:
            task_description += f" с подписью: {caption}"
        
        self.create_task_for_message(metadata['username'], task_description)
        
        return True
