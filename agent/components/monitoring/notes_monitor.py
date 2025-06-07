from datetime import datetime
from .base_monitor import BaseMonitor


class NotesMonitor(BaseMonitor):
    def __init__(self, agent):
        """
        Инициализация с полным доступом к агенту для согласованности
        с другими мониторами
        """
        self.agent = agent
        self.memory_manager = agent.memory_manager
        self.input_formatter = agent.input_formatter

    def get_raw_data(self) -> str:
        """
        Получает релевантные заметки на основе текущего контекста
        Использует временную метку из MonitoringSet для согласованности
        """
        current_context = self._get_current_context()
        memories = self.memory_manager.search_similar(current_context)
        return '. '.join(memories) if memories else ''

    def _get_current_context(self) -> str:
        """
        Формирует текущий контекст для поиска релевантных заметок,
        включая последние сообщения из чата
        """
        chat_context = self.input_formatter.get_formatted_chat()
        timestamp = self.agent.monitoring_set.get_chrono_mark()
        return f'{timestamp}:\n{chat_context}'

    def render(self) -> str:
        """
        Рендерит заметки в XML формат
        Добавляет метаданные о количестве найденных заметок
        """
        content = self.get_raw_data()
        if not content:
            return ''

        notes = content.split('. ')
        formatted_notes = []

        for note in notes:
            if note.strip():
                # Извлекаем ID из конца заметки, если он есть
                if '(ID ' in note:
                    note_text, note_id = note.rsplit('(ID ', 1)
                    note_id = note_id.rstrip(')')
                    s = (f'<note id="{note_id}">\n'
                         f'<content>{note_text.strip()}</content>\n'
                         f'</note>')
                    formatted_notes.append(s)
                else:
                    s = (f'<note>\n'
                         f'<content>{note}</content>\n'
                         f'</note>')
                    formatted_notes.append(s)

        content = '\n'.join(formatted_notes)
        attributes = {
            "count": str(len(notes))
        }

        return self.wrap_in_xml("relevant_notes", f"\n{content}\n", attributes)