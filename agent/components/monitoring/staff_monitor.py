from .base_monitor import BaseMonitor

class StaffMonitor(BaseMonitor):
    def __init__(self, staff_tool):
        """
        Инициализация монитора сотрудников.
        
        Args:
            staff_tool: Экземпляр StaffTool
        """
        self.staff_tool = staff_tool
    
    def get_raw_data(self) -> str:
        """
        Получение данных о сотрудниках и их задачах.
        
        Returns:
            Строковое представление данных
        """
        staff_with_tasks = self.staff_tool.data_manager.get_staff_list()
        
        if not staff_with_tasks:
            return "Нет данных о сотрудниках"
        
        result = []
        
        for staff in staff_with_tasks:
            staff_info = f"{staff['full_name']} - {staff['position']} ({staff.get('telegram_username') or staff.get('telegram')})"
            result.append(staff_info)
            # Добавляем задачи сотрудника, если они есть
            if "tasks" in staff and staff["tasks"]:
                for task in staff["tasks"]:
                    task_info = f"   Задача #{task['id']}: {task['description']} - Срок: {task['deadline']} - Статус: {task['status']}"
                    result.append(task_info)
            else:
                result.append("   Нет активных задач")
            
            result.append("")  # Пустая строка между сотрудниками
        
        return "\n".join(result)
    
    def render(self) -> str:
        """
        Рендеринг данных о сотрудниках в XML формате.
        
        Returns:
            XML представление данных о сотрудниках
        """
        content = self.get_raw_data()
        
        if "Нет данных о сотрудниках" in content:
            return ""  # Не показываем монитор, если нет данных
        
        return self.wrap_in_xml(
            "staff_list",
            f"\n{content}\n",
            {"source": "staff_manager"}
        )
