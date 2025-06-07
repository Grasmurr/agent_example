from datetime import datetime
from .base_monitor import BaseMonitor

class TimerMonitor(BaseMonitor):
    """Monitor for displaying active timers."""
    
    def __init__(self, timer_tool):
        """
        Initialize timer monitor with a reference to the timer tool.
        
        Args:
            timer_tool: Instance of TimerTool
        """
        self.timer_tool = timer_tool
    
    def get_raw_data(self) -> str:
        """
        Retrieve data about active timers.
        
        Returns:
            String representation of active timers
        """
        active_timers = {id: timer for id, timer in self.timer_tool.timers.items() 
                        if timer["status"] == "active"}
        
        if not active_timers:
            return "Нет активных таймеров."
        
        result = []
        
        # Sort timers by next run time
        sorted_timers = sorted(active_timers.items(), 
                              key=lambda x: x[1]["next_run"])
        
        # Display next 5 timers to run
        for timer_id, timer in sorted_timers[:5]:
            next_run = datetime.fromtimestamp(timer["next_run"])
            now = datetime.now()
            time_left = next_run - now
            
            if time_left.total_seconds() < 0:
                time_left_str = "сейчас"
            else:
                days = time_left.days
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                time_left_parts = []
                if days > 0:
                    time_left_parts.append(f"{days}д")
                if hours > 0 or days > 0:
                    time_left_parts.append(f"{hours}ч")
                if minutes > 0 or hours > 0 or days > 0:
                    time_left_parts.append(f"{minutes}м")
                time_left_parts.append(f"{seconds}с")
                
                time_left_str = " ".join(time_left_parts)
            
            timer_type = "🔄" if timer["is_recurring"] else "⏱️"
            has_action = "💬" if timer["action"] else ""
            has_procedure = "🔧" if timer["procedure"] else ""
            
            result.append(f"{timer_type} {timer['name']} ({timer_id}): {next_run.strftime('%Y-%m-%d %H:%M:%S')} ({time_left_str}) {has_action}{has_procedure}")
        
        # Add total count if there are more timers
        if len(active_timers) > 5:
            result.append(f"... и еще {len(active_timers) - 5} таймеров")
        
        return "\n".join(result)
    
    def render(self) -> str:
        """
        Render timer data in XML format.
        
        Returns:
            XML representation of timer data
        """
        content = self.get_raw_data()
        
        if "Нет активных таймеров" in content:
            return ""  # Don't show the monitor if there are no timers
            
        return self.wrap_in_xml(
            "timers",
            f"\n{content}\n",
            {"source": "timer_manager"}
        )
