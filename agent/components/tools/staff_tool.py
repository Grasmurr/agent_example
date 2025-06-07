"""
Staff tool for managing staff information, tasks, and communication.
Integrates multiple staff management components into a unified interface.
"""
import logging
from typing import List, Dict, Any, Optional

from .staff.staff_data_manager import StaffDataManager
from .staff.staff_communication import StaffCommunication
from .staff.staff_task_manager import StaffTaskManager
from .staff.staff_sheet_manager import StaffSheetManager
from .staff.staff_timer_manager import StaffTimerManager

class StaffTool:
    def __init__(self, tg_tool, agent=None):
        """
        Initialize the staff tool with required dependencies.
        
        Args:
            tg_tool: Instance of TGTool for sending Telegram messages
            agent: Optional reference to the agent instance
            data_manager: Optional data manager instance (will create one if not provided)
        """
        # Initialize or use provided data manager
        self.data_manager = StaffDataManager()
        
        # Initialize component handlers
        self.communication = StaffCommunication(tg_tool, self.data_manager)
        self.task_manager = StaffTaskManager(self.data_manager)
        self.sheet_manager = StaffSheetManager(self.data_manager, agent)
        self.timer_manager = StaffTimerManager(self.data_manager, agent)
        
        # Store references for direct access
        self.tg_tool = tg_tool
        self.agent = agent
        
        logging.info("StaffTool initialized")
    
    # Communication methods
    def open_telegram_chat(self, staff_telegram: str) -> str:
        """
        Open a chat with a staff member by their Telegram ID.
        
        Args:
            staff_telegram: Telegram ID of the staff member (e.g., "@username")
            
        Returns:
            Message with the result of the operation
        """
        return self.communication.open_telegram_chat(staff_telegram)
    
    def send_telegram_message_to(self, to_staff_telegram: str, msg: str) -> str:
        """
        Send a message to a staff member via Telegram.
        
        Args:
            to_staff_telegram: Telegram ID of the staff member
            msg: Text of the message
            
        Returns:
            Message with the result of the operation
        """
        return self.communication.send_telegram_message_to(to_staff_telegram, msg)
    
    def forward_message_to_thread(self, staff_telegram: str, message_text: str, 
                                  media_type: str = None, file_id: str = None) -> bool:
        """
        Forward a message from a staff member to their thread in the supergroup.
        
        Args:
            staff_telegram: Telegram ID of the staff member
            message_text: Text of the message or media description
            media_type: Type of media (voice, photo, document, etc.) or None for text
            file_id: File ID in Telegram for media messages
            
        Returns:
            True on success, False on error
        """
        return self.communication.forward_message_to_thread(staff_telegram, message_text, media_type, file_id)
    
    # Task management methods
    def task_in_progress(self, task_id: int) -> str:
        """
        Change task status to 'in progress'.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Message with the result of the operation
        """
        return self.task_manager.task_in_progress(task_id)
    
    def task_finished(self, task_id: int) -> str:
        """
        Change task status to 'finished'.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Message with the result of the operation
        """
        return self.task_manager.task_finished(task_id)
    
    # Data query methods
    def get_notifications(self) -> List[Dict]:
        """
        Get a list of notifications about new messages.
        
        Returns:
            List of notification dictionaries
        """
        return self.data_manager.get_notifications()
    
    # Sheet management methods
    def read_staff_tasks(self, staff_telegram_username):
        """
        Read tasks for a specific staff member from the combined tasks sheet.
        
        Args:
            staff_telegram_username: Telegram username of the staff member
            
        Returns:
            DataFrame with filtered staff tasks or error message
        """
        return self.sheet_manager.read_staff_tasks(staff_telegram_username)
    
    def get_staff_tasks_summary(self, staff_telegram_username):
        """
        Get a summary of tasks for a specific staff member.
        
        Args:
            staff_telegram_username: Telegram username of the staff member
            
        Returns:
            Formatted string with task summary
        """
        return self.sheet_manager.get_staff_tasks_summary(staff_telegram_username)
    
    # Timer methods
    def setup_task_planning_timer(self, staff_telegram_username):
        """
        Set up a timer for sending task planning messages to a staff member.
        
        Args:
            staff_telegram_username: Telegram username of the staff member
            
        Returns:
            Result message
        """
        return self.timer_manager.setup_task_planning_timer(staff_telegram_username)
    
    def setup_task_reporting_timer(self, staff_telegram_username):
        """
        Set up a timer for sending task reporting messages to a staff member.
        
        Args:
            staff_telegram_username: Telegram username of the staff member
            
        Returns:
            Result message
        """
        return self.timer_manager.setup_task_reporting_timer(staff_telegram_username)
    
    def setup_all_staff_timers(self):
        """
        Set up planning and reporting timers for all staff members.
        
        Returns:
            Dictionary with setup results for each staff member
        """
        return self.timer_manager.setup_all_staff_timers()
    
    # Synchronization methods
    def sync_sheet_tasks_with_redis(self):
        """
        Synchronize tasks for all staff members from Google Sheets with Redis.
        
        Returns:
            Result message
        """
        return self.task_manager.sync_sheet_tasks_with_redis(self.sheet_manager)
    
    def store_staff_tasks_in_redis(self, staff_telegram_username, tasks_df):
        """
        Store staff tasks in Redis.
        
        Args:
            staff_telegram_username: Telegram username of the staff member
            tasks_df: DataFrame with staff tasks
            
        Returns:
            Result message
        """
        return self.task_manager.store_staff_tasks_in_redis(staff_telegram_username, tasks_df)
    
    def get_staff_tasks_from_redis(self, staff_telegram_username):
        """
        Get staff tasks from Redis.
        
        Args:
            staff_telegram_username: Telegram username of the staff member
            
        Returns:
            List of task dictionaries or error message
        """
        return self.task_manager.get_staff_tasks_from_redis(staff_telegram_username)
