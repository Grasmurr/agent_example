from .base_monitor import BaseMonitor
import pandas as pd
import os


class GoogleSheetsMonitor(BaseMonitor):
    def __init__(self, google_sheets_tool):
        """
        Инициализация монитора Google Sheets с ссылкой на Google Sheets инструмент.

        Args:
            google_sheets_tool: Экземпляр класса GoogleSheetsTool
        """
        self.google_sheets_tool = google_sheets_tool
        self.sheet_name = "ВСЕЗАДАЧИ" # os.getenv('GOOGLE_SHEET_NAME', "ВСЕЗАДАЧИ")  # Имя листа по умолчанию для мониторинга

    def get_raw_data(self) -> str:
        """
        Получение данных из Google Sheets.

        Returns:
            Строковое представление данных
        """
        try:
            service = self.google_sheets_tool.get_service()
            request = service.spreadsheets().values().get(
                spreadsheetId=self.google_sheets_tool.SHEET_ID,
                range=f"'{self.sheet_name}'"
            )
            response = request.execute()
            values = response.get('values', [])

            if not values:
                return "Лист пуст или не содержит данных"

            # Создаем DataFrame для форматированного вывода
            df = pd.DataFrame(values[1:], columns=values[0]) if len(values) > 0 else pd.DataFrame()

            # Ограничиваем вывод для монитора
            max_rows = 100  # Максимальное количество строк для отображения
            max_cols = 50  # Максимальное количество столбцов для отображения

            if len(df) > max_rows:
                df = df.head(max_rows)
                footer = f"\n[Показаны первые {max_rows} строк из {len(values) - 1}]"
            else:
                footer = ""

            if len(df.columns) > max_cols:
                df = df.iloc[:, :max_cols]
                footer += f"\n[Показаны первые {max_cols} столбцов из {len(values[0])}]"

            # Форматируем вывод
            if not df.empty:
                return df.to_string(index=False) + footer
            else:
                return "Лист содержит только заголовки: " + ", ".join(values[0])

        except Exception as e:
            return f"Ошибка при чтении листа: {str(e)}"

    def render(self) -> str:
        """
        Рендеринг данных из Google Sheets в XML формате.

        Returns:
            XML представление данных из Google Sheets
        """
        content = self.get_raw_data()

        if "Ошибка при чтении листа" in content or "Лист пуст" in content:
            return ""  # Не показываем монитор, если нет данных или произошла ошибка

        return self.wrap_in_xml(
            "google_sheets_data",
            f"\n{content}\n",
            {"sheet_name": self.sheet_name, "source": "google_sheets"}
        )
