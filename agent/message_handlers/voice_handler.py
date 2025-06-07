import logging
import os
from typing import Dict, Any

from .base_handler import BaseMessageHandler
from components.stt import transcribe  # Import transcribe function directly


class VoiceMessageHandler(BaseMessageHandler):
    """
    Обработчик голосовых сообщений.
    """
    
    def can_handle(self, message: Dict[str, Any]) -> bool:
        """
        Проверяет, содержит ли сообщение голосовое сообщение.
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            True, если сообщение содержит голосовое сообщение
        """
        return 'voice' in message
    
    def handle(self, data: Dict[str, Any]) -> bool:
        """
        Обрабатывает голосовое сообщение.
        
        Args:
            data: Данные сообщения
            
        Returns:
            True, если сообщение было успешно обработано
        """
        # Извлекаем необходимые данные
        message = data['message']
        metadata = self.format_message_metadata(message)
        voice = message['voice']
        file_id = voice['file_id']
        
        # Скачиваем и транскрибируем голосовое сообщение
        file_path = self.agent.toolset.tg_tool.download_voice_file(voice['file_id'])
        stt_text = transcribe(file_path)  # Use transcribe function directly
        os.remove(file_path)
        logging.info(f"Transcribed voice message: {stt_text}")
        
        # Форматируем сообщение для логирования и хранения
        stt_text_msg = f"\nchat: {metadata['chat_title']} | {metadata['username']}: voice_message[{stt_text}] (delivered and read {metadata['date']})"
        
        # Добавляем сообщение в Redis и inbox
        self.add_message_to_redis(stt_text_msg)
        self.store_inbox_message(stt_text_msg)
        
        # Обрабатываем приватное сообщение от сотрудника
        if hasattr(self.agent.toolset, "staff_tool") and message['chat']['type'] == 'private' and metadata['username']:
            # Создаем staff telegram username с префиксом @
            staff_telegram = f"@{metadata['username']}"
            
            # Обрабатываем уведомление и пересылаем сообщение в тред с голосовым сообщением
            if self.handle_staff_notification(
                staff_telegram, 
                f"[Голосовое сообщение]: {stt_text}", 
                media_type="voice", 
                file_id=file_id
            ):
                return True
        
        # Создаем задачу для ответа на сообщение
        self.create_task_for_message(
            metadata['username'],
            f"Нужно ответить на сообщение от {metadata['username']}: {stt_text}"
        )
        
        return True
