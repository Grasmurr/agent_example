"""
Staff data manager for handling staff data storage and retrieval from Redis.
"""
import os
import json
import logging
import redis
from typing import List, Dict, Any, Optional
from datetime import datetime

class StaffDataManager:
    """
    Manages staff data storage and retrieval from Redis.
    Handles staff list, tasks, and thread IDs.
    """
    
    def __init__(self):
        """Initialize the staff data manager with Redis connection."""
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True
        )
        
        # Redis keys for storing staff data
        self.staff_key = "agent:staff_list"
        self.tasks_key = "agent:staff_tasks"
        self.messages_key = "agent:staff_messages"
        
        # Path to the threads file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.threads_file_path = os.path.join(
            os.path.dirname(os.path.dirname(current_dir)),
            'data', 
            'staff_threads.json'
        )
        
        # Create directory for the threads file if it doesn't exist
        os.makedirs(os.path.dirname(self.threads_file_path), exist_ok=True)
        
        # Load thread data
        self.threads_data = self._load_threads_data()
        
        logging.info("StaffDataManager initialized")
    
    def _load_threads_data(self) -> Dict:
        """
        Load thread data from the JSON file.
        
        Returns:
            Dictionary containing thread data
        """
        try:
            if os.path.exists(self.threads_file_path):
                with open(self.threads_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # Create empty structure if file doesn't exist
                return {"threads": {}}
        except Exception as e:
            logging.error(f"Error loading thread data from file: {e}")
            return {"threads": {}}
    
    def _save_threads_data(self) -> None:
        """Save thread data to the JSON file."""
        try:
            with open(self.threads_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.threads_data, f, indent=2, ensure_ascii=False)
            logging.info(f"Thread data saved to file: {self.threads_file_path}")
        except Exception as e:
            logging.error(f"Error saving thread data to file: {e}")
    
    def initialize_test_data(self) -> None:
        """Initialize test data for staff if none exists."""
        # Check if data already exists
        if self.redis_client.exists(self.staff_key):
            try:
                existing_data = self.redis_client.get(self.staff_key)
                logging.info(f"Existing data in Redis: {existing_data}")
                # Delete existing key for forced reinitialization
                self.redis_client.delete(self.staff_key)
                logging.info("Existing key deleted for data reinitialization")
            except Exception as e:
                logging.error(f"Error attempting to get data from Redis: {e}")
        
        # Staff list test data
        staff_list = [
            {
                "id": 1,
                "full_name": "Попов Роберт Егорович",
                "position": "Разработчик",
                "telegram_username": "@robert_meow",
                "telegram_id": "768787336",
                "google_sheet_name": "Роберт Попов",
                "task_planning_at": "11:00",
                "task_reporting_at": "18:50"
            },
            {
                "id": 2,
                "full_name": "Жагун-Линник Александр Павлович",
                "position": "Технический директор",
                "telegram_username": "@zhagun_linnik",
                "telegram_id": "666873600",
                "google_sheet_name": "Александр Жагун-Линник",
                "task_planning_at": "11:00",
                "task_reporting_at": "16:50"
            },
            {
                "id": 3,
                "full_name": "Ермаков Кирилл Андреевич",
                "position": "Директор",
                "telegram_username": "@CTM_Kirill",
                "telegram_id": "1386410319",
                "google_sheet_name": "Кирилл Ермаков",
                "task_planning_at": "09:00",
                "task_reporting_at": "22:50"
            },
            {
                "id": 4,
                "full_name": "Суханицкий Роман Альбертович",
                "position": "Разработчик",
                "telegram_username": "@Grasmurr",
                "telegram_id": "305378717",
                "google_sheet_name": "Роман Суханицкий",
                "task_planning_at": "11:00",
                "task_reporting_at": "18:50"
            }
        ]
        
        # Save staff list to Redis
        self.redis_client.set(self.staff_key, json.dumps(staff_list))
        
        logging.info("Test staff data initialized")
    
    def get_staff_list(self) -> List[Dict]:
        """
        Get the list of staff from Redis.
        
        Returns:
            List of staff dictionaries
        """
        try:
            staff_json = self.redis_client.get(self.staff_key)
            if not staff_json:
                logging.warning("Staff list in Redis is empty or doesn't exist")
                # Initialize test data
                self.initialize_test_data()
                # Try again
                staff_json = self.redis_client.get(self.staff_key)
                if not staff_json:
                    logging.error("Failed to initialize staff data")
                    return []
            
            staff_list = json.loads(staff_json)
            logging.info(f"Retrieved staff list from Redis: {len(staff_list)} entries")
            
            # Check for required fields
            valid_staff = []
            for staff in staff_list:
                if "telegram_username" not in staff:
                    logging.warning(f"Missing telegram_username for staff: {staff.get('full_name', 'Unknown')}")
                else:
                    valid_staff.append(staff)
            
            if len(valid_staff) != len(staff_list):
                logging.warning(f"Filtered out {len(staff_list) - len(valid_staff)} invalid staff entries")
            
            return staff_list
        except Exception as e:
            logging.error(f"Error retrieving staff list: {e}")
            return []
    
    def get_tasks(self) -> List[Dict]:
        """
        Get the list of tasks from Redis.
        
        Returns:
            List of task dictionaries
        """
        try:
            tasks_json = self.redis_client.get(self.tasks_key)
            if not tasks_json:
                return []
            
            return json.loads(tasks_json)
        except Exception as e:
            logging.error(f"Error retrieving tasks list: {e}")
            return []
    
    def update_task_status(self, task_id: int, new_status: str) -> str:
        """
        Update the status of a task.
        
        Args:
            task_id: ID of the task
            new_status: New status
            
        Returns:
            Result message
        """
        try:
            task_key = f"task:{int(task_id)}"
            
            # Check if task exists
            if not self.redis_client.exists(task_key):
                return f"Can't find a task with ID {task_id}!"
            
            # Get current status
            status = self.redis_client.hget(task_key, "status")
            
            if status == new_status:
                return f"Task with ID {task_id} is already {new_status}!"
            
            # Update task status
            timestamp_field = f"{new_status}_at"
            self.redis_client.hset(task_key, "status", new_status)
            self.redis_client.hset(
                task_key, 
                timestamp_field, 
                datetime.now().isoformat()
            )
            
            return f"Task with ID {task_id} status updated from {status} to {new_status}"
        except Exception as e:
            logging.error(f"Error updating task status: {e}")
            return f"Error updating task status: {str(e)}"
    
    def get_employee_thread_id(self, staff_telegram: str) -> Optional[int]:
        """
        Get thread ID for a staff member.
        
        Args:
            staff_telegram: Telegram username
            
        Returns:
            Thread ID or None if not found
        """
        try:
            thread_id = self.threads_data.get("threads", {}).get(staff_telegram)
            return int(thread_id) if thread_id else None
        except Exception as e:
            logging.error(f"Error retrieving thread ID for {staff_telegram}: {e}")
            return None
    
    def save_employee_thread_id(self, staff_telegram: str, thread_id: int) -> None:
        """
        Save thread ID for a staff member.
        
        Args:
            staff_telegram: Telegram username
            thread_id: Thread ID
        """
        try:
            if "threads" not in self.threads_data:
                self.threads_data["threads"] = {}
            
            self.threads_data["threads"][staff_telegram] = thread_id
            self._save_threads_data()
            
            logging.info(f"Saved thread ID {thread_id} for {staff_telegram}")
        except Exception as e:
            logging.error(f"Error saving thread ID for {staff_telegram}: {e}")
    
    def add_notification(self, staff_telegram: str) -> None:
        """
        Add notification for new message from staff.
        
        Args:
            staff_telegram: Telegram username
        """
        try:
            messages_json = self.redis_client.get(self.messages_key)
            messages = json.loads(messages_json) if messages_json else []
            
            # Filter messages, excluding those without telegram_username
            valid_messages = [m for m in messages if "telegram_username" in m]
            
            # Check if notification already exists
            if not any(m["telegram_username"] == staff_telegram for m in valid_messages):
                # Add new notification
                valid_messages.append({
                    "telegram_username": staff_telegram,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Save updated notification list
                self.redis_client.set(self.messages_key, json.dumps(valid_messages))
        except Exception as e:
            logging.error(f"Error adding notification: {e}")
    
    def remove_notification(self, staff_telegram: str) -> None:
        """
        Remove notification for staff.
        
        Args:
            staff_telegram: Telegram username
        """
        try:
            messages_json = self.redis_client.get(self.messages_key)
            if not messages_json:
                return
            
            messages = json.loads(messages_json)
            
            # Filter messages, excluding those without telegram_username
            valid_messages = [m for m in messages if "telegram_username" in m]
            
            # Remove notification for the specified staff
            updated_messages = [m for m in valid_messages if m["telegram_username"] != staff_telegram]
            
            # Save updated notification list
            self.redis_client.set(self.messages_key, json.dumps(updated_messages))
        except Exception as e:
            logging.error(f"Error removing notification: {e}")
    
    def get_notifications(self) -> List[Dict]:
        """
        Get list of notifications.
        
        Returns:
            List of notification dictionaries
        """
        try:
            messages_json = self.redis_client.get(self.messages_key)
            if not messages_json:
                return []
            
            messages = json.loads(messages_json)
            
            # Filter messages, excluding those without telegram_username
            valid_messages = [m for m in messages if "telegram_username" in m]
            
            return valid_messages
        except Exception as e:
            logging.error(f"Error retrieving notifications: {e}")
            return []
    
    def store_staff_tasks_in_redis(self, staff_id: int, tasks: List[Dict]) -> bool:
        """
        Store staff tasks in Redis.
        
        Args:
            staff_id: Staff ID
            tasks: List of task dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Key for storing staff tasks
            staff_tasks_key = f"agent:staff_tasks:{staff_id}"
            
            # If tasks is empty, clear the key
            if not tasks:
                self.redis_client.delete(staff_tasks_key)
                return True
            
            # Convert tasks to JSON strings for storage
            tasks_dict = {}
            for i, task in enumerate(tasks):
                task_id = task.get("id", f"{staff_id}_{i}")
                tasks_dict[task_id] = json.dumps(task, ensure_ascii=False)
            
            # Update Redis
            self.redis_client.delete(staff_tasks_key)
            if tasks_dict:
                self.redis_client.hset(staff_tasks_key, mapping=tasks_dict)
            
            # Update mapping for quick lookup
            self.redis_client.hset(
                "agent:staff_tasks_mapping",
                f"@staff_{staff_id}",
                staff_id
            )
            
            return True
        except Exception as e:
            logging.error(f"Error storing staff tasks in Redis: {e}")
            return False
    
    def get_staff_tasks_from_redis(self, staff_id: int) -> List[Dict]:
        """
        Get staff tasks from Redis.
        
        Args:
            staff_id: Staff ID
            
        Returns:
            List of task dictionaries
        """
        try:
            # Key for storing staff tasks
            staff_tasks_key = f"agent:staff_tasks:{staff_id}"
            
            # Get all tasks from Redis
            tasks_dict = self.redis_client.hgetall(staff_tasks_key)
            
            if not tasks_dict:
                return []
            
            # Convert JSON strings to dictionaries
            tasks = []
            for task_id, task_json in tasks_dict.items():
                try:
                    task = json.loads(task_json)
                    tasks.append(task)
                except json.JSONDecodeError:
                    logging.warning(f"Unable to decode task {task_id}: {task_json}")
            
            # Sort tasks by status and date
            tasks.sort(key=lambda x: (x.get("status", ""), x.get("created_at", "")))
            
            return tasks
        except Exception as e:
            logging.error(f"Error retrieving staff tasks from Redis: {e}")
            return []
    
    def update_task_status_in_redis(self, task_id: str, new_status: str) -> str:
        """
        Update task status in Redis.
        
        Args:
            task_id: Task ID
            new_status: New status
            
        Returns:
            Result message
        """
        try:
            # Parse task_id to get staff_id
            if "_" not in task_id:
                return f"Invalid task ID format: {task_id}"
            
            staff_id = task_id.split("_")[0]
            
            # Key for storing staff tasks
            staff_tasks_key = f"agent:staff_tasks:{staff_id}"
            
            # Get task from Redis
            task_json = self.redis_client.hget(staff_tasks_key, task_id)
            
            if not task_json:
                return f"Task with ID {task_id} not found in Redis"
            
            # Update status
            try:
                task = json.loads(task_json)
                old_status = task.get("status", "unknown")
                task["status"] = new_status
                task["updated_at"] = datetime.now().isoformat()
                
                # Save updated task to Redis
                self.redis_client.hset(
                    staff_tasks_key,
                    task_id,
                    json.dumps(task, ensure_ascii=False)
                )
                
                return f"Task status changed from '{old_status}' to '{new_status}'"
            except json.JSONDecodeError:
                return f"Unable to decode task {task_id}: {task_json}"
        except Exception as e:
            logging.error(f"Error updating task status in Redis: {e}")
            return f"Error updating task status in Redis: {str(e)}"
