import logging
import re
import time
from datetime import datetime, timedelta
import uuid
import threading
import ast
import traceback
import redis
import json
import os

class TimerTool:
    """Tool for creating and managing timers with flexible scheduling options."""
    
    def __init__(self, agent=None):
        """
        Initialize the timer tool with Redis for persistence.
        
        Args:
            agent: Reference to the agent instance (optional)
        """
        self.agent = agent
        self.timers = {}  # In-memory timers
        self.timer_threads = {}  # Running timer threads
        
        # Redis for persistence
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True
        )
        self.redis_timers_key = "agent:timers"
        
        # Load existing timers from Redis
        self._load_timers_from_redis()
        
        # Start background thread for timer management
        self.is_running = True
        self.timer_check_thread = threading.Thread(target=self._timer_check_loop)
        self.timer_check_thread.daemon = True
        self.timer_check_thread.start()
        
        logging.info("TimerTool initialized successfully")
    
    def create_timer(self, time_spec: str, name: str = None, 
                     action: str = None, procedure: str = None) -> str:
        """
        Create a new timer with the specified settings.
        
        Args:
            time_spec: Time specification (e.g., "через 5 минут", "каждые 2 часа", "в 15:30")
            name: Optional name for the timer
            action: Optional action instruction to provide when timer activates
            procedure: Optional Python code to execute when timer activates
            
        Returns:
            Timer ID and confirmation message
        """
        try:
            # Validate procedure code if provided
            if procedure:
                self._validate_python_code(procedure)
            
            # Generate timer ID and name if not provided
            timer_id = str(uuid.uuid4())[:8]
            if not name:
                name = f"Timer-{timer_id}"
            
            # Parse time specification
            next_run, is_recurring, recurrence_interval = self._parse_time_spec(time_spec)
            
            if next_run is None:
                return f"Ошибка: Не удалось разобрать спецификацию времени '{time_spec}'"
            
            # Create timer object
            timer = {
                "id": timer_id,
                "name": name,
                "time_spec": time_spec,
                "next_run": next_run.timestamp(),
                "is_recurring": is_recurring,
                "recurrence_interval": recurrence_interval,
                "action": action,
                "procedure": procedure,
                "created_at": datetime.now().timestamp(),
                "status": "active"
            }
            
            # Store timer
            self.timers[timer_id] = timer
            self._save_timer_to_redis(timer)
            
            # Format response based on timer type
            if is_recurring:
                recurrence_text = self._format_recurrence_interval(recurrence_interval)
                return f"Повторяющийся таймер '{name}' (ID: {timer_id}) создан. Первый запуск в {next_run.strftime('%Y-%m-%d %H:%M:%S')}, затем {recurrence_text}."
            else:
                return f"Одноразовый таймер '{name}' (ID: {timer_id}) создан. Запустится в {next_run.strftime('%Y-%m-%d %H:%M:%S')}."
            
        except Exception as e:
            logging.error(f"Error creating timer: {e}")
            return f"Ошибка создания таймера: {str(e)}"
    
    def list_timers(self) -> str:
        """
        List all active timers.
        
        Returns:
            Formatted string with timer information
        """
        active_timers = {id: timer for id, timer in self.timers.items() 
                        if timer["status"] == "active"}
        
        if not active_timers:
            return "Нет активных таймеров."
        
        result = []
        result.append(f"Активные таймеры ({len(active_timers)}):")
        
        for timer_id, timer in active_timers.items():
            next_run = datetime.fromtimestamp(timer["next_run"])
            now = datetime.now()
            time_left = next_run - now
            
            if time_left.total_seconds() < 0:
                time_left_str = "должен сработать"
            else:
                days = time_left.days
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                time_left_parts = []
                if days > 0:
                    time_left_parts.append(f"{days}д")
                if hours > 0 or days > 0:
                    time_left_parts.append(f"{hours}ч")
                if minutes > 0 or hours > 0 or days > 0:
                    time_left_parts.append(f"{minutes}м")
                time_left_parts.append(f"{seconds}с")
                
                time_left_str = " ".join(time_left_parts)
            
            timer_type = "Повторяющийся" if timer["is_recurring"] else "Одноразовый"
            has_action = "Да" if timer["action"] else "Нет" 
            has_procedure = "Да" if timer["procedure"] else "Нет"
            
            result.append(f"ID: {timer_id} | Имя: {timer['name']} | Тип: {timer_type}")
            result.append(f"  Следующий запуск: {next_run.strftime('%Y-%m-%d %H:%M:%S')} ({time_left_str})")
            result.append(f"  Действие: {has_action} | Процедура: {has_procedure}")
            result.append("")
        
        return "\n".join(result)
    
    def cancel_timer(self, timer_id: str) -> str:
        """
        Cancel a timer by its ID.
        
        Args:
            timer_id: ID of the timer to cancel
            
        Returns:
            Confirmation message
        """
        if timer_id not in self.timers:
            return f"Таймер с ID {timer_id} не найден."
        
        timer = self.timers[timer_id]
        timer["status"] = "cancelled"
        self._save_timer_to_redis(timer)
        
        # Stop the thread if running
        if timer_id in self.timer_threads:
            # We can't really stop threads in Python, but we can mark them for cleanup
            self.timer_threads[timer_id] = None
        
        return f"Таймер '{timer['name']}' (ID: {timer_id}) был отменен."
    
    def get_timer_details(self, timer_id: str) -> str:
        """
        Get detailed information about a specific timer.
        
        Args:
            timer_id: ID of the timer
            
        Returns:
            Formatted string with timer details
        """
        if timer_id not in self.timers:
            return f"Таймер с ID {timer_id} не найден."
        
        timer = self.timers[timer_id]
        next_run = datetime.fromtimestamp(timer["next_run"])
        created_at = datetime.fromtimestamp(timer["created_at"])
        
        result = [f"Детали таймера с ID: {timer_id}"]
        result.append(f"Имя: {timer['name']}")
        result.append(f"Статус: {timer['status']}")
        result.append(f"Создан: {created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        result.append(f"Следующий запуск: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        result.append(f"Спецификация времени: {timer['time_spec']}")
        result.append(f"Тип: {'Повторяющийся' if timer['is_recurring'] else 'Одноразовый'}")
        
        if timer["is_recurring"]:
            recurrence_text = self._format_recurrence_interval(timer["recurrence_interval"])
            result.append(f"Повторение: {recurrence_text}")
        
        result.append(f"Имеет действие: {'Да' if timer['action'] else 'Нет'}")
        result.append(f"Имеет процедуру: {'Да' if timer['procedure'] else 'Нет'}")
        
        if timer["action"]:
            result.append("\nДействие:")
            result.append(timer["action"])
        
        if timer["procedure"]:
            result.append("\nПроцедура:")
            result.append(timer["procedure"])
        
        return "\n".join(result)
    
    def edit_timer(self, timer_id: str, time_spec: str = None, name: str = None,
                  action: str = None, procedure: str = None) -> str:
        """
        Edit an existing timer.
        
        Args:
            timer_id: ID of the timer to edit
            time_spec: New time specification (optional)
            name: New name for the timer (optional)
            action: New action instruction (optional)
            procedure: New Python code to execute (optional)
            
        Returns:
            Confirmation message
        """
        if timer_id not in self.timers:
            return f"Таймер с ID {timer_id} не найден."
        
        timer = self.timers[timer_id]
        
        # Only validate procedure if it's being updated
        if procedure is not None:
            try:
                self._validate_python_code(procedure)
                timer["procedure"] = procedure
            except Exception as e:
                return f"Ошибка валидации кода процедуры: {str(e)}"
        
        # Update other fields if provided
        if name is not None:
            timer["name"] = name
        
        if action is not None:
            timer["action"] = action
        
        # Update time specification if provided
        if time_spec is not None:
            next_run, is_recurring, recurrence_interval = self._parse_time_spec(time_spec)
            
            if next_run is None:
                return f"Ошибка: Не удалось разобрать спецификацию времени '{time_spec}'"
            
            timer["time_spec"] = time_spec
            timer["next_run"] = next_run.timestamp()
            timer["is_recurring"] = is_recurring
            timer["recurrence_interval"] = recurrence_interval
        
        # Save updated timer
        self._save_timer_to_redis(timer)
        
        return f"Таймер '{timer['name']}' (ID: {timer_id}) был обновлен."
    
    def wake_up_agent(self) -> str:
        """
        Wake up the agent if it's in a sleep state.
        
        Returns:
            Confirmation message
        """
        if not self.agent:
            return "Ошибка: Нет доступа к агенту"
        
        # Add a wakeup message to the agent's inbox
        wakeup_message = f"\nПробуждение агента таймером (delivered and read {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
        self.agent.add_inbox_message(wakeup_message)
        
        return "Агент пробужден"
    
    def _parse_time_spec(self, time_spec: str):
        """
        Parse time specification string into actual datetime objects.
        
        Args:
            time_spec: Time specification string
            
        Returns:
            Tuple of (next_run_datetime, is_recurring, recurrence_interval)
        """
        now = datetime.now()
        
        # Case 1: Relative time - "через X время"
        if "через" in time_spec.lower():
            return self._parse_relative_time(time_spec, now)
        
        # Case 2: Recurring time - "каждые X время"
        elif "кажд" in time_spec.lower():
            return self._parse_recurring_time(time_spec, now)
        
        # Case 3: Absolute time - "в XX:XX"
        elif "в " in time_spec.lower():
            return self._parse_absolute_time(time_spec, now)
        
        # Try to guess the format
        else:
            # Try each parser in sequence
            for parser in [self._parse_relative_time, self._parse_recurring_time, self._parse_absolute_time]:
                try:
                    result = parser(time_spec, now)
                    if result[0] is not None:
                        return result
                except:
                    continue
                    
            # If all parsers fail, return None
            return None, False, None
    
    def _parse_relative_time(self, time_spec: str, now: datetime):
        """Parse relative time specification like 'через 5 минут'"""
        # Extract the time part after "через"
        match = re.search(r'через\s+(.*)', time_spec.lower())
        if match:
            time_part = match.group(1)
        else:
            time_part = time_spec
        
        # Parse time components
        seconds = 0
        
        # Match patterns like "5 минут", "2 часа", etc.
        time_patterns = [
            (r'(\d+)\s*(?:секунд|сек)', 1),               # Seconds
            (r'(\d+)\s*(?:минут|мин)', 60),               # Minutes
            (r'(\d+)\s*(?:час|часов|ч)', 3600),           # Hours
            (r'(\d+)\s*(?:день|дня|дней|д)', 86400),      # Days
            (r'(\d+)\s*(?:недел|неделя|недель)', 604800), # Weeks
            (r'(\d+)\s*(?:месяц|месяца|месяцев)', 2592000), # Months (approx)
            (r'(\d+)\s*(?:год|года|лет)', 31536000),      # Years (approx)
        ]
        
        for pattern, multiplier in time_patterns:
            for match in re.finditer(pattern, time_part):
                value = int(match.group(1))
                seconds += value * multiplier
        
        if seconds == 0:
            return None, False, None
        
        next_run = now + timedelta(seconds=seconds)
        return next_run, False, None
    
    def _parse_recurring_time(self, time_spec: str, now: datetime):
        """Parse recurring time specification like 'каждые 10 минут'"""
        # Extract the time part after "каждые"
        match = re.search(r'кажд(?:ые|ый|ое|ая)\s+(.*)', time_spec.lower())
        if match:
            time_part = match.group(1)
        else:
            time_part = time_spec
        
        # Parse time components
        seconds = 0
        
        # Match patterns like "5 минут", "2 часа", etc.
        time_patterns = [
            (r'(\d+)\s*(?:секунд|сек)', 1),               # Seconds
            (r'(\d+)\s*(?:минут|мин)', 60),               # Minutes
            (r'(\d+)\s*(?:час|часов|ч)', 3600),           # Hours
            (r'(\d+)\s*(?:день|дня|дней|д)', 86400),      # Days
            (r'(\d+)\s*(?:недел|неделя|недель)', 604800), # Weeks
            (r'(\d+)\s*(?:месяц|месяца|месяцев)', 2592000), # Months (approx)
            (r'(\d+)\s*(?:год|года|лет)', 31536000),      # Years (approx)
        ]
        
        for pattern, multiplier in time_patterns:
            for match in re.finditer(pattern, time_part):
                value = int(match.group(1))
                seconds += value * multiplier
        
        if seconds == 0:
            return None, False, None
        
        next_run = now + timedelta(seconds=seconds)
        return next_run, True, seconds
    
    def _parse_absolute_time(self, time_spec: str, now: datetime):
        """Parse absolute time specification like 'в 15:30'"""
        # Extract time from the specification
        match = re.search(r'в\s+(\d{1,2})(?::(\d{2}))?', time_spec.lower())
        if not match:
            return None, False, None
        
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        
        # Create datetime for today at specified time
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If the time is already past for today, schedule for tomorrow
        if target_time <= now:
            target_time += timedelta(days=1)
        
        # Check if this is a daily recurring timer
        is_recurring = "ежедневно" in time_spec.lower() or "каждый день" in time_spec.lower()
        recurrence_interval = 86400 if is_recurring else None  # 24 hours in seconds
        
        return target_time, is_recurring, recurrence_interval
    
    def _format_recurrence_interval(self, seconds: int) -> str:
        """Format a recurrence interval in seconds to human-readable form"""
        if seconds is None:
            return "неизвестный интервал"
            
        if seconds < 60:
            return f"каждые {seconds} секунд"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"каждые {minutes} минут{'у' if minutes == 1 else ('ы' if minutes < 5 else '')}"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"каждые {hours} час{'a' if 1 < hours < 5 else 'ов' if hours >= 5 else ''}"
        elif seconds < 604800:
            days = seconds // 86400
            return f"каждые {days} {'день' if days == 1 else 'дня' if days < 5 else 'дней'}"
        elif seconds < 2592000:
            weeks = seconds // 604800
            return f"каждые {weeks} {'неделю' if weeks == 1 else 'недели' if weeks < 5 else 'недель'}"
        elif seconds < 31536000:
            months = seconds // 2592000
            return f"каждые {months} {'месяц' if months == 1 else 'месяца' if months < 5 else 'месяцев'}"
        else:
            years = seconds // 31536000
            return f"каждые {years} {'год' if years == 1 else 'года' if years < 5 else 'лет'}"
    
    def _validate_python_code(self, code: str):
        """
        Validate that the provided Python code is syntactically correct.
        
        Args:
            code: Python code to validate
            
        Raises:
            SyntaxError: If the code has syntax errors
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            line_no = e.lineno
            offset = e.offset
            line = code.split('\n')[line_no-1] if line_no <= len(code.split('\n')) else ""
            
            # Create an error message with the problematic line highlighted
            error_msg = f"Синтаксическая ошибка в строке {line_no}, позиция {offset}:\n"
            error_msg += line + "\n"
            error_msg += " " * (offset-1) + "^" if offset > 0 else ""
            
            raise SyntaxError(error_msg)
    
    def _load_timers_from_redis(self):
        """Load saved timers from Redis"""
        try:
            timers_json = self.redis_client.get(self.redis_timers_key)
            if timers_json:
                timers_dict = json.loads(timers_json)
                self.timers = timers_dict
                logging.info(f"Loaded {len(self.timers)} timers from Redis")
                
                # Update next run time for recurring timers that missed executions
                self._update_missed_recurring_timers()
            else:
                self.timers = {}
                logging.info("No saved timers found in Redis")
        except Exception as e:
            logging.error(f"Error loading timers from Redis: {e}")
            self.timers = {}
    
    def _update_missed_recurring_timers(self):
        """Update next run time for recurring timers that missed executions"""
        now = datetime.now().timestamp()
        
        for timer_id, timer in self.timers.items():
            if timer["status"] != "active" or not timer["is_recurring"]:
                continue
                
            next_run = timer["next_run"]
            interval = timer["recurrence_interval"]
            
            # If the timer's next run time is in the past, update it to the next appropriate time
            if next_run < now and interval:
                # Calculate how many intervals have passed
                missed_intervals = int((now - next_run) // interval) + 1
                
                # Update to the next future run time
                new_next_run = next_run + (missed_intervals * interval)
                timer["next_run"] = new_next_run
                
                logging.info(f"Updated missed recurring timer {timer_id}, next run at {datetime.fromtimestamp(new_next_run)}")
    
    def _save_timer_to_redis(self, timer):
        """Save a timer to Redis"""
        try:
            # Update the timer in the in-memory dictionary
            self.timers[timer["id"]] = timer
            
            # Save the entire timers dictionary to Redis
            timers_json = json.dumps(self.timers)
            self.redis_client.set(self.redis_timers_key, timers_json)
        except Exception as e:
            logging.error(f"Error saving timer to Redis: {e}")
    
    def _timer_check_loop(self):
        """Background thread that checks for timers to execute"""
        while self.is_running:
            now = datetime.now().timestamp()
            
            # Find timers that should execute
            for timer_id, timer in list(self.timers.items()):
                if timer["status"] != "active":
                    continue
                    
                next_run = timer["next_run"]
                
                # Check if timer should run
                if next_run <= now:
                    # Execute timer in a separate thread
                    thread = threading.Thread(
                        target=self._execute_timer,
                        args=(timer_id,)
                    )
                    thread.daemon = True
                    thread.start()
                    
                    self.timer_threads[timer_id] = thread
                    
                    logging.info(f"Started execution thread for timer {timer_id}")
            
            # Sleep for a short period to avoid high CPU usage
            time.sleep(1)
    
    def _execute_timer(self, timer_id):
        """Execute a specific timer"""
        try:
            timer = self.timers.get(timer_id)
            if not timer or timer["status"] != "active":
                return
                
            logging.info(f"Executing timer {timer_id}: {timer['name']}")
            
            # Execute procedure if provided
            if timer["procedure"]:
                try:
                    # Create a globals dictionary with some useful variables
                    globals_dict = {
                        'agent': self.agent,
                        'timer_id': timer_id,
                        'timer_name': timer['name'],
                        'datetime': datetime,
                        'time': time,
                        'logging': logging
                    }
                    
                    # Execute the procedure
                    exec(timer["procedure"], globals_dict)
                    logging.info(f"Successfully executed procedure for timer {timer_id}")
                except Exception as e:
                    logging.error(f"Error executing procedure for timer {timer_id}: {e}")
                    logging.error(traceback.format_exc())
            
            # Handle action if provided
            if timer["action"] and self.agent:
                try:
                    # MODIFIED PART: Create a task directly instead of adding to inbox
                    if hasattr(self.agent.toolset, "task_tool"):
                        task_description = f"Таймер '{timer['name']}' активирован: {timer['action']}"
                        task_result = self.agent.toolset.task_tool.create_task(task_description)
                        logging.info(f"Created task from timer {timer_id}: {task_result}")
                    else:
                        # Fallback to old method if task_tool not available
                        action_message = f"\nТаймер '{timer['name']}' активирован с действием: {timer['action']} (delivered and read {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
                        self.agent.add_inbox_message(action_message)
                        self.agent.store_inbox_message(action_message)
                        logging.info(f"Added action from timer {timer_id} to agent inbox")
                except Exception as e:
                    logging.error(f"Error handling action for timer {timer_id}: {e}")
            
            # Update recurring timer
            if timer["is_recurring"] and timer["recurrence_interval"]:
                # Calculate next run time
                next_run = timer["next_run"] + timer["recurrence_interval"]
                
                # If next run is already in the past (might happen if the agent was off),
                # adjust to the next appropriate time
                now = datetime.now().timestamp()
                if next_run < now:
                    missed_intervals = int((now - next_run) // timer["recurrence_interval"]) + 1
                    next_run = timer["next_run"] + (missed_intervals * timer["recurrence_interval"])
                
                timer["next_run"] = next_run
                self._save_timer_to_redis(timer)
                logging.info(f"Updated recurring timer {timer_id}, next run at {datetime.fromtimestamp(next_run)}")
            else:
                # Mark one-time timer as completed
                timer["status"] = "completed"
                self._save_timer_to_redis(timer)
                logging.info(f"Marked one-time timer {timer_id} as completed")
        
        except Exception as e:
            logging.error(f"Error in timer execution thread for timer {timer_id}: {e}")
            logging.error(traceback.format_exc())
