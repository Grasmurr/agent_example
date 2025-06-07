import importlib
import importlib.util
import inspect
import logging
import os
import sys
from typing import Dict, Any, Type, List, Optional, Callable, Union

from langchain.tools.base import BaseTool, StructuredTool

class ToolFactory:
    """
    Фабрика для динамического создания инструментов.
    """
    
    def __init__(self):
        self.registry: Dict[str, Type] = {}
        self.instances: Dict[str, Any] = {}
        self.functions: Dict[str, Callable] = {}
        self.dependencies: Dict[str, List[str]] = {}
        
    def discover_tools(self, tools_dir: str = None):
        """
        Сканирует указанную директорию для обнаружения классов инструментов.
        
        Args:
            tools_dir: Путь к директории с инструментами (если None, используется относительный путь)
        """
        try:
            # Определяем директорию инструментов
            if tools_dir is None:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                tools_dir = os.path.join(os.path.dirname(current_dir), "tools")
            
            # Проверяем существование директории
            if not os.path.exists(tools_dir) or not os.path.isdir(tools_dir):
                logging.error(f"Директория инструментов {tools_dir} не существует или не является директорией")
                return
                
            logging.info(f"Сканирование директории инструментов: {tools_dir}")
            
            # Получаем список файлов инструментов
            tool_files = [f for f in os.listdir(tools_dir) 
                         if f.endswith('_tool.py') and not f.startswith('__')]
            logging.info(f"Найдено {len(tool_files)} файлов инструментов: {', '.join(tool_files)}")
            
            # Получаем список файлов инструментов
            tool_files = [f for f in os.listdir(tools_dir) 
                         if f.endswith('_tool.py') and not f.startswith('__')]
            logging.info(f"Найдено {len(tool_files)} файлов инструментов: {', '.join(tool_files)}")
            
            # Временно добавляем tools_dir в sys.path для корректной работы относительных импортов
            original_path = sys.path.copy()
            sys.path.insert(0, tools_dir)
            sys.path.insert(0, os.path.dirname(tools_dir))  # Для импорта из родительского пакета
            
            # Создаем фиктивный модуль для каждого импорта
            for tool_file in tool_files:
                try:
                    file_path = os.path.join(tools_dir, tool_file)
                    module_name = tool_file[:-3]  # Убираем расширение .py
                    
                    # Создаем фиктивный пакетный контекст
                    package_name = "tools"
                    if package_name not in sys.modules:
                        sys.modules[package_name] = type('module', (), {})()
                    
                    # Импортируем модуль вручную, подготавливая контекст для относительных импортов
                    with open(file_path, 'r') as f:
                        # Читаем содержимое файла
                        content = f.read()
                        
                        # Заменяем относительные импорты на абсолютные
                        content = content.replace("from .", "from tools.")
                        
                        # Создаем модуль
                        module = type('module', (), {'__name__': f"tools.{module_name}"})()
                        sys.modules[f"tools.{module_name}"] = module
                        
                        # Выполняем код модуля в контексте модуля
                        exec(content, module.__dict__)
                    
                    # Ищем классы инструментов в модуле
                    tool_classes = []
                    for name, obj in module.__dict__.items():
                        if inspect.isclass(obj) and name.endswith('Tool'):
                            # Получаем зависимости
                            try:
                                dependencies = self._get_constructor_dependencies(obj)
                            except:
                                dependencies = []
                            
                            # Регистрируем класс инструмента
                            tool_name = self._get_tool_name(name)
                            self.registry[tool_name] = obj
                            self.dependencies[tool_name] = dependencies
                            tool_classes.append(name)
                    
                    if tool_classes:
                        logging.info(f"В модуле {module_name} найдены инструменты: {', '.join(tool_classes)}")
                    else:
                        logging.warning(f"В модуле {module_name} не найдено классов инструментов")
                    
                except Exception as e:
                    logging.error(f"Ошибка при загрузке инструмента {tool_file}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Восстанавливаем исходный sys.path
            sys.path = original_path
            
            logging.info(f"Всего обнаружено инструментов: {len(self.registry)}")
        except Exception as e:
            logging.error(f"Ошибка при обнаружении инструментов: {e}")
    
    def _get_constructor_dependencies(self, cls: Type) -> List[str]:
        """
        Извлекает зависимости из конструктора класса.
        
        Args:
            cls: Класс инструмента
            
        Returns:
            Список имен аргументов конструктора
        """
        try:
            signature = inspect.signature(cls.__init__)
            # Пропускаем self и аргументы с значениями по умолчанию
            return [param for param in list(signature.parameters.keys())[1:] 
                    if signature.parameters[param].default == inspect.Parameter.empty]
        except (ValueError, TypeError):
            return []
    
    def _get_tool_name(self, class_name: str) -> str:
        """
        Преобразует имя класса в имя инструмента.
        
        Args:
            class_name: Имя класса
            
        Returns:
            Имя инструмента
        """
        # Преобразуем CamelCase в snake_case
        return class_name.replace("Tool", "").lower() + "_tool"
    
    def initialize_tools(self, dependencies: Dict[str, Any]) -> Dict[str, Any]:
        """
        Инициализирует все зарегистрированные инструменты с указанными зависимостями.
        
        Args:
            dependencies: Словарь зависимостей (имя -> объект)
            
        Returns:
            Словарь инициализированных инструментов (имя -> экземпляр)
        """
        self.instances.clear()
        
        # Сначала создаем экземпляры инструментов
        for name, cls in self.registry.items():
            try:
                args = {}
                for dep_name in self.dependencies[name]:
                    if dep_name in dependencies:
                        args[dep_name] = dependencies[dep_name]
                    elif dep_name in self.instances:
                        args[dep_name] = self.instances[dep_name]
                    else:
                        logging.warning(f"Отсутствует зависимость '{dep_name}' для инструмента '{name}'")
                        continue
                
                instance = cls(**args)
                self.instances[name] = instance
                logging.info(f"Инициализирован инструмент: {name}")
                
            except Exception as e:
                logging.error(f"Ошибка при инициализации инструмента {name}: {e}")
        
        return self.instances
    
    def collect_tool_functions(self) -> Dict[str, Callable]:
        """
        Собирает все функции из инициализированных инструментов.
        
        Returns:
            Словарь функций инструментов (имя функции -> функция)
        """
        self.functions.clear()
        
        for tool_name, tool_instance in self.instances.items():
            # Собираем публичные методы инструмента (не начинающиеся с _)
            for name, method in inspect.getmembers(tool_instance, inspect.ismethod):
                if not name.startswith('_'):
                    function_name = name
                    self.functions[function_name] = method
                    logging.info(f"Зарегистрирована функция: {function_name} из {tool_name}")
        
        return self.functions
    
    def get_function(self, name: str) -> Optional[Callable]:
        """
        Получает функцию инструмента по имени.
        
        Args:
            name: Имя функции
            
        Returns:
            Функция инструмента или None, если функция не найдена
        """
        return self.functions.get(name)
    
    def get_instance(self, name: str) -> Optional[Any]:
        """
        Получает экземпляр инструмента по имени.
        
        Args:
            name: Имя инструмента
            
        Returns:
            Экземпляр инструмента или None, если инструмент не найден
        """
        return self.instances.get(name)
    
    def get_functions_by_names(self, function_names: List[str]) -> List[Callable]:
        """
        Получает функции инструментов по их именам.
        
        Args:
            function_names: Список имен функций
            
        Returns:
            Список функций инструментов
        """
        return [self.functions[name] for name in function_names if name in self.functions]
    
    def create_structured_tools(self, function_names: List[str]) -> List[StructuredTool]:
        """
        Создает структурированные инструменты для LangChain на основе функций.
        
        Args:
            function_names: Список имен функций
            
        Returns:
            Список структурированных инструментов
        """
        tools = []
        
        for name in function_names:
            func = self.get_function(name)
            if func:
                try:
                    tool = StructuredTool.from_function(func)
                    tools.append(tool)
                except Exception as e:
                    logging.error(f"Ошибка при создании инструмента из функции {name}: {e}")
        
        return tools
