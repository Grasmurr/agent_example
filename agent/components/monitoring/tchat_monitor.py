import logging
from typing import List
from multiprocessing.managers import ListProxy
from .base_monitor import BaseMonitor
import re

class TelegramChatMonitor(BaseMonitor):
    def __init__(self, agent):
        self.input_formatter = agent.input_formatter

    def get_raw_data(self) -> str:
        return self.input_formatter.get_formatted_chat()

    def render(self) -> str:
        message_end_regex = re.compile(r'(.*?): (.*?) \(delivered and read (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)')
        formatted_messages = []

        # Убираем лишние пробелы и переносы строк
        cleaned_data = " ".join(self.get_raw_data().split())

        matches = message_end_regex.findall(cleaned_data)
        for username, text, timestamp in matches:
            try:
                formatted_messages.append(
                    f'<message timestamp="{timestamp}">\n'
                    f'<user>{username.strip()}</user>\n'
                    f'<text>{text.strip()}</text>\n'
                    f'</message>'
                )
            except Exception as e:
                logging.error(f"Error parsing message: {username}: {text}")
                logging.error(f"Error details: {str(e)}")

        content = "\n".join(formatted_messages[::-1])  # Сообщения в порядке убывания времени
        return self.wrap_in_xml("telegram_chat", f"\n{content}\n", {"source": "telegram"})
