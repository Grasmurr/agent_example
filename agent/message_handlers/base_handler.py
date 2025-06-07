from abc import ABC, abstractmethod
from datetime import datetime
import logging
from typing import Dict, Any, Optional


class BaseMessageHandler(ABC):
    """
    Базовый абстрактный класс для обработчиков сообщений.
    Предоставляет общий интерфейс и базовую функциональность для всех обработчиков.
    """
    
    def __init__(self, agent):
        """
        Инициализация базового обработчика.
        
        Args:
            agent: Экземпляр основного агента
        """
        self.agent = agent
    
    @abstractmethod
    def can_handle(self, message: Dict[str, Any]) -> bool:
        """
        Проверяет, может ли данный обработчик обработать сообщение.
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            True, если обработчик может обработать сообщение, иначе False
        """
        pass
    
    @abstractmethod
    def handle(self, data: Dict[str, Any]) -> bool:
        """
        Обрабатывает сообщение.
        
        Args:
            data: Данные сообщения для обработки
            
        Returns:
            True, если сообщение было успешно обработано, иначе False
        """
        pass
    
    def format_message_metadata(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлекает и форматирует общие метаданные из сообщения.
        
        Args:
            message: Сообщение для форматирования
            
        Returns:
            Словарь метаданных сообщения
        """
        metadata = {}
        
        # Извлекаем основные метаданные
        metadata['username'] = message['from'].get('username')
        metadata['chat_title'] = message['chat'].get('title', 'private')
        metadata['date'] = datetime.fromtimestamp(int(message['date'])).strftime('%Y-%m-%d %H:%M:%S')
        metadata['message_thread_id'] = message.get('message_thread_id')
        
        return metadata
    
    def add_message_to_redis(self, msg: str) -> bool:
        """
        Добавляет сообщение в Redis.
        
        Args:
            msg: Форматированное сообщение для добавления
            
        Returns:
            True в случае успеха, False при ошибке
        """
        try:
            self.agent.add_message_to_redis(msg)
            logging.info(f"Added message to Redis chat: {msg}")
            return True
        except Exception as e:
            logging.error(f"Failed to add message to Redis chat: {e}")
            return False
    
    def store_inbox_message(self, msg: str) -> bool:
        """
        Сохраняет сообщение в inbox.
        
        Args:
            msg: Форматированное сообщение для сохранения
            
        Returns:
            True в случае успеха, False при ошибке
        """
        try:
            self.agent.store_inbox_message(msg)
            logging.info(f"Stored message in inbox: {msg}")
            return True
        except Exception as e:
            logging.error(f"Failed to store message in inbox: {e}")
            return False
    
    def handle_staff_notification(self, staff_telegram: str, message_content: str, 
                                  media_type: str = None, file_id: str = None) -> bool:
        """
        Обрабатывает уведомление для сотрудника и пересылает сообщение в тред.
        Поддерживает как текстовые, так и медиа-сообщения.
        
        Args:
            staff_telegram: Telegram ID сотрудника с префиксом @
            message_content: Текст сообщения или описание медиа для пересылки
            media_type: Тип медиа (voice, photo, document, etc.) или None для текста
            file_id: ID файла в Telegram для медиа-сообщений
            
        Returns:
            True если успешно, False в случае ошибки
        """
        if not hasattr(self.agent.toolset, "staff_tool"):
            return False
            
        # Добавляем уведомление для сотрудника
        self.agent.toolset.staff_tool.add_notification(staff_telegram)
        
        # Пересылаем сообщение в тред в супергруппе
        try:
            success = self.agent.toolset.staff_tool.forward_message_to_thread(
                staff_telegram, message_content, media_type, file_id
            )
            if not success:
                logging.warning(f"Не удалось переслать сообщение от {staff_telegram} в тред, но процесс продолжается")
            return success
        except Exception as e:
            logging.error(f"Ошибка при пересылке сообщения в тред: {e}")
            return False
    
    def create_task_for_message(self, username: str, task_description: str) -> Optional[int]:
        """
        Создает задачу для обработки сообщения.
        
        Args:
            username: Имя пользователя отправителя
            task_description: Описание задачи
            
        Returns:
            ID созданной задачи или None в случае ошибки
        """
        if not hasattr(self.agent.toolset, "task_tool"):
            return None
            
        try:
            task_id = self.agent.toolset.task_tool.create_task(
                description=task_description,
            )
            logging.info(f"Created task #{task_id} to respond to message")
            return task_id
        except Exception as e:
            logging.error(f"Failed to create task for message response: {e}")
            return None
