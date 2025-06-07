from .base_monitor import BaseMonitor


class DataFrameMonitor(BaseMonitor):
    """
    Monitor for DataFrame data visualization.
    Accepts either sql_pandas_tool or mysql_pandas_tool for backward compatibility.
    """
    
    def __init__(self, sql_pandas_tool):
        """
        Initialize the DataFrame monitor.
        
        Args:
            sql_pandas_tool: Tool for SQL and pandas operations (either SqlPandasTool or MySqlPandasTool)
        """
        self.sql_pandas_tool = sql_pandas_tool

    def get_raw_data(self) -> str:
        """Получение информации о существующих DataFrame"""
        dataframes = self.sql_pandas_tool.dataframes
        if not dataframes:
            return "No DataFrames in memory"

        df_info = []
        for name, df in dataframes.items():
            df_info.append(f"DataFrame '{name}': {df.shape[0]} rows × {df.shape[1]} columns")
        return "\n".join(df_info)

    def render(self) -> str:
        """Рендеринг информации о DataFrame в XML формате"""
        content = self.get_raw_data()
        if content == "No DataFrames in memory":
            return ""  # Не показываем пустой монитор

        return self.wrap_in_xml(
            "dataframes",
            f"\n{content}\n",
            {"source": "pandas"}
        )