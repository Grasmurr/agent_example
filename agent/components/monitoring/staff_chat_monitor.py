from .base_monitor import BaseMonitor

class StaffChatMonitor(BaseMonitor):
    def __init__(self, staff_tool):
        """
        Инициализация монитора чата с сотрудником.
        
        Args:
            staff_tool: Экземпляр StaffTool
        """
        self.staff_tool = staff_tool
    
    def get_raw_data(self) -> str:
        """
        Получение данных о текущем открытом чате с сотрудником.
        
        Returns:
            Строковое представление данных
        """
        # Проверяем, открыт ли чат с каким-либо сотрудником
        if not self.staff_tool.current_chat_id:
            return "Чат не открыт. Используйте open_telegram_chat(...) для открытия чата с сотрудником."
        
        # В реальном приложении здесь бы загружалась история сообщений
        # Для демонстрации просто показываем информацию о текущем открытом чате
        
        return f"Открыт чат с {self.staff_tool.current_chat_id}\n\n[История сообщений будет отображаться здесь]"
    
    def render(self) -> str:
        """
        Рендеринг данных о текущем чате в XML формате.
        
        Returns:
            XML представление данных о чате
        """
        content = self.get_raw_data()
        
        if "Чат не открыт" in content:
            return ""  # Не показываем монитор, если чат не открыт
        
        return self.wrap_in_xml(
            "staff_chat",
            f"\n{content}\n",
            {"source": "staff_manager", "chat_id": self.staff_tool.current_chat_id}
        )
