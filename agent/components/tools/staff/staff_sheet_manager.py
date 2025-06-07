"""
Staff sheet manager for handling staff Google Sheets data.
Handles reading from Google Sheets and formatting task information.
"""
import logging
from typing import Dict, Any, Optional, List
import pandas as pd

class StaffSheetManager:
    """
    Manages staff Google Sheets data and operations.
    """
    
    def __init__(self, data_manager, agent=None):
        """
        Initialize the staff sheet manager.
        
        Args:
            data_manager: Instance of StaffDataManager for accessing staff data
            agent: Reference to the agent instance (optional)
        """
        self.data_manager = data_manager
        self.agent = agent
        
        logging.info("StaffSheetManager initialized")
    
    def read_staff_tasks(self, staff_telegram_username):
        """
        Read tasks for a specific staff member from the combined tasks sheet.
        Improved to handle column mismatches and inconsistent data.
        Automatically saves tasks to Redis.
        
        Args:
            staff_telegram_username: Telegram username of the staff member (with or without @)
            
        Returns:
            DataFrame with filtered staff tasks or error message
        """
        try:
            # Import pandas at the function level to ensure it's always available
            import pandas as pd
            import numpy as np
            if not staff_telegram_username.startswith('@'):
                staff_telegram_username = f"@{staff_telegram_username}"
            
            # First try to get tasks from Redis (for faster access and as fallback)
            if hasattr(self.data_manager, 'get_staff_tasks_from_redis'):
                redis_tasks = self.data_manager.get_staff_tasks_from_redis(staff_telegram_username)
            else:
                redis_tasks = []
            
            # Validate staff exists
            staff_list = self.data_manager.get_staff_list()
            staff = next((s for s in staff_list if s.get("telegram_username") == staff_telegram_username), None)
            
            if not staff:
                return f"Staff member with Telegram username {staff_telegram_username} not found"
            
            # Get staff full name for filtering
            staff_full_name = staff.get('full_name')
            if not staff_full_name:
                return f"Full name not available for {staff_telegram_username}"
                
            # Break down the full name into components for flexible matching
            name_parts = staff_full_name.lower().split()
            first_name = name_parts[1] if len(name_parts) > 1 else ""
            last_name = name_parts[0] if len(name_parts) > 0 else ""
            
            # Check Google Sheets tool is available
            if not self.agent or not hasattr(self.agent.toolset, "google_sheets_tool"):
                # If Google Sheets tool is not available, use Redis tasks if we have them
                if isinstance(redis_tasks, list) and redis_tasks:
                    # Convert Redis tasks to DataFrame
                    df = pd.DataFrame(redis_tasks)
                    logging.info(f"Using Redis tasks for {staff_telegram_username} (Google Sheets tool not available)")
                    return df
                return "GoogleSheetsTool not available"
            
            google_sheets_tool = self.agent.toolset.google_sheets_tool
            
            # Read the combined sheet
            sheet_name = "ВСЕЗАДАЧИ"
            result = google_sheets_tool.read_sheet(sheet_name)
            
            if "DataFrame" not in result:
                # Try direct API access to diagnose the issue
                logging.info(f"Using direct API to diagnose sheet structure for {sheet_name}")
                try:
                    service = google_sheets_tool.get_service()
                    request = service.spreadsheets().values().get(
                        spreadsheetId=google_sheets_tool.SHEET_ID,
                        range=f"'{sheet_name}'"
                    )
                    response = request.execute()
                    values = response.get('values', [])
                    
                    if not values:
                        # If no values and we have Redis tasks, use those
                        if isinstance(redis_tasks, list) and redis_tasks:
                            df = pd.DataFrame(redis_tasks)
                            logging.info(f"Using Redis tasks for {staff_telegram_username} (Sheet empty)")
                            return df
                        return f"Sheet {sheet_name} is empty"
                    
                    # Log sheet structure for diagnosis
                    row_lengths = [len(row) for row in values[:5]]  # First 5 rows
                    logging.info(f"Sheet structure: {row_lengths} columns in first 5 rows")
                    
                    # Create DataFrame manually with flexible column handling
                    # pandas and numpy already imported at the function level
                    
                    # Determine max columns
                    max_cols = max(len(row) for row in values)
                    
                    # Create headers (use first row or generate)
                    if values:
                        headers = list(values[0])
                        # Extend headers if needed
                        while len(headers) < max_cols:
                            headers.append(f"Column_{len(headers)+1}")
                    else:
                        headers = [f"Column_{i+1}" for i in range(max_cols)]
                    
                    # Normalize data rows to have same length
                    data_rows = []
                    for row in values[1:]:  # Skip header
                        padded_row = list(row)
                        # Pad shorter rows
                        while len(padded_row) < max_cols:
                            padded_row.append(None)
                        data_rows.append(padded_row)
                    
                    # Create DataFrame
                    df = pd.DataFrame(data_rows, columns=headers)
                    
                    # Save in pandas tool
                    df_name = f"sheet_{sheet_name.lower().replace(' ', '_')}"
                    self.agent.toolset.sql_pandas_tool.dataframes[df_name] = df
                    
                    logging.info(f"Created dataframe with {len(df)} rows and {len(df.columns)} columns")
                except Exception as e:
                    # If error and we have Redis tasks, use those
                    if isinstance(redis_tasks, list) and redis_tasks:
                        df = pd.DataFrame(redis_tasks)
                        logging.info(f"Using Redis tasks for {staff_telegram_username} due to API error: {e}")
                        return df
                        
                    logging.error(f"Error in direct API access: {e}")
                    import traceback
                    traceback.print_exc()
                    return f"Error reading sheet: {result}"
            
            # Get the dataframe from the pandas tool
            df_name = f"sheet_{sheet_name.lower().replace(' ', '_')}"
            if not self.agent or not hasattr(self.agent.toolset, "sql_pandas_tool"):
                # If SQL Pandas Tool is not available, use Redis tasks if we have them
                if isinstance(redis_tasks, list) and redis_tasks:
                    df = pd.DataFrame(redis_tasks)
                    logging.info(f"Using Redis tasks for {staff_telegram_username} (SQL Pandas Tool not available)")
                    return df
                return "SQL Pandas Tool not available"
                
            if df_name not in self.agent.toolset.sql_pandas_tool.dataframes:
                # If DataFrame not found and we have Redis tasks, use those
                if isinstance(redis_tasks, list) and redis_tasks:
                    df = pd.DataFrame(redis_tasks)
                    logging.info(f"Using Redis tasks for {staff_telegram_username} (DataFrame not found)")
                    return df
                return f"DataFrame '{df_name}' not found after reading sheet"
                
            df = self.agent.toolset.sql_pandas_tool.dataframes[df_name]
            
            # IMPROVED STAFF NAME MATCHING:
            # Find staff column - typically the first column
            staff_column = None
            if 'Исполнитель' in df.columns:
                staff_column = 'Исполнитель'
            elif 'A' in df.columns:
                staff_column = 'A'
            elif 'Column_1' in df.columns:
                staff_column = 'Column_1'
            else:
                # Get first column whatever it's called
                staff_column = df.columns[0]
            
            # Convert names to lowercase for case-insensitive matching
            # Create a flexible matching mask
            mask = df[staff_column].astype(str).str.lower().apply(
                lambda x: any(part in x for part in [first_name, last_name])
            )
            
            # If the first method doesn't find matches, try additional approaches
            if mask.sum() == 0:
                # Try matching by first name or position
                if 'директор' in last_name.lower() or 'директор' in first_name.lower():
                    mask = df[staff_column].astype(str).str.lower().str.contains('директор')
                elif 'сз' in last_name.lower() or 'cз' in first_name.lower():
                    mask = df[staff_column].astype(str).str.lower().str.contains('сз')
                    
                # Try matching by direct telegram username
                # Remove @ from username for comparison
                username_without_at = staff_telegram_username.replace('@', '')
                
                # Check if any row contains the telegram username
                username_mask = df[staff_column].astype(str).str.lower().str.contains(username_without_at.lower())
                
                # Combine masks
                mask = mask | username_mask
            
            filtered_df = df[mask].copy()
            
            logging.info(f"Found {len(filtered_df)} rows for {staff_full_name} after flexible matching")
            
            if filtered_df.empty:
                # If no matches found and we have Redis tasks, use those
                if isinstance(redis_tasks, list) and redis_tasks:
                    df = pd.DataFrame(redis_tasks)
                    logging.info(f"Using Redis tasks for {staff_telegram_username} (no matches in sheet)")
                    return df
                    
                # Create an empty dataframe with the same columns for consistency
                filtered_df = pd.DataFrame(columns=df.columns)
            
            # Save the filtered dataframe with the staff-specific name for backward compatibility
            safe_name = ''.join(c if c.isalnum() else '_' for c in staff.get('full_name', ''))
            staff_df_name = f"sheet_{safe_name.lower()}"
            self.agent.toolset.sql_pandas_tool.dataframes[staff_df_name] = filtered_df
            
            # Store tasks in Redis for future reference and backup
            if hasattr(self, 'store_staff_tasks_in_redis'):
                self.store_staff_tasks_in_redis(staff_telegram_username, filtered_df)
            
            logging.info(f"Successfully filtered {len(filtered_df)} tasks for {staff_full_name}, saved as {staff_df_name}")
            return filtered_df
                
        except Exception as e:
            logging.error(f"Error reading staff tasks: {e}")
            import traceback
            traceback.print_exc()
            return f"Error reading staff tasks: {str(e)}"
    
    def get_staff_tasks_summary(self, staff_telegram_username):
        """
        Get a summary of tasks for a specific staff member.
        Enhanced to be more robust against sheet structure issues.
        
        Args:
            staff_telegram_username: Telegram username of the staff member
            
        Returns:
            Formatted string with task summary
        """
        try:
            # Import pandas at the function level to ensure it's always available
            import pandas as pd
            if not staff_telegram_username.startswith('@'):
                staff_telegram_username = f"@{staff_telegram_username}"
                    
            staff_list = self.data_manager.get_staff_list()
            staff = next((s for s in staff_list if s.get("telegram_username") == staff_telegram_username), None)
            
            if not staff:
                return f"Staff member with Telegram username {staff_telegram_username} not found"
                    
            tasks_result = self.read_staff_tasks(staff_telegram_username)
            
            if isinstance(tasks_result, str):
                return tasks_result
            
            if tasks_result.empty:
                return f"No tasks for {staff.get('full_name', staff_telegram_username)}"
                    
            tasks_summary = self._format_task_info(tasks_result)
            
            # Find sum column - could be "sum", "F", "Column_7", etc. (Column G in screenshot)
            sum_col = None
            for col_name in ['Column_7', 'G', 'sum', 'F']:
                if col_name in tasks_result.columns:
                    sum_col = col_name
                    break
            
            # Find status column (typically has dates or "✓" markers - Column E in screenshot)
            status_col = None
            for col_name in ['V', 'E', 'Column_5', 'status', 'Статус']:
                if col_name in tasks_result.columns:
                    status_col = col_name
                    break
            
            # Calculate statistics
            total_amount = 0
            if sum_col:
                try:
                    # Convert to numeric, handling errors
                    tasks_result[sum_col] = pd.to_numeric(tasks_result[sum_col].astype(str).str.replace('\xa0', ''), errors='coerce')
                    total_amount = tasks_result[sum_col].sum()
                except Exception as e:
                    logging.error(f"Error calculating sum: {e}")
                    
            completed_tasks = 0
            total_tasks = len(tasks_result)
            
            if status_col:
                try:
                    # In this sheet, status doesn't contain checkmarks but deadlines
                    # No special marker means not completed yet
                    completed_tasks = sum(1 for status in tasks_result[status_col] if pd.notna(status) and status != '')
                except Exception as e:
                    logging.error(f"Error counting completed tasks: {e}")
            
            staff_name = staff.get('full_name', staff_telegram_username)
            summary = f"Task summary for {staff_name}:\n\n"
            summary += f"Total tasks: {total_tasks}\n"
            summary += f"Tasks in progress: {total_tasks - completed_tasks}\n"
            summary += f"Tasks with deadline set: {completed_tasks}\n"
            summary += f"Total amount: {total_amount:,.0f} rub.\n\n"
            
            if tasks_summary:
                summary += "Task details:\n\n"
                summary += tasks_summary
            else:
                summary += "No detailed task information available."
            
            return summary
                
        except Exception as e:
            logging.error(f"Error getting staff tasks summary: {e}")
            import traceback
            traceback.print_exc()
            return f"Error getting staff tasks summary: {str(e)}"
    
    def _format_task_info(self, tasks_df):
        """
        Format task information from DataFrame into a readable string.
        Enhanced to handle variable column structures.
        
        Args:
            tasks_df: DataFrame with task information
            
        Returns:
            Formatted string with task information
        """
        try:
            # Import pandas at the function level to ensure it's always available
            import pandas as pd
            if tasks_df.empty:
                return "No tasks found"
            
            # Map columns based on actual sheet structure from screenshot
            column_mapping = {
                'executor': 'Исполнитель',
                'task': 'ЗАДАЧА',
                'result': 'РЕЗУЛЬТАТ',
                'due_date': '☠️ Due time',
                'status': 'V',
                'amount': 'Column_7'  # This appears to be the column with monetary values
            }
            
            # Use fallbacks if the exact column names aren't found
            for expected in column_mapping.keys():
                if column_mapping[expected] not in tasks_df.columns:
                    # Try to find the column by position based on screenshot
                    if expected == 'executor' and tasks_df.columns[0]:
                        column_mapping[expected] = tasks_df.columns[0]
                    elif expected == 'task' and len(tasks_df.columns) > 1:
                        column_mapping[expected] = tasks_df.columns[1]
                    elif expected == 'result' and len(tasks_df.columns) > 2:
                        column_mapping[expected] = tasks_df.columns[2]
                    elif expected == 'due_date' and len(tasks_df.columns) > 3:
                        column_mapping[expected] = tasks_df.columns[3]
                    elif expected == 'status' and len(tasks_df.columns) > 4:
                        column_mapping[expected] = tasks_df.columns[4]
                    elif expected == 'amount' and len(tasks_df.columns) > 6:
                        column_mapping[expected] = tasks_df.columns[6]
            
            # Format tasks with the available columns
            formatted_tasks = []
            
            for _, row in tasks_df.iterrows():
                if pd.isna(row.iloc[0]):
                    continue  # Skip rows with empty first column
                    
                task_info = []
                
                # Add task information based on available columns
                if 'task' in column_mapping:
                    col = column_mapping['task']
                    if col in tasks_df.columns:
                        task = row[col] if not pd.isna(row[col]) else "Not specified"
                        task_info.append(f"Task: {task}")
                        
                if 'result' in column_mapping:
                    col = column_mapping['result']
                    if col in tasks_df.columns:
                        result = row[col] if not pd.isna(row[col]) else "Not specified"
                        task_info.append(f"Result: {result}")
                        
                if 'due_date' in column_mapping:
                    col = column_mapping['due_date']
                    if col in tasks_df.columns:
                        due_date = row[col] if not pd.isna(row[col]) else "Not specified"
                        task_info.append(f"Due date: {due_date}")
                        
                if 'status' in column_mapping:
                    col = column_mapping['status']
                    if col in tasks_df.columns:
                        status = row[col]
                        if pd.isna(status) or status == "":
                            status_text = "In progress"
                        else:
                            status_text = status if isinstance(status, str) else "✓"
                        task_info.append(f"Status: {status_text}")
                        
                if 'amount' in column_mapping:
                    col = column_mapping['amount']
                    if col in tasks_df.columns:
                        amount = row[col] if not pd.isna(row[col]) else "0"
                        task_info.append(f"Amount: {amount}")
                
                if task_info:
                    formatted_tasks.append("\n".join(task_info))
            
            return "\n\n".join(formatted_tasks)
        
        except Exception as e:
            logging.error(f"Error formatting task information: {e}")
            import traceback
            traceback.print_exc()
            return f"Error formatting task information: {str(e)}"
