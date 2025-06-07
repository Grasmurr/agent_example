"""
Staff task manager for managing staff tasks.
Handles task status updates and task synchronization with Redis.
"""
import logging
from typing import Dict, Any, Optional, List

class StaffTaskManager:
    """
    Manages staff tasks and their statuses.
    """
    
    def __init__(self, data_manager):
        """
        Initialize the staff task manager.
        
        Args:
            data_manager: Instance of StaffDataManager for accessing staff data
        """
        self.data_manager = data_manager
        
        logging.info("StaffTaskManager initialized")
    
    def task_in_progress(self, task_id: int) -> str:
        """
        Change task status to 'in progress'.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Message with the result of the operation
        """
        result = self.data_manager.update_task_status(task_id, "in progress")
        
        # If this is a new format ID (with staff_id prefix), update in Redis
        if isinstance(task_id, str) and "_" in task_id:
            self.data_manager.update_task_status_in_redis(task_id, "в работе")
            
        return result
    
    def task_finished(self, task_id: int) -> str:
        """
        Change task status to 'finished'.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Message with the result of the operation
        """
        result = self.data_manager.update_task_status(task_id, "finished")
        
        # If this is a new format ID (with staff_id prefix), update in Redis
        if isinstance(task_id, str) and "_" in task_id:
            self.data_manager.update_task_status_in_redis(task_id, "завершено")
            
        return result
    
    def store_staff_tasks_in_redis(self, staff_telegram_username, tasks_df):
        """
        Store staff tasks in Redis after loading from Google Sheets.
        
        Args:
            staff_telegram_username: Telegram username of the staff member
            tasks_df: DataFrame with staff tasks
            
        Returns:
            Result message
        """
        try:
            # Get staff information
            staff_list = self.data_manager.get_staff_list()
            
            if not staff_telegram_username.startswith('@'):
                staff_telegram_username = f"@{staff_telegram_username}"
            
            staff = next((s for s in staff_list if s.get("telegram_username") == staff_telegram_username), None)
            
            if not staff:
                return f"Staff member with Telegram username {staff_telegram_username} not found"
            
            staff_id = staff.get("id")
            if not staff_id:
                return f"Staff ID not found for {staff_telegram_username}"
            
            # Convert DataFrame to list of dictionaries
            if hasattr(tasks_df, "to_dict"):
                tasks_list = tasks_df.to_dict("records")
                
                # Store in Redis
                self.data_manager.store_staff_tasks_in_redis(staff_id, tasks_list)
                
                return f"Stored {len(tasks_list)} tasks for staff member {staff_telegram_username} in Redis"
            else:
                return f"Invalid tasks format for {staff_telegram_username}"
        except Exception as e:
            logging.error(f"Error storing staff tasks in Redis: {e}")
            import traceback
            traceback.print_exc()
            return f"Error storing staff tasks in Redis: {str(e)}"
    
    def get_staff_tasks_from_redis(self, staff_telegram_username):
        """
        Get staff tasks from Redis.
        
        Args:
            staff_telegram_username: Telegram username of the staff member
            
        Returns:
            List of task dictionaries or error message
        """
        try:
            # Get staff information
            staff_list = self.data_manager.get_staff_list()
            
            if not staff_telegram_username.startswith('@'):
                staff_telegram_username = f"@{staff_telegram_username}"
            
            staff = next((s for s in staff_list if s.get("telegram_username") == staff_telegram_username), None)
            
            if not staff:
                return f"Staff member with Telegram username {staff_telegram_username} not found"
            
            staff_id = staff.get("id")
            if not staff_id:
                return f"Staff ID not found for {staff_telegram_username}"
            
            # Get tasks from Redis
            return self.data_manager.get_staff_tasks_from_redis(staff_id)
        except Exception as e:
            logging.error(f"Error getting staff tasks from Redis: {e}")
            import traceback
            traceback.print_exc()
            return f"Error getting staff tasks from Redis: {str(e)}"
    
    def sync_sheet_tasks_with_redis(self, sheet_manager):
        """
        Synchronize tasks for all staff members from Google Sheets with Redis.
        
        Args:
            sheet_manager: Instance of StaffSheetManager for reading sheets
            
        Returns:
            Result message
        """
        try:
            # Get list of staff
            staff_list = self.data_manager.get_staff_list()
            
            results = {}
            
            # For each staff member, load and save tasks
            for staff in staff_list:
                telegram_username = staff.get("telegram_username")
                if not telegram_username:
                    continue
                    
                # Get tasks from Google Sheets
                tasks_result = sheet_manager.read_staff_tasks(telegram_username)
                
                # If result is a string, it means there was an error
                if isinstance(tasks_result, str):
                    results[telegram_username] = {"error": tasks_result}
                    continue
                    
                # Store tasks in Redis
                staff_id = staff.get("id")
                if not staff_id:
                    results[telegram_username] = {"error": "Missing staff ID"}
                    continue
                
                # Convert DataFrame to list of dictionaries for Redis storage
                if hasattr(tasks_result, "to_dict"):
                    tasks_list = tasks_result.to_dict("records")
                    
                    # Store in Redis
                    success = self.data_manager.store_staff_tasks_in_redis(staff_id, tasks_list)
                    results[telegram_username] = {"success": success}
                else:
                    results[telegram_username] = {"error": "Invalid tasks result format"}
            
            # Format report
            success_count = sum(1 for result in results.values() if "success" in result)
            error_count = len(results) - success_count
            
            summary = f"Synchronized {success_count} staff members with Redis, errors: {error_count}"
            
            return summary
        except Exception as e:
            logging.error(f"Error synchronizing tasks with Redis: {e}")
            import traceback
            traceback.print_exc()
            return f"Error synchronizing tasks with Redis: {str(e)}"
