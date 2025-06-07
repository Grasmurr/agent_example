from .base_monitor import BaseMonitor

class MessagesMonitor(BaseMonitor):
    def __init__(self, staff_tool):
        """
        Инициализация монитора сообщений.
        
        Args:
            staff_tool: Экземпляр StaffTool
        """
        self.staff_tool = staff_tool
    
    def get_raw_data(self) -> str:
        """
        Получение данных о новых сообщениях.
        
        Returns:
            Строковое представление данных
        """
        notifications = self.staff_tool.get_notifications()
        
        if not notifications:
            return "Нет новых сообщений"
        
        result = []
        
        for notification in notifications:
            # Получаем информацию о сотруднике из его Telegram ID
            telegram_id = notification["telegram_username"]
            timestamp = notification["timestamp"]
            
            notification_text = f"Получено новое Telegram сообщение от {telegram_id} ({timestamp}). Используй open_telegram_chat('{telegram_id}') для чтения сообщений."
            result.append(notification_text)
        
        return "\n".join(result)
    
    def render(self) -> str:
        """
        Рендеринг данных о новых сообщениях в XML формате.
        
        Returns:
            XML представление данных о новых сообщениях
        """
        content = self.get_raw_data()
        
        if "Нет новых сообщений" in content:
            return ""  # Не показываем монитор, если нет новых сообщений
        
        return self.wrap_in_xml(
            "new_messages",
            f"\n{content}\n",
            {"source": "staff_manager"}
        )
