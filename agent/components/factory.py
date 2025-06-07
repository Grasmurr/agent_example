import importlib
import inspect
import logging
import os
import sys
from typing import Dict, Any, Type, List, Optional, Callable, TypeVar, Generic, Union

T = TypeVar('T')

class ComponentFactory(Generic[T]):
    """
    Универсальная фабрика компонентов для динамической загрузки классов и создания их экземпляров.
    """
    
    def __init__(self, base_class: Type[T], components_dir: str):
        """
        Инициализирует фабрику компонентов.
        
        Args:
            base_class: Базовый класс для всех компонентов данного типа
            components_dir: Путь к директории с компонентами (относительно корня проекта)
        """
        self.base_class = base_class
        # Получаем абсолютный путь к директории компонентов
        self.components_dir = components_dir
        self.registry: Dict[str, Type[T]] = {}
        self.dependencies: Dict[str, List[str]] = {}
        
    def register(self, name: str, component_class: Type[T], dependencies: List[str] = None):
        """
        Регистрирует компонент в реестре.
        
        Args:
            name: Имя компонента
            component_class: Класс компонента
            dependencies: Список зависимостей (имена других компонентов или имена аргументов)
        """
        if not issubclass(component_class, self.base_class):
            raise TypeError(f"Класс {component_class.__name__} не является подклассом {self.base_class.__name__}")
        
        self.registry[name] = component_class
        self.dependencies[name] = dependencies or []
        logging.info(f"Зарегистрирован компонент: {name}")
        
    def discover_components(self):
        """
        Обнаруживает и регистрирует компоненты из указанной директории.
        """
        try:
            # Получаем абсолютный путь к директории
            components_path = os.path.abspath(self.components_dir)
            logging.info(f"Поиск компонентов в директории: {components_path}")
            
            # Проверяем существование директории
            if not os.path.exists(components_path) or not os.path.isdir(components_path):
                logging.error(f"Директория {components_path} не существует или не является директорией")
                return
                
            # Получаем список файлов Python в директории
            python_files = [f for f in os.listdir(components_path) 
                           if f.endswith('.py') and not f.startswith('__')]
            
            logging.info(f"Найдено {len(python_files)} файлов Python в директории: {', '.join(python_files)}")
            
            # Определяем базовое имя модуля на основе пути
            base_module_parts = []
            # Добавляем динамический импорт модулей
            sys.path.insert(0, os.path.dirname(components_path))
            
            module_base = os.path.basename(components_path)
            
            # Для каждого файла пытаемся импортировать и найти компоненты
            for file_name in python_files:
                module_name = file_name[:-3]  # Убираем расширение .py
                full_module_name = f"{module_base}.{module_name}"
                
                try:
                    # Импортируем модуль
                    spec = importlib.util.find_spec(full_module_name)
                    if spec is None:
                        logging.warning(f"Не удалось найти модуль {full_module_name}")
                        continue
                        
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Ищем компоненты в модуле
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            hasattr(obj, '__mro__') and
                            self.base_class in obj.__mro__ and 
                            obj != self.base_class):
                            
                            # Получаем зависимости из конструктора
                            dependencies = self._get_constructor_dependencies(obj)
                            
                            # Регистрируем компонент
                            component_name = self._get_component_name(name)
                            self.register(component_name, obj, dependencies)
                            logging.info(f"Зарегистрирован компонент: {component_name} из модуля {full_module_name}")
                    
                except (ImportError, AttributeError) as e:
                    logging.error(f"Ошибка при импорте модуля {full_module_name}: {e}")
            
            logging.info(f"Всего обнаружено компонентов: {len(self.registry)}")
        except Exception as e:
            logging.error(f"Ошибка при обнаружении компонентов: {e}")
    
    def _get_constructor_dependencies(self, cls: Type[T]) -> List[str]:
        """
        Извлекает зависимости из конструктора класса.
        
        Args:
            cls: Класс компонента
            
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
            
    def _get_component_name(self, class_name: str) -> str:
        """
        Преобразует имя класса в имя компонента.
        
        Args:
            class_name: Имя класса
            
        Returns:
            Имя компонента
        """
        # Преобразуем CamelCase в snake_case
        if "Monitor" in class_name:
            return class_name.replace("Monitor", "").lower() + "_monitor"
        elif "Tool" in class_name:
            return class_name.replace("Tool", "").lower() + "_tool"
        return class_name.lower()
        
    def create(self, name: str, dependencies: Dict[str, Any] = None) -> T:
        """
        Создает экземпляр компонента с указанным именем.
        
        Args:
            name: Имя компонента
            dependencies: Словарь зависимостей (имя -> объект)
            
        Returns:
            Экземпляр компонента
        """
        if name not in self.registry:
            raise ValueError(f"Компонент с именем '{name}' не зарегистрирован")
        
        component_class = self.registry[name]
        required_deps = self.dependencies[name]
        dependencies = dependencies or {}
        
        # Подготавливаем аргументы конструктора
        args = {}
        for dep_name in required_deps:
            if dep_name in dependencies:
                args[dep_name] = dependencies[dep_name]
            else:
                raise ValueError(f"Отсутствует зависимость '{dep_name}' для компонента '{name}'")
        
        # Создаем экземпляр компонента
        return component_class(**args)
    
    def create_multiple(self, names: List[str], dependencies: Dict[str, Any] = None) -> List[T]:
        """
        Создает несколько экземпляров компонентов.
        
        Args:
            names: Список имен компонентов
            dependencies: Словарь зависимостей (имя -> объект)
            
        Returns:
            Список экземпляров компонентов
        """
        return [self.create(name, dependencies) for name in names]
    
    def get_available_components(self) -> List[str]:
        """
        Возвращает список имен всех доступных компонентов.
        
        Returns:
            Список имен компонентов
        """
        return list(self.registry.keys())