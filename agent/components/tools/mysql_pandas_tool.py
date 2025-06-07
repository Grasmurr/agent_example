import mysql.connector
import pandas as pd
import os
import json
from typing import Optional, Dict
import logging
from datetime import datetime, date, time
import decimal


class SqlPandasTool:
    def __init__(self):
        self.dataframes: Dict[str, pd.DataFrame] = {}

    def _get_connection(self):
        """Creates MySQL connection using environment variables"""
        return mysql.connector.connect(
            host=os.environ['MYSQL_HOST'],
            port=int(os.environ.get('MYSQL_PORT', 3306)),
            user=os.environ['MYSQL_USER'],
            password=os.environ['MYSQL_PASSWORD'],
            database=os.environ['MYSQL_DATABASE'],
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )

    def _json_serializer(self, obj):
        """Custom JSON serializer for non-serializable types"""
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        elif isinstance(obj, time):
            return obj.strftime("%H:%M:%S")
        elif isinstance(obj, decimal.Decimal):
            return float(obj)
        return str(obj)

    def query_to_df(self, sql: str, df_name: str = "default") -> str:
        """
        Executes SQL query and creates a pandas DataFrame from results.
        Args:
            sql: SQL query to execute (read-only)
            df_name: name for the resulting DataFrame
        Returns:
            String description of created DataFrame
        """
        # Validate query is read-only
        if not sql.lower().strip().startswith(('select', 'show', 'describe', 'desc', 'explain')):
            return "Error: Only read-only queries are allowed"

        try:
            # Execute query
            conn = self._get_connection()
            df = pd.read_sql(sql, conn)

            # Store DataFrame
            self.dataframes[df_name] = df

            # Return info about created DataFrame
            info = (f"Created DataFrame '{df_name}' with shape {df.shape}\n"
                    f"Columns: {list(df.columns)}\n"
                    f"Sample data:\n{df.head().to_string()}")

            return info

        except Exception as e:
            return f"Error executing query: {str(e)}"

        finally:
            if 'conn' in locals():
                conn.close()


    def merge_dataframes(self, df_names: list, output_df_name: str, format: str = 'vertical') -> str:
        """
        Объединяет несколько датафреймов в один новый.

        Args:
            df_names: Список имен датафреймов для объединения
            output_df_name: Имя для нового объединенного датафрейма
            format: Способ объединения - 'vertical' (строки под строками) или
                    'horizontal' (столбцы рядом со столбцами)

        Returns:
            Строка с результатом операции
        """
        try:
            # Проверяем существование всех датафреймов
            dfs_to_merge = []
            for df_name in df_names:
                if df_name not in self.dataframes:
                    return f"DataFrame '{df_name}' не найден"
                dfs_to_merge.append(self.dataframes[df_name])

            # Если список пуст
            if not dfs_to_merge:
                return "Нет датафреймов для объединения"

            # Объединяем датафреймы
            if format.lower() == 'vertical':
                # Объединение по строкам (одна таблица под другой)
                result_df = pd.concat(dfs_to_merge, ignore_index=True)
            elif format.lower() == 'horizontal':
                # Объединение по столбцам (одна таблица рядом с другой)
                result_df = pd.concat(dfs_to_merge, axis=1)
            else:
                return f"Неизвестный формат объединения: {format}. Используйте 'vertical' или 'horizontal'."

            # Сохраняем результат в новый датафрейм
            self.dataframes[output_df_name] = result_df

            # Возвращаем информацию о результате
            return f"Объединены датафреймы {df_names} в '{output_df_name}' с {result_df.shape[0]} строками и {result_df.shape[1]} столбцами"

        except Exception as e:
            return f"Ошибка при объединении датафреймов: {str(e)}"


    def clear_all_dataframes(self) -> str:
        """
        Удаляет все датафреймы из памяти.

        Returns:
            Строка с результатом операции
        """
        try:
            count = len(self.dataframes)
            self.dataframes.clear()
            return f"Удалены все датафреймы (всего {count})"

        except Exception as e:
            return f"Ошибка при очистке датафреймов: {str(e)}"


    def execute_pandas(self, command: str) -> str:
        """
        Executes pandas command on stored DataFrames.
        Args:
            command: pandas command to execute (e.g. "df_name.head()")
        Returns:
            String result of command execution
        """
        try:
            # Create local variables for all stored DataFrames
            local_vars = {name: df for name, df in self.dataframes.items()}
            local_vars['pd'] = pd

            # Execute command
            result = eval(command, {"__builtins__": {}}, local_vars)

            # Convert result to string
            if isinstance(result, pd.DataFrame):
                return result.to_string()
            elif isinstance(result, pd.Series):
                return result.to_string()
            else:
                return str(result)

        except Exception as e:
            return f"Error executing pandas command: {str(e)}"

    def get_df_info(self, df_name: str = "default") -> str:
        """Returns information about specified DataFrame"""
        try:
            if df_name not in self.dataframes:
                return f"DataFrame '{df_name}' not found"

            df = self.dataframes[df_name]

            info = []
            info.append(f"DataFrame '{df_name}':")
            info.append(f"Shape: {df.shape}")
            info.append(f"Columns: {list(df.columns)}")
            info.append("\nDataFrame info:")

            # Capture df.info() output
            import io
            buffer = io.StringIO()
            df.info(buf=buffer)
            info.append(buffer.getvalue())

            info.append("\nSample data:")
            info.append(df.head().to_string())

            return "\n".join(info)

        except Exception as e:
            return f"Error getting DataFrame info: {str(e)}"