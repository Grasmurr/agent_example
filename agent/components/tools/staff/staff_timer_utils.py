"""
Staff timer utilities for managing staff planning and reporting timers.
"""
import logging
from typing import Dict, Any, Optional

class StaffTimerUtils:
    """
    Utilities for managing staff planning and reporting timers.
    """
    
    @staticmethod
    def create_planning_action(staff: Dict[str, Any]) -> str:
        """
        Create action text for task planning timer.
        
        Args:
            staff: Staff information dictionary
            
        Returns:
            Action text as string
        """
        telegram_username = staff.get('telegram_username')
        staff_name = staff.get('full_name', 'Сотрудник')
        staff_name_parts = staff_name.split()
        first_name = staff_name_parts[1] if len(staff_name_parts) > 1 else staff_name
        
        # Create a detailed action instruction
        action = (
            f"Отправить утреннее сообщение сотруднику {staff_name} ({telegram_username}). "
            f"1. Используй send_telegram_message_to('{telegram_username}', сообщение). "
            f"2. Используй read_sheet('ВСЕЗАДАЧИ') для получения всех задач и фильтруй по имени сотрудника '{staff_name}'. "
            f"3. В сообщении обратись к сотруднику по имени '{first_name}'. "
            f"4. Попроси прокомментировать (аудио не более одной минуты) задачи текущего периода и сегодняшние действия. "
            f"5. Укажи общую сумму задач и количество выполненных задач, если доступно."
        )
        
        return action
    
    @staticmethod
    def create_reporting_action(staff: Dict[str, Any]) -> str:
        """
        Create action text for task reporting timer.
        
        Args:
            staff: Staff information dictionary
            
        Returns:
            Action text as string
        """
        telegram_username = staff.get('telegram_username')
        staff_name = staff.get('full_name', 'Сотрудник')
        staff_name_parts = staff_name.split()
        first_name = staff_name_parts[1] if len(staff_name_parts) > 1 else staff_name
        
        # Create a detailed action instruction
        action = (
            f"Отправить вечернее сообщение сотруднику {staff_name} ({telegram_username}). "
            f"1. Используй send_telegram_message_to('{telegram_username}', сообщение). "
            f"2. В сообщении обратись к сотруднику по имени '{first_name}'. "
            f"3. Попроси прокомментировать (аудио не более одной минуты) сегодняшние действия "
            f"и проговорить задачи в целом, включая их корректировки по результатам сегодняшнего дня."
        )
        
        return action
    
    @staticmethod
    def setup_task_planning_timer(staff: Dict[str, Any], timer_tool) -> str:
        """
        Set up a timer for task planning message at specified time.
        
        Args:
            staff: Staff information dictionary
            timer_tool: The timer tool instance
            
        Returns:
            Timer ID or error message
        """
        try:
            if not timer_tool:
                return "TimerTool not available"
            
            staff_name = staff.get('full_name', 'Сотрудник')
            telegram_username = staff.get('telegram_username')
            planning_time = staff.get('task_planning_at')
            
            if not telegram_username or not planning_time:
                return f"Missing telegram_username or task_planning_at for {staff_name}"
            
            timer_name = f"Task Planning - {staff_name}"
            time_spec = f"в {planning_time} ежедневно"
            
            # Generate action text
            action = StaffTimerUtils.create_planning_action(staff)
            
            result = timer_tool.create_timer(
                time_spec=time_spec,
                name=timer_name,
                action=action
            )
            
            return result
        except Exception as e:
            logging.error(f"Error setting up task planning timer: {e}")
            return f"Error setting up task planning timer: {str(e)}"
    
    @staticmethod
    def setup_task_reporting_timer(staff: Dict[str, Any], timer_tool) -> str:
        """
        Set up a timer for task reporting message at specified time.
        
        Args:
            staff: Staff information dictionary
            timer_tool: The timer tool instance
            
        Returns:
            Timer ID or error message
        """
        try:
            if not timer_tool:
                return "TimerTool not available"
            
            staff_name = staff.get('full_name', 'Сотрудник')
            telegram_username = staff.get('telegram_username')
            reporting_time = staff.get('task_reporting_at')
            
            if not telegram_username or not reporting_time:
                return f"Missing telegram_username or task_reporting_at for {staff_name}"
            
            timer_name = f"Task Reporting - {staff_name}"
            time_spec = f"в {reporting_time} ежедневно"
            
            # Generate action text
            action = StaffTimerUtils.create_reporting_action(staff)
            
            result = timer_tool.create_timer(
                time_spec=time_spec,
                name=timer_name,
                action=action
            )
            
            return result
        except Exception as e:
            logging.error(f"Error setting up task reporting timer: {e}")
            return f"Error setting up task reporting timer: {str(e)}"
    
    @staticmethod
    def setup_task_sync_timer(timer_tool, staff_tool) -> str:
        """
        Set up a timer for periodically synchronizing tasks with Redis.
        
        Args:
            timer_tool: The timer tool instance
            staff_tool: The staff tool instance
            
        Returns:
            Timer ID or error message
        """
        try:
            if not timer_tool:
                return "TimerTool not available"
            
            timer_name = "Синхронизация задач с Redis"
            time_spec = "каждые 30 минут"
            
            # Create action for timer
            action = (
                "Синхронизировать задачи сотрудников с Redis. "
                "Используй staff_tool.sync_sheet_tasks_with_redis() для обновления данных в Redis."
            )
            
            result = timer_tool.create_timer(
                time_spec=time_spec,
                name=timer_name,
                action=action
            )
            
            return result
        except Exception as e:
            logging.error(f"Error setting up task sync timer: {e}")
            return f"Error setting up task sync timer: {str(e)}"
