import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from .mysql_pandas_tool import SqlPandasTool


class GoogleSheetsTool:
    def __init__(self):
        self.FILE_PATH = os.getenv('GOOGLE_FILE_PATH')
        self.SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
        self.sql_pandas_tool = SqlPandasTool()

    def get_service(self):
        """
        Создаёт/обновляет Google Sheets service на основе service-account credentials.
        """
        creds = service_account.Credentials.from_service_account_file(self.FILE_PATH)
        service = build('sheets', 'v4', credentials=creds)
        return service

    def clear_sheet(self, sheet_name: str) -> str:
        """
        Очищает все данные из указанного листа в Google Sheets.
        """
        try:
            service = self.get_service()
            request = service.spreadsheets().values().clear(
                spreadsheetId=self.SHEET_ID,
                range=f"'{sheet_name}'"
            )
            request.execute()
            return f"Лист '{sheet_name}' очищен."
        except Exception as e:
            return f"Ошибка при очистке листа: {e}"

    def _prepare_value(self, value: Any) -> Any:
        """
        Преобразует значения pandas в формат, подходящий для Google Sheets
        """
        if pd.isna(value) or value is None:
            return ''
        elif isinstance(value, (pd.Timestamp, datetime)):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(value, (np.int64, np.int32)):
            return int(value)
        elif isinstance(value, (np.float64, np.float32)):
            return float(value)
        elif isinstance(value, bool):
            return str(value)
        elif isinstance(value, (list, dict)):
            return str(value)
        return value

    def _prepare_data_for_sheets(self, df: pd.DataFrame) -> list:
        """
        Преобразует DataFrame в список списков для Google Sheets
        с корректной обработкой типов данных
        """
        headers = list(df.columns)
        values = []
        for _, row in df.iterrows():
            processed_row = [self._prepare_value(val) for val in row]
            values.append(processed_row)
        return [headers] + values

    def update_sheet_from_df(self, df_name: str) -> str:
        """
        Загружает данные из DataFrame в Google Sheets.
        Если количество строк меньше количества столбцов,
        автоматически транспонирует DataFrame и переименовывает
        первый столбец в "значение".

        Args:
            df_name: имя DataFrame для загрузки
        """
        if df_name not in self.sql_pandas_tool.dataframes:
            return f"DataFrame '{df_name}' не найден"

        try:
            sheet_name: str = 'ТЕСТ'
            df = self.sql_pandas_tool.dataframes[df_name].copy()

            # Проверяем, нужно ли транспонировать датафрейм
            row_count = len(df)
            col_count = len(df.columns)

            was_transposed = False
            if row_count < col_count:
                # Транспонируем датафрейм, если строк меньше чем столбцов
                df = df.T

                # Переименовываем первый столбец (индекс) с "0" на "значение"
                df = df.reset_index()  # Преобразуем индекс в обычный столбец
                df.columns = ['значение'] + list(df.columns)[1:]  # Переименовываем первый столбец

                was_transposed = True

            values = self._prepare_data_for_sheets(df)
            service = self.get_service()
            self.clear_sheet(sheet_name)

            # Загружаем новые данные
            sheet_range = f"'{sheet_name}'!A1"
            request = service.spreadsheets().values().update(
                spreadsheetId=self.SHEET_ID,
                range=sheet_range,
                valueInputOption='RAW',
                body={'values': values}
            )
            response = request.execute()

            transposed_msg = " (датафрейм был транспонирован, т.к. строк меньше чем столбцов)" if was_transposed else ""

            return (f"Данные из DataFrame '{df_name}' успешно загружены в лист '{sheet_name}'{transposed_msg}\n"
                    f"Обновлено {response['updatedCells']} ячеек")

        except Exception as e:
            return f"Ошибка при обновлении листа: {str(e)}"

    def read_sheet(self, sheet_name: str = 'ТЕСТ') -> str:
        """
        Читает данные из указанного листа Google Sheets.
        Улучшенная версия с обработкой несоответствия количества столбцов.
    
        Args:
            sheet_name: имя листа для чтения (по умолчанию 'ТЕСТ')
    
        Returns:
            Строковое представление данных или сообщение об ошибке
        """
        try:
            service = self.get_service()
            request = service.spreadsheets().values().get(
                spreadsheetId=self.SHEET_ID,
                range=f"'{sheet_name}'"
            )
            response = request.execute()
            values = response.get('values', [])
    
            if not values:
                return "Лист пуст или не содержит данных"
    
            # Найдем максимальное количество столбцов в данных
            max_cols = 0
            for row in values:
                max_cols = max(max_cols, len(row))
            
            # Создаем список заголовков
            if len(values) > 0:
                # Если первая строка короче максимального количества столбцов,
                # дополняем её пустыми значениями
                headers = values[0].copy()
                while len(headers) < max_cols:
                    headers.append(f"Column_{len(headers)+1}")
            else:
                headers = [f"Column_{i+1}" for i in range(max_cols)]
            
            # Подготавливаем данные с одинаковой длиной строк
            normalized_data = []
            for row in values[1:]:  # Пропускаем заголовки
                normalized_row = row.copy()
                # Дополняем короткие строки пустыми значениями
                while len(normalized_row) < max_cols:
                    normalized_row.append('')
                normalized_data.append(normalized_row)
    
            # Создаем DataFrame
            df = pd.DataFrame(normalized_data, columns=headers) if normalized_data else pd.DataFrame(columns=headers)
    
            # Сохраняем прочитанный DataFrame для возможного использования
            df_name = f"sheet_{sheet_name.lower().replace(' ', '_').replace('-', '_')}"
            self.sql_pandas_tool.dataframes[df_name] = df
    
            rows_count = len(df)
            cols_count = len(df.columns) if rows_count > 0 else 0
    
            return (f"Данные успешно прочитаны из листа '{sheet_name}'\n"
                    f"Получено {rows_count} строк × {cols_count} столбцов\n"
                    f"Данные сохранены в DataFrame '{df_name}'")
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Ошибка при чтении листа: {str(e)}"
