import json
import datetime
import redis
import os
import logging
from typing import List, Dict, Any, Optional


class TaskTool:
    def __init__(self):
        # Redis connection
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_password = os.getenv('REDIS_PASSWORD')

        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True
        )
        self.tasks_key = "tasks"  # Key for the sorted set containing all tasks

        # Ensure indexes are set up for tasks
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis data structures if they don't exist"""
        # In Redis, we don't need to create tables like in SQL
        # We'll use a hash for each task, with a unique ID
        # And we'll maintain a sorted set for ordering and searching
        logging.info("Redis connection initialized for TaskTool")

    def _generate_task_id(self) -> int:
        """Generate a new unique task ID"""
        task_id = self.redis_client.incr("task_id_counter")
        return task_id

    def task_key(self, task_id: int) -> str:
        """Generate Redis key for a task"""
        return f"task:{task_id}"

    def create_task(self, description: str) -> str:
        """Create a new task with the given description."""
        try:
            task_id = self._generate_task_id()
            created_at = datetime.datetime.now().isoformat()

            task_data = {
                "id": task_id,
                "description": description,
                "status": "pending",
                "created_at": created_at,
            }

            # Store task in Redis hash
            task_key = self.task_key(task_id)
            self.redis_client.hset(task_key, mapping=task_data)

            # Add to the tasks sorted set for ordering
            # Using creation timestamp as score for natural time ordering
            timestamp = datetime.datetime.fromisoformat(created_at).timestamp()
            self.redis_client.zadd(self.tasks_key, {str(task_id): timestamp})

            return f'The task has been successfully created with ID {task_id}'

        except Exception as e:
            logging.error(f"Error creating task: {e}")
            return f"Failed to create task: {str(e)}"

    def finish_task(self, task_id: int) -> str:
        """Mark a task as finished by its ID."""
        try:
            task_key = self.task_key(int(task_id))

            # Check if task exists
            if not self.redis_client.exists(task_key):
                return f'Can\'t find a task with ID {task_id}!'

            # Get current status
            status = self.redis_client.hget(task_key, "status")

            if status == 'finished':
                return f'Task with ID {task_id} is already finished!'
            elif status == 'canceled':
                return f'Task with ID {task_id} was canceled and cannot be finished!'

            # Update task
            finished_at = datetime.datetime.now().isoformat()
            self.redis_client.hset(task_key, "status", "finished")
            self.redis_client.hset(task_key, "finished_at", finished_at)

            return f'The task with ID {task_id} has been successfully finished!'

        except Exception as e:
            logging.error(f"Error finishing task: {e}")
            return f"Failed to finish task: {str(e)}"

    def cancel_task(self, task_id: int) -> str:
        """Cancel a task by its ID."""
        try:
            task_key = self.task_key(int(task_id))

            # Check if task exists
            if not self.redis_client.exists(task_key):
                return f'Can\'t find a task with ID {task_id}!'

            # Get current status
            status = self.redis_client.hget(task_key, "status")

            if status == 'canceled':
                return f'Task with ID {task_id} is already canceled!'
            elif status == 'finished':
                return f'Task with ID {task_id} was already finished and cannot be canceled!'

            # Update task
            canceled_at = datetime.datetime.now().isoformat()
            self.redis_client.hset(task_key, "status", "canceled")
            self.redis_client.hset(task_key, "canceled_at", canceled_at)

            return f'The task with ID {task_id} has been cancelled'

        except Exception as e:
            logging.error(f"Error canceling task: {e}")
            return f"Failed to cancel task: {str(e)}"

    def show_pending_tasks(self, n=5) -> str:
        """Show pending tasks."""
        try:
            # Get all task IDs from the sorted set
            task_ids = self.redis_client.zrange(self.tasks_key, 0, -1)

            pending_tasks = []

            # For each task ID, check if it's pending
            for task_id in task_ids:
                task_key = self.task_key(int(task_id))
                task_data = self.redis_client.hgetall(task_key)

                if task_data.get("status") == "pending":
                    pending_tasks.append([
                        int(task_data.get("id")),
                        task_data.get("description"),
                        task_data.get("created_at")
                    ])

                    # If we have enough pending tasks, stop
                    if len(pending_tasks) >= int(n):
                        break

            if pending_tasks:
                return f"Current tasks:\n{json.dumps(pending_tasks, indent=4, ensure_ascii=False)}\n"
            else:
                return "There are no pending tasks. Feel free to add tasks to simplify tracking of your activities!"

        except Exception as e:
            logging.error(f"Error retrieving pending tasks: {e}")
            return f"Failed to retrieve pending tasks: {str(e)}"
            
    def check_timeouts(self, timeout_minutes: int = 5) -> str:
        """
        Проверяет все задачи в статусе "pending" и меняет статус на "timeout" 
        для тех, которые находятся в этом статусе более указанного времени.
        
        Args:
            timeout_minutes: Время в минутах, после которого задача считается просроченной
            
        Returns:
            Сообщение о результате операции
        """
        try:
            # Получаем все task IDs из отсортированного набора
            task_ids = self.redis_client.zrange(self.tasks_key, 0, -1)
            
            updated_tasks = 0
            current_time = datetime.datetime.now()
            
            for task_id in task_ids:
                task_key = self.task_key(int(task_id))
                task_data = self.redis_client.hgetall(task_key)
                
                if task_data.get("status") == "pending":
                    # Получаем время создания задачи
                    created_at = datetime.datetime.fromisoformat(task_data.get("created_at"))
                    
                    # Проверяем, прошло ли timeout_minutes с момента создания
                    if (current_time - created_at).total_seconds() > timeout_minutes * 60:
                        # Обновляем статус
                        self.redis_client.hset(task_key, "status", "timeout")
                        self.redis_client.hset(task_key, "timeout_at", current_time.isoformat())
                        updated_tasks += 1
                        logging.info(f"Task {task_id} status changed to timeout")
            
            if updated_tasks > 0:
                return f"Обновлено {updated_tasks} задач со статусом timeout"
            else:
                return "Нет просроченных задач"
            
        except Exception as e:
            logging.error(f"Error checking task timeouts: {e}")
            return f"Failed to check task timeouts: {str(e)}"
