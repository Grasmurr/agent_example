import logging
from typing import Dict, Any

from .base_handler import BaseMessageHandler


class DocumentMessageHandler(BaseMessageHandler):
    """
    Обработчик сообщений с документами (файлами).
    """
    
    def can_handle(self, message: Dict[str, Any]) -> bool:
        """
        Проверяет, содержит ли сообщение документ.
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            True, если сообщение содержит документ
        """
        return 'document' in message
    
    def handle(self, data: Dict[str, Any]) -> bool:
        """
        Обрабатывает сообщение с документом.
        
        Args:
            data: Данные сообщения
            
        Returns:
            True, если сообщение было успешно обработано
        """
        # Извлекаем необходимые данные
        message = data['message']
        metadata = self.format_message_metadata(message)
        document = message['document']
        
        # Извлекаем информацию о документе
        file_id = document.get('file_id', '')
        file_name = document.get('file_name', 'unnamed_file')
        mime_type = document.get('mime_type', 'unknown')
        file_size = document.get('file_size', 0)
        caption = message.get('caption', '')
        
        # Формируем описание документа
        doc_info = f"документ [{file_name}, {mime_type}, {file_size} байт]"
        if caption:
            doc_info += f" с подписью: {caption}"
            
        # Форматируем сообщение для логирования и хранения
        doc_msg = f"\nchat: {metadata['chat_title']} | {metadata['username']}: {doc_info} (delivered and read {metadata['date']})"
        
        # Добавляем сообщение в Redis и inbox
        self.add_message_to_redis(doc_msg)
        self.store_inbox_message(doc_msg)
        
        # Обрабатываем приватное сообщение от сотрудника
        if hasattr(self.agent.toolset, "staff_tool") and message['chat']['type'] == 'private' and metadata['username']:
            # Создаем staff telegram username с префиксом @
            staff_telegram = f"@{metadata['username']}"
            
            # Подготавливаем текст для пересылки
            forward_text = f"[Документ: {file_name}, {mime_type}, {file_size} байт]"
            if caption:
                forward_text += f"\nПодпись: {caption}"
            
            # Обрабатываем уведомление и пересылаем сообщение в тред с документом
            if self.handle_staff_notification(
                staff_telegram, 
                forward_text,
                media_type="document",
                file_id=file_id
            ):
                return True
        
        # Создаем задачу для обработки документа
        task_description = f"Нужно обработать документ от {metadata['username']}: {file_name}"
        if caption:
            task_description += f" с подписью: {caption}"
        
        self.create_task_for_message(metadata['username'], task_description)
        
        return True
