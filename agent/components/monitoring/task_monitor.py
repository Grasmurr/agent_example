from .base_monitor import BaseMonitor
import json, logging
import xml.sax.saxutils

def is_valid_json(s):
    try:
        json.loads(s)
        return True
    except json.JSONDecodeError:
        return False


class TaskMonitor(BaseMonitor):
    def __init__(self, task_tool):
        self.task_tool = task_tool

    def get_raw_data(self) -> str:
        return self.task_tool.show_pending_tasks()

    def render(self) -> str:
        raw_tasks = self.get_raw_data()
        try:
            if not raw_tasks or "There are no pending tasks" in raw_tasks:
                return "<tasks>No pending tasks</tasks>"
    
            tasks_str = raw_tasks.replace("Current tasks:\n", "").strip()
    
            if tasks_str and tasks_str != "[]" and is_valid_json(tasks_str):
                tasks_data = json.loads(tasks_str)
                formatted_tasks = []
                for task_id, description, created_at in tasks_data:
                    # Escape the description for XML
                    escaped_description = xml.sax.saxutils.escape(description)
                    s = (f'<task id ="{task_id}" timestamp="{created_at}">\n'
                         f'<description>{escaped_description}</description>\n'
                         f'</task>')
                    formatted_tasks.append(s)
                content = f"{''.join(formatted_tasks)}\n"
            else:
                content = "<tasks>No pending tasks</tasks>"
    
        except Exception as e:
            logging.error(f"Error formatting tasks: {e}")
            logging.error(f"Raw tasks string was: {raw_tasks} (type: {type(raw_tasks)})")
            content = "<tasks>Error formatting tasks</tasks>"
    
        return self.wrap_in_xml("current_tasks", content, {"type": "task_list"})