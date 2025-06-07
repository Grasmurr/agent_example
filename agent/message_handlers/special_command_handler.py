import logging
import os
from typing import Dict, Any

from .base_handler import BaseMessageHandler


class SpecialCommandHandler(BaseMessageHandler):
    """
    Обработчик специальных команд, таких как /send_history.
    """
    
    # Добавить в SpecialCommandHandler.can_handle:
    def can_handle(self, message: Dict[str, Any]) -> bool:
        """
        Проверяет, содержит ли сообщение специальную команду.
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            True, если сообщение содержит специальную команду
        """
        return 'text' in message and (
            message['text'].startswith('/send_history') or
            message['text'].startswith('/sync_tasks') or 
            message['text'].startswith('/redis_tasks')
        )
    
    # Добавить в SpecialCommandHandler.handle:
    def handle(self, data: Dict[str, Any]) -> bool:
        """
        Обрабатывает специальную команду.
        
        Args:
            data: Данные сообщения
            
        Returns:
            True, если сообщение было успешно обработано
        """
        message = data['message']
        command = message['text'].split()[0]
        
        if command == '/send_history':
            # Обрабатываем команду /send_history
            history_text = '\n'.join([str(msg) for msg in self.agent.history])
            with open('history.txt', 'w') as file:
                file.write(history_text)
    
            self.agent.toolset.tg_tool.send_file(
                chat_id=message['chat']['id'],
                document=open('history.txt', 'rb'),
                caption='Here is the history of messages.',
                message_thread_id=message.get('message_thread_id')
            )
            os.remove('history.txt')
            return True
        
        elif command == '/sync_tasks':
            # Обрабатываем команду синхронизации задач с Redis
            if hasattr(self.agent.toolset, "staff_tool"):
                result = self.agent.toolset.staff_tool.sync_sheet_tasks_with_redis()
                
                self.agent.toolset.tg_tool.send_msg(
                    chat_id=message['chat']['id'],
                    text=f"Результат синхронизации задач с Redis:\n\n{result}",
                    message_thread_id=message.get('message_thread_id')
                )
                return True
            else:
                self.agent.toolset.tg_tool.send_msg(
                    chat_id=message['chat']['id'],
                    text="Ошибка: StaffTool не инициализирован",
                    message_thread_id=message.get('message_thread_id')
                )
                return True
                
        elif command == '/redis_tasks':
            # Обрабатываем команду получения задач из Redis
            parts = message['text'].split()
            
            if len(parts) < 2:
                self.agent.toolset.tg_tool.send_msg(
                    chat_id=message['chat']['id'],
                    text="Использование: /redis_tasks @username",
                    message_thread_id=message.get('message_thread_id')
                )
                return True
                
            username = parts[1]
            if not username.startswith('@'):
                username = f"@{username}"
                
            if hasattr(self.agent.toolset, "staff_tool"):
                tasks = self.agent.toolset.staff_tool.get_staff_tasks_from_redis(username)
                
                if isinstance(tasks, list):
                    if not tasks:
                        result_text = f"Задач для {username} в Redis не найдено"
                    else:
                        task_strings = []
                        for task in tasks:
                            task_desc = task.get('task', 'Нет описания')
                            task_status = task.get('status', 'неизвестно')
                            task_id = task.get('id', 'нет ID')
                            task_strings.append(f"ID: {task_id}\nЗадача: {task_desc}\nСтатус: {task_status}\n")
                        
                        result_text = f"Задачи для {username} из Redis ({len(tasks)}):\n\n" + "\n".join(task_strings)
                else:
                    result_text = f"Ошибка получения задач: {tasks}"
                    
                self.agent.toolset.tg_tool.send_msg(
                    chat_id=message['chat']['id'],
                    text=result_text,
                    message_thread_id=message.get('message_thread_id')
                )
                return True
            else:
                self.agent.toolset.tg_tool.send_msg(
                    chat_id=message['chat']['id'],
                    text="Ошибка: StaffTool не инициализирован",
                    message_thread_id=message.get('message_thread_id')
                )
                return True
        
        return False