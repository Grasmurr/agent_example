import logging
from typing import Dict, Any, List, Optional

from .base_handler import BaseMessageHandler
from .text_handler import TextMessageHandler
from .voice_handler import VoiceMessageHandler
from .document_handler import DocumentMessageHandler
from .photo_handler import PhotoMessageHandler
from .animation_handler import AnimationMessageHandler
from .sticker_handler import StickerMessageHandler
from .generic_handler import GenericMessageHandler
from .special_command_handler import SpecialCommandHandler


class MessageHandlerFactory:
    """
    Фабрика обработчиков сообщений, которая выбирает подходящий обработчик
    в зависимости от типа сообщения.
    """
    
    def __init__(self, agent):
        """
        Инициализация фабрики обработчиков.
        
        Args:
            agent: Экземпляр основного агента
        """
        self.agent = agent
        
        # Инициализируем все обработчики
        self.handlers: List[BaseMessageHandler] = [
            # Сначала специальные команды (высший приоритет)
            SpecialCommandHandler(agent),
            
            # Затем обработчики для конкретных типов сообщений
            TextMessageHandler(agent),
            VoiceMessageHandler(agent),
            DocumentMessageHandler(agent),
            PhotoMessageHandler(agent),
            AnimationMessageHandler(agent),
            StickerMessageHandler(agent),
            
            # Наконец, обработчик для прочих типов сообщений (низший приоритет)
            GenericMessageHandler(agent)
        ]
    
    def get_handler(self, message: Dict[str, Any]) -> Optional[BaseMessageHandler]:
        """
        Возвращает подходящий обработчик для сообщения.
        
        Args:
            message: Сообщение, для которого нужно найти обработчик
            
        Returns:
            Подходящий обработчик или None, если такой не найден
        """
        for handler in self.handlers:
            try:
                if handler.can_handle(message):
                    return handler
            except Exception as e:
                logging.error(f"Error in handler {handler.__class__.__name__}.can_handle(): {e}")
        
        logging.warning(f"No suitable handler found for message type: {message.keys()}")
        return None
