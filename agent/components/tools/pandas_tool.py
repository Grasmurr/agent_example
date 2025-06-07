import pandas as pd
import json
from typing import Optional, Dict
import logging


class PandasTool:
    def __init__(self):
        self.dataframes: Dict[str, pd.DataFrame] = {}

    def create_dataframe(self, data: str, name: str = "default") -> str:
        """Creates a pandas DataFrame from JSON string data and stores it with given name"""
        try:
            # Парсим JSON данные из MySQL tool
            df_data = json.loads(data)
            if not df_data:
                return "Empty data received"

            # Создаем DataFrame
            df = pd.DataFrame(df_data)
            self.dataframes[name] = df

            # Возвращаем информацию о созданном DataFrame
            return (f"Created DataFrame '{name}' with shape {df.shape}\n"
                    f"Columns: {list(df.columns)}")
        except Exception as e:
            return f"Error creating DataFrame: {str(e)}"

    def execute_pandas(self, command: str) -> str:
        """Executes pandas command on stored DataFrames"""
        try:
            # Создаем локальные переменные для всех сохраненных датафреймов
            local_vars = {name: df for name, df in self.dataframes.items()}

            # Добавляем pandas как pd в локальные переменные
            local_vars['pd'] = pd

            # Выполняем команду
            result = eval(command, {"__builtins__": {}}, local_vars)

            # Преобразуем результат в строку
            if isinstance(result, pd.DataFrame):
                return result.to_string()
            elif isinstance(result, pd.Series):
                return result.to_string()
            else:
                return str(result)

        except Exception as e:
            return f"Error executing pandas command: {str(e)}"

    def get_dataframe_info(self, name: str = "default") -> str:
        """Returns information about the specified DataFrame"""
        try:
            if name not in self.dataframes:
                return f"DataFrame '{name}' not found"

            df = self.dataframes[name]
            info_str = []
            info_str.append(f"DataFrame '{name}':")
            info_str.append(f"Shape: {df.shape}")
            info_str.append(f"Columns: {list(df.columns)}")
            info_str.append("\nSample data:")
            info_str.append(df.head().to_string())

            return "\n".join(info_str)
        except Exception as e:
            return f"Error getting DataFrame info: {str(e)}"