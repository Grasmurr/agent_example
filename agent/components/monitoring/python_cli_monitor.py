import re
from .base_monitor import BaseMonitor

class PythonCliMonitor(BaseMonitor):
    def __init__(self, python_cli_tool):
        """
        Initialize monitor with reference to the Python CLI tool.
        
        Args:
            python_cli_tool: Instance of PythonCliTool
        """
        self.python_cli_tool = python_cli_tool

    def _clean_output(self, text):
        """
        Clean SSH terminal output by removing ANSI escape sequences.
        """
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', text)
        
        # Standardize newlines
        cleaned = cleaned.replace('\r\n', '\n')
        
        return cleaned

    def get_raw_data(self) -> str:
        """
        Get information about the Python CLI tool's history.
        
        Returns:
            String representation of the Python commands and outputs
        """
        if not self.python_cli_tool.last_commands:
            return "No Python commands have been executed yet."
        
        output = ["Python Execution History:"]
        
        # Add command history with outputs
        # Show only the last 3 commands for conciseness
        for i, (cmd, result) in enumerate(zip(
            self.python_cli_tool.last_commands[-3:],
            self.python_cli_tool.last_outputs[-3:]
        )):
            # Format the command
            output.append(f"\n>>> {cmd}")
            
            # Clean and format the output
            cleaned_result = self._clean_output(result)
            
            # Truncate if too long
            if len(cleaned_result) > 500:
                formatted_result = cleaned_result[:250] + "\n[...]\n" + cleaned_result[-250:]
            else:
                formatted_result = cleaned_result
            
            output.append(f"{formatted_result}")
        
        return "\n".join(output)

    def render(self) -> str:
        """
        Render Python CLI monitor data in XML format.
        
        Returns:
            XML representation of Python command history or empty string if no history
        """
        content = self.get_raw_data()
        
        if "No Python commands have been executed yet" in content:
            return ""  # Don't show monitor if no history
            
        return self.wrap_in_xml(
            "python_cli",
            f"\n{content}\n",
            {"source": "vm"}
        )
