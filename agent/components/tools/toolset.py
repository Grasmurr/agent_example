"""
Toolset manager for initializing and managing tools for the agent.
"""
import logging
from typing import List, Dict, Any, Callable, Optional
from langchain.tools.base import StructuredTool
from multiprocessing.managers import ListProxy

from components.tools.tool_registry import ToolRegistry
from components.tools.tool_initializer import ToolInitializer


class Toolset:
    def __init__(self, memory_manager, tg_messages: ListProxy, agent=None):
        """
        Initialize the toolset with all available tools.
        
        Args:
            memory_manager: Memory manager for tools that require it
            tg_messages: Telegram messages list proxy
            agent: Reference to the agent instance
        """
        # Initialize registry
        self.registry = ToolRegistry()
        
        # Store agent reference for later use
        self.agent = agent
        
        # Initialize tools
        self.initializer = ToolInitializer(self.registry, memory_manager, tg_messages, agent)
        self.initializer.initialize_all_tools()
        
        # Define shortcuts to common tools for backward compatibility
        self._create_tool_shortcuts()
        
        # Define mappings for ease of access
        self.tool_instances = self.registry.tool_instances
        self.tool_functions = self.registry.tool_functions
        self.aspect_tools_mapping = self.registry.aspect_tools_mapping
        
        logging.info(f"Toolset initialized with {len(self.tool_instances)} tools")
    
    def _create_tool_shortcuts(self):
        """Create shortcuts to common tools for backward compatibility."""
        for tool_name, tool in self.registry.tool_instances.items():
            # Create attributes like self.tg_tool, self.task_tool, etc.
            setattr(self, tool_name, tool)
    
    def update_agent_reference(self, agent):
        """
        Update the agent reference in all tools after initialization.
        This is necessary to solve circular dependency issues.
        
        Args:
            agent: The agent instance
        """
        logging.info("Updating agent reference in tools")
        
        # Update agent reference in tools that store it
        for tool_name, tool in self.registry.tool_instances.items():
            if hasattr(tool, 'agent'):
                tool.agent = agent
                logging.info(f"Updated agent reference in tool: {tool_name}")
    
    def tools(self, active_tools=None):
        """
        Return a list of tools, filtering by active tools if specified.
        
        Args:
            active_tools: List of names of active tools
        Returns:
            list: List of StructuredTool objects
        """
        # If active tools are specified
        if active_tools and isinstance(active_tools, list) and len(active_tools) > 0:
            # Collect all functions for active tools
            active_functions = []
            for tool_name in active_tools:
                # Check if the name is a tool name or a function name
                if tool_name in self.aspect_tools_mapping:
                    # This is a tool name from an aspect, add all its functions
                    active_functions.extend(self.aspect_tools_mapping[tool_name])
                elif tool_name in self.tool_functions:
                    # This is a function name, add it
                    active_functions.append(tool_name)
            
            # If no functions remain after filtering, add basic tools
            if not active_functions:
                active_functions = ["send_telegram_message", "show_pending_tasks"]
        else:
            # Use default set of tools
            active_functions = [
                "send_telegram_message",
                "create_task",
                "finish_task",
                "show_pending_tasks",
                "cancel_task",
                "sketchpad_append",
                "sketchpad_replace",
                "sketchpad_clear"
            ]
        
        # Create structured tools from functions
        tools = []
        for func_name in active_functions:
            if func_name in self.tool_functions:
                try:
                    tool = StructuredTool.from_function(self.tool_functions[func_name])
                    tools.append(tool)
                except Exception as e:
                    logging.error(f"Error creating tool from function {func_name}: {e}")
        
        return tools
    
    def reload_tools(self):
        """
        Reload tools after file changes on disk.
        """
        try:
            # Store old registry for reference
            old_registry = self.registry
            
            # Create new registry
            self.registry = ToolRegistry()
            
            # Initialize tools with new registry
            self.initializer = ToolInitializer(
                self.registry, 
                self.agent.memory_manager, 
                self.agent.tg_messages, 
                self.agent
            )
            self.initializer.initialize_all_tools()
            
            # Update shortcuts and mappings
            self._create_tool_shortcuts()
            self.tool_instances = self.registry.tool_instances
            self.tool_functions = self.registry.tool_functions
            self.aspect_tools_mapping = self.registry.aspect_tools_mapping
            
            logging.info(f"Tools successfully reloaded: {len(self.tool_instances)} tools")
            return True
        except Exception as e:
            logging.error(f"Error reloading tools: {str(e)}")
            return False
    
    def get_tool_functions(self, tool_names: List[str]) -> List[Callable]:
        """
        Get all functions of the specified tools.
        
        Args:
            tool_names: List of tool names
            
        Returns:
            List of functions from those tools
        """
        return self.registry.get_tool_functions(tool_names)
    
    def get_available_tools(self) -> List[str]:
        """
        Get names of all available tools.
        
        Returns:
            List of tool names
        """
        return self.registry.get_available_tools()
    
    def get_available_functions(self) -> List[str]:
        """
        Get names of all available functions.
        
        Returns:
            List of function names
        """
        return self.registry.get_available_functions()
    
    def tool_from(self, function):
        """
        Create a StructuredTool from a function.
        
        Args:
            function: Function to create a tool from
            
        Returns:
            StructuredTool object
        """
        return StructuredTool.from_function(function)
