import logging
import uuid
import re

class PythonCliTool:
    def __init__(self, ssh_tool):
        """
        Initialize Python CLI tool with reference to the SSH tool.
        
        Args:
            ssh_tool: Instance of SSHTool for executing commands on VM
        """
        self.ssh_tool = ssh_tool
        self.python_command = "python3"  # Default command
        self.last_commands = []
        self.last_outputs = []
        self.max_history = 10
        self.working_dir = "/tmp/python_cli_tool"  # Directory for temporary files
        
        # Initialize working directory
        self._init_working_dir()
    
    def _init_working_dir(self):
        """Creates the working directory on the VM if it doesn't exist."""
        self.ssh_tool.terminal(f"mkdir -p {self.working_dir}")
    
    def _check_python_availability(self):
        """Checks if Python is available on the VM."""
        output = self.ssh_tool.terminal(f"which {self.python_command}")
        return self.python_command in output
    
    def execute_python_cli(self, code):
        """
        Executes Python code on the remote VM.
        
        For simple one-liners, uses python -c.
        For multi-line code, creates a temporary script and executes it.
        
        Args:
            code: Python code to execute
            
        Returns:
            Output from executing the code
        """
        # Check if Python is available
        if not self._check_python_availability():
            error_msg = f"{self.python_command} not found on the VM. Please install Python."
            logging.error(error_msg)
            return error_msg
        
        # Clean the code (remove leading/trailing whitespace)
        code = code.strip()
        
        # For simple one-liners, try to detect expressions
        if "\n" not in code and not code.endswith(";") and "=" not in code and "print" not in code:
            # This looks like an expression, so wrap it in print
            try:
                # Try to compile as an expression to confirm
                compile(code, '<string>', 'eval')
                # If it compiles, wrap in print for REPL-like behavior
                escaped_code = code.replace('"', '\\"')
                command = f'{self.python_command} -c "print({escaped_code})"'
            except SyntaxError:
                # Not a valid expression, use as-is
                escaped_code = code.replace('"', '\\"')
                command = f'{self.python_command} -c "{escaped_code}"'
            
            output = self.ssh_tool.terminal(command)
        else:
            # For multi-line code, create a temporary script
            script_name = f"script_{uuid.uuid4().hex[:8]}.py"
            script_path = f"{self.working_dir}/{script_name}"
            
            # Create the script file using heredoc to avoid escaping issues
            create_script_cmd = f'cat > {script_path} << \'EOL\'\n{code}\nEOL'
            self.ssh_tool.terminal(create_script_cmd)
            
            # Execute the script
            command = f"{self.python_command} {script_path}"
            output = self.ssh_tool.terminal(command)
            
            # Clean up the script file
            self.ssh_tool.terminal(f"rm {script_path}")
        
        # Store command and output in history
        self.last_commands.append(code)
        self.last_outputs.append(output)
        
        # Maintain max history size
        if len(self.last_commands) > self.max_history:
            self.last_commands.pop(0)
            self.last_outputs.pop(0)
        
        return output
    
    def install_python_package(self, package_name):
        """
        Installs a Python package using pip.
        
        Args:
            package_name: Name of the package to install
            
        Returns:
            Output from the pip install command
        """
        # Check if pip is available
        pip_check = self.ssh_tool.terminal("which pip3 || which pip")
        if not pip_check.strip():
            return "Error: pip not found on the VM. Please install pip."
        
        # Determine pip command
        pip_command = "pip3" if "pip3" in pip_check else "pip"
        
        # Install the package
        command = f"{pip_command} install {package_name}"
        output = self.ssh_tool.terminal(command)
        
        return output
    
    def list_python_packages(self):
        """
        Lists installed Python packages.
        
        Returns:
            Output from pip list command
        """
        # Check if pip is available
        pip_check = self.ssh_tool.terminal("which pip3 || which pip")
        if not pip_check.strip():
            return "Error: pip not found on the VM. Please install pip."
        
        # Determine pip command
        pip_command = "pip3" if "pip3" in pip_check else "pip"
        
        # List packages
        command = f"{pip_command} list"
        output = self.ssh_tool.terminal(command)
        
        return output
