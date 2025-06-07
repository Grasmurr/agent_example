"""
Tool initializer for handling the initialization of tools in the correct order.
Automatically discovers and initializes tools based on dependency analysis.
"""
import logging
import os
import sys
import inspect
import importlib
from typing import Dict, List, Any, Tuple
from multiprocessing.managers import ListProxy

class ToolInitializer:
    """
    Handles the automatic initialization of tools in the correct order based on dependencies.
    """
    
    def __init__(self, registry, memory_manager, tg_messages: ListProxy, agent=None):
        """
        Initialize the tool initializer.
        
        Args:
            registry: Tool registry to register initialized tools
            memory_manager: Memory manager for tools that require it
            tg_messages: Telegram messages list proxy
            agent: Reference to the agent instance
        """
        self.registry = registry
        self.memory_manager = memory_manager
        self.tg_messages = tg_messages
        self.agent = agent
        
        # Dictionary of core dependencies that aren't tools
        self.core_deps = {
            "memory_manager": self.memory_manager,
            "tg_messages": self.tg_messages,
            "agent": self.agent
        }
    
    def initialize_all_tools(self) -> None:
        """
        Initialize all tools automatically by:
        1. Discovering all tool modules
        2. Analyzing dependencies
        3. Determining initialization order
        4. Initializing tools in the correct order
        """
        try:
            # Discover tool modules
            tools_info = self._discover_tools()
            
            # Initialize tools in the right order
            self._initialize_tools_in_order(tools_info)
            
            logging.info(f"All tools initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing tools: {e}")
            import traceback
            traceback.print_exc()
    
    def _discover_tools(self) -> Dict[str, Dict]:
        """
        Discover all tool modules and their information.
        
        Returns:
            Dictionary mapping tool names to tool information
        """
        tools_info = {}
        tools_dir = os.path.dirname(__file__)
        
        # Find all potential tool modules
        for filename in os.listdir(tools_dir):
            if filename.endswith("_tool.py") and not filename.startswith("__"):
                try:
                    # Get module name
                    module_name = filename[:-3]  # Remove .py extension
                    
                    # Import the module
                    module_path = f"components.tools.{module_name}"
                    module = importlib.import_module(module_path)
                    
                    # Find the tool class
                    tool_class = None
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and name.endswith("Tool"):
                            tool_class = obj
                            break
                    
                    if not tool_class:
                        logging.warning(f"No tool class found in {filename}")
                        continue
                    
                    # Get constructor parameters to determine dependencies
                    init_signature = inspect.signature(tool_class.__init__)
                    dependencies = []
                    
                    for param_name in init_signature.parameters:
                        if param_name == "self" or param_name in self.core_deps:
                            continue
                        
                        # This is likely a dependency on another tool
                        dependencies.append(param_name)
                    
                    # Store tool information
                    tools_info[module_name] = {
                        "name": module_name,
                        "class": tool_class,
                        "dependencies": dependencies
                    }
                    
                except Exception as e:
                    logging.error(f"Error analyzing {filename}: {e}")
        
        logging.info(f"Discovered {len(tools_info)} tools")
        return tools_info
    
    def _initialize_tools_in_order(self, tools_info: Dict[str, Dict]) -> None:
        """
        Initialize tools in the correct order based on dependencies.
        
        Args:
            tools_info: Dictionary mapping tool names to tool information
        """
        # Split tools into those without dependencies and those with dependencies
        basic_tools = {}
        dependent_tools = {}
        
        for name, info in tools_info.items():
            if not info["dependencies"]:
                basic_tools[name] = info
            else:
                dependent_tools[name] = info
        
        # Initialize basic tools first
        for name, info in basic_tools.items():
            self._initialize_tool(info)
        
        # Initialize dependent tools with multiple passes
        remaining_tools = dependent_tools.copy()
        max_passes = 10  # Prevent infinite loops
        
        for _ in range(max_passes):
            if not remaining_tools:
                break
                
            # Keep track of tools initialized in this pass
            initialized_in_pass = []
            
            for name, info in remaining_tools.items():
                # Check if all dependencies are satisfied
                deps_satisfied = True
                for dep in info["dependencies"]:
                    if not self.registry.get_tool_instance(dep):
                        deps_satisfied = False
                        break
                
                if deps_satisfied:
                    # Initialize this tool
                    self._initialize_tool(info)
                    initialized_in_pass.append(name)
            
            # If no tools were initialized in this pass, we have unresolvable dependencies
            if not initialized_in_pass:
                unresolved = list(remaining_tools.keys())
                logging.error(f"Unresolvable dependencies for tools: {unresolved}")
                break
            
            # Remove initialized tools from remaining
            for name in initialized_in_pass:
                del remaining_tools[name]
    
    def _initialize_tool(self, tool_info: Dict) -> None:
        """
        Initialize a single tool and register it.
        
        Args:
            tool_info: Dictionary with tool information
        """
        try:
            tool_class = tool_info["class"]
            tool_name = tool_info["name"]
            
            # Prepare constructor parameters
            init_signature = inspect.signature(tool_class.__init__)
            init_params = {}
            
            for param_name in init_signature.parameters:
                if param_name == "self":
                    continue
                
                if param_name in self.core_deps:
                    # This is a core dependency
                    init_params[param_name] = self.core_deps[param_name]
                else:
                    # This is likely a dependency on another tool
                    dependency_tool = self.registry.get_tool_instance(param_name)
                    if dependency_tool:
                        init_params[param_name] = dependency_tool
                    else:
                        logging.warning(f"Dependency {param_name} for {tool_name} not available, skipping parameter")
            
            # Instantiate the tool
            tool_instance = tool_class(**init_params)
            
            # Register the tool
            self.registry.register_tool(tool_name, tool_instance)
            
            logging.info(f"Initialized tool: {tool_name}")
            
        except Exception as e:
            logging.error(f"Error initializing {tool_info['name']}: {e}")
