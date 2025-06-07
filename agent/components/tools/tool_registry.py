"""
Tool registry for managing tool registration and function discovery.
Maintains mappings between tool names and functions.
"""
import logging
import inspect
from typing import Dict, Any, Callable, List, Optional

class ToolRegistry:
    """
    Registry for managing tool instances and their functions.
    Provides lookup capabilities for tool functions based on tool names or aspect names.
    """
    
    def __init__(self):
        """Initialize an empty tool registry."""
        self.tool_instances: Dict[str, Any] = {}  # Tool name -> Tool instance
        self.tool_functions: Dict[str, Callable] = {}  # Function name -> Function
        self.aspect_tools_mapping: Dict[str, List[str]] = {}  # Aspect name -> List of function names
    
    def register_tool(self, name: str, instance: Any) -> None:
        """
        Register a tool instance in the registry.
        
        Args:
            name: Name of the tool (usually with '_tool' suffix)
            instance: The tool instance to register
        """
        self.tool_instances[name] = instance
        
        # Register tool functions
        for method_name, method in inspect.getmembers(instance, inspect.ismethod):
            if not method_name.startswith('_'):
                self.tool_functions[method_name] = method
                logging.info(f"Registered function {method_name} from tool {name}")
        
        # Update aspect mapping
        short_name = name.replace('_tool', '')
        self.aspect_tools_mapping[short_name] = []
        for method_name, method in inspect.getmembers(instance, inspect.ismethod):
            if not method_name.startswith('_'):
                self.aspect_tools_mapping[short_name].append(method_name)
    
    def get_tool_instance(self, name: str) -> Optional[Any]:
        """
        Get a tool instance by name.
        
        Args:
            name: Name of the tool
            
        Returns:
            The tool instance or None if not found
        """
        return self.tool_instances.get(name)
    
    def get_function(self, name: str) -> Optional[Callable]:
        """
        Get a function by name.
        
        Args:
            name: Name of the function
            
        Returns:
            The function or None if not found
        """
        return self.tool_functions.get(name)
    
    def get_aspect_functions(self, aspect_name: str) -> List[str]:
        """
        Get all function names for a given aspect.
        
        Args:
            aspect_name: Name of the aspect
            
        Returns:
            List of function names for the aspect
        """
        return self.aspect_tools_mapping.get(aspect_name, [])
    
    def get_tool_functions(self, tool_names: List[str]) -> List[Callable]:
        """
        Get all functions from specified tools.
        
        Args:
            tool_names: List of tool names
            
        Returns:
            List of functions from those tools
        """
        functions = []
        for tool_name in tool_names:
            if tool_name in self.aspect_tools_mapping:
                for func_name in self.aspect_tools_mapping[tool_name]:
                    func = self.tool_functions.get(func_name)
                    if func:
                        functions.append(func)
        return functions
    
    def get_available_tools(self) -> List[str]:
        """
        Get names of all registered tools.
        
        Returns:
            List of tool names
        """
        return list(self.tool_instances.keys())
    
    def get_available_functions(self) -> List[str]:
        """
        Get names of all registered functions.
        
        Returns:
            List of function names
        """
        return list(self.tool_functions.keys())
    
    def clear(self) -> None:
        """
        Clear all registered tools and functions.
        """
        self.tool_instances.clear()
        self.tool_functions.clear()
        self.aspect_tools_mapping.clear()
