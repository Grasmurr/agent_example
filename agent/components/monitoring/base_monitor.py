from abc import ABC, abstractmethod
from typing import Optional
import xml.sax.saxutils

class BaseMonitor(ABC):
    """Базовый класс для всех мониторов"""

    @abstractmethod
    def get_raw_data(self) -> str:
        """Получение сырых данных от источника"""
        pass

    def escape_for_xml(self, content: str) -> str:
        """Safely escape content for XML inclusion"""
        return xml.sax.saxutils.escape(content)
        
    def wrap_in_xml(self, tag: str, content: str, attributes: Optional[dict] = None) -> str:
        """Обертывание контента в XML с автоматическим экранированием"""
        if "<" not in content or ">" not in content:
            content = self.escape_for_xml(content)
            
        attr_str = '' if not attributes else ' ' + ' '.join(f'{k}="{v}"' for k, v in attributes.items())
        return f"<{tag}{attr_str}>{content}</{tag}>"

    @abstractmethod
    def render(self) -> str:
        """Рендеринг данных в XML формате"""
        pass