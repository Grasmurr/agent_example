import logging
from datetime import datetime
import redis


class InputFormatter:
    def __init__(self, redis_host="localhost", redis_port=6379, redis_password=None):
        """
        Класс для форматирования сообщений чата.

        :param tg_window: Количество последних сообщений для отображения.
        :param redis_host: Хост Redis.
        :param redis_port: Порт Redis.
        :param redis_password: Пароль Redis (если есть).
        """
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True
        )
        self.redis_chat_key = "agent:chat_messages"
        self.redis_inbox_key = "agent:inbox_messages"

    def get_formatted_chat(self) -> str:
        """
        Получает последние сообщения чата из Redis и непрочитанные сообщения.

        :return: Отформатированная строка с историей чата и непрочитанными сообщениями.
        """
        last_messages = self.get_last_messages()
        unseen_messages = self.get_unseen_messages()

        formatted_chat = f'\nTelegram Chat:\n{last_messages}'
        if unseen_messages:
            formatted_chat += f'\n\nUnseen:\n{unseen_messages}'

        return formatted_chat

    def get_last_messages(self, count: int = 15) -> str:
        """
        Получает последние N сообщений из истории чата в Redis.

        :param count: Количество последних сообщений.
        :return: Строка с сообщениями.
        """
        messages = self.redis_client.lrange(self.redis_chat_key, 0, count - 1)
        return '\n'.join(messages) if messages else "No messages"

    def get_unseen_messages(self) -> str:
        """
        Получает все непрочитанные сообщения и очищает inbox.

        :return: Строка с непрочитанными сообщениями.
        """
        messages = self.redis_client.lrange(self.redis_inbox_key, 0, -1)
        self.redis_client.delete(self.redis_inbox_key)  # Очистка после прочтения
        return '\n'.join(messages) if messages else ""

    def format_chat_input(self, task_tool):
        """
        Форматирует входные данные, добавляя невыполненные задачи.

        :param task_tool: Инструмент для управления задачами.
        :return: Отформатированный ввод.
        """
        input_text = self.get_formatted_chat()
        input_text += f'\n\n{task_tool.show_pending_tasks()}'
        return input_text

    def format_final_input(self, input_text, memories):
        """
        Добавляет к вводу воспоминания и временную метку.

        :param input_text: Текущий текст ввода.
        :param memories: Список релевантных воспоминаний.
        :return: Итоговый форматированный ввод.
        """
        if memories:
            input_text = f'\n\n{input_text}\nRelevant notes:\n{". ".join(memories)}'

        input_text = f"{input_text}\n\n{self.get_chrono_mark()}: Think about current situation and act accordingly."
        return input_text

    def get_chrono_mark(self):
        """
        Возвращает текущую временную метку.

        :return: Строка с датой и временем.
        """
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
