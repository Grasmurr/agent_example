"""
Staff timer manager for handling staff planning and reporting timers.
Provides interfaces to set up timers for staff members.
"""
import logging
from typing import Dict, Any, Optional, List
from components.tools.staff.staff_timer_utils import StaffTimerUtils

class StaffTimerManager:
    """
    Manages timers for staff planning and reporting.
    """
    
    def __init__(self, data_manager, agent=None):
        """
        Initialize the staff timer manager.
        
        Args:
            data_manager: Instance of StaffDataManager for accessing staff data
            agent: Reference to the agent instance (optional)
        """
        self.data_manager = data_manager
        self.agent = agent
        
        logging.info("StaffTimerManager initialized")
    
    def setup_task_planning_timer(self, staff_telegram_username):
        """
        Set up a timer for sending task planning messages to a staff member.
        
        Args:
            staff_telegram_username: Telegram username of the staff member
            
        Returns:
            Result message
        """
        try:
            if not self.agent or not hasattr(self.agent.toolset, "timer_tool"):
                return "TimerTool not available"
            
            # Get staff information
            staff_list = self.data_manager.get_staff_list()
            
            if not staff_telegram_username.startswith('@'):
                staff_telegram_username = f"@{staff_telegram_username}"
            
            staff = next((s for s in staff_list if s.get("telegram_username") == staff_telegram_username), None)
            
            if not staff:
                return f"Staff member with Telegram username {staff_telegram_username} not found"
            
            # Use StaffTimerUtils to set up the timer
            result = StaffTimerUtils.setup_task_planning_timer(
                staff, 
                self.agent.toolset.timer_tool
            )
            
            return result
        except Exception as e:
            logging.error(f"Error setting up task planning timer: {e}")
            return f"Error setting up task planning timer: {str(e)}"
    
    def setup_task_reporting_timer(self, staff_telegram_username):
        """
        Set up a timer for sending task reporting messages to a staff member.
        
        Args:
            staff_telegram_username: Telegram username of the staff member
            
        Returns:
            Result message
        """
        try:
            if not self.agent or not hasattr(self.agent.toolset, "timer_tool"):
                return "TimerTool not available"
            
            # Get staff information
            staff_list = self.data_manager.get_staff_list()
            
            if not staff_telegram_username.startswith('@'):
                staff_telegram_username = f"@{staff_telegram_username}"
            
            staff = next((s for s in staff_list if s.get("telegram_username") == staff_telegram_username), None)
            
            if not staff:
                return f"Staff member with Telegram username {staff_telegram_username} not found"
            
            # Use StaffTimerUtils to set up the timer
            result = StaffTimerUtils.setup_task_reporting_timer(
                staff, 
                self.agent.toolset.timer_tool
            )
            
            return result
        except Exception as e:
            logging.error(f"Error setting up task reporting timer: {e}")
            return f"Error setting up task reporting timer: {str(e)}"
    
    def setup_all_staff_timers(self):
        """
        Set up planning and reporting timers for all staff members using actions instead of procedures.
        Also synchronizes all staff tasks with Redis.
        
        Returns:
            Dictionary with setup results for each staff member
        """
        try:
            staff_list = self.data_manager.get_staff_list()
            
            results = {}
            
            # Sync all tasks with Redis first
            if hasattr(self.agent.toolset, "staff_tool") and hasattr(self.agent.toolset.staff_tool, "sync_sheet_tasks_with_redis"):
                sync_result = self.agent.toolset.staff_tool.sync_sheet_tasks_with_redis()
                results["sync"] = sync_result
            
            # Then set up timers for each staff member
            for staff in staff_list:
                staff_name = staff.get('full_name', 'Unknown')
                telegram_username = staff.get('telegram_username')
                
                if not telegram_username:
                    results[staff_name] = {"error": "Missing telegram_username"}
                    continue
                    
                planning_result = StaffTimerUtils.setup_task_planning_timer(
                    staff, 
                    self.agent.toolset.timer_tool
                )
                
                reporting_result = StaffTimerUtils.setup_task_reporting_timer(
                    staff, 
                    self.agent.toolset.timer_tool
                )
                
                results[staff_name] = {
                    "planning": planning_result,
                    "reporting": reporting_result
                }
            
            # Set up task sync timer
            sync_timer_result = StaffTimerUtils.setup_task_sync_timer(
                self.agent.toolset.timer_tool, 
                self.agent.toolset.staff_tool
            )
            results["sync_timer"] = sync_timer_result
            
            return results
            
        except Exception as e:
            logging.error(f"Error setting up staff timers: {e}")
            return {"error": f"Error setting up staff timers: {str(e)}"}
