import logging
import os
import importlib
import inspect
import sys
from typing import Dict, Any, List, Optional, Type

class MonitorFactory:
    """
    Фабрика для динамического создания мониторов.
    """
    
    def __init__(self):
        """Инициализирует фабрику мониторов."""
        # Определяем путь к директории мониторов
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.monitoring_dir = os.path.join(current_dir, "monitoring")
        
        # Регистры для хранения классов и зависимостей
        self.registry: Dict[str, Type] = {}
        self.dependencies: Dict[str, List[str]] = {}
        
        # Импортируем BaseMonitor автоматически
        self.BaseMonitor = self._import_base_monitor()
        
        # Автоматически обнаруживаем мониторы при инициализации
        self.discover_components()
    
    def _import_base_monitor(self):
        """Импортирует BaseMonitor из директории мониторов."""
        try:
            base_monitor_path = os.path.join(self.monitoring_dir, "base_monitor.py")
            if os.path.exists(base_monitor_path):
                module_name = "monitoring.base_monitor"
                
                # Добавляем родительский каталог в sys.path
                parent_dir = os.path.dirname(self.monitoring_dir)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                
                # Сначала проверяем, не импортирован ли уже модуль
                if module_name in sys.modules:
                    base_monitor_module = sys.modules[module_name]
                else:
                    # Импортируем модуль
                    base_monitor_module = importlib.import_module(module_name)
                
                # Получаем класс BaseMonitor
                BaseMonitor = getattr(base_monitor_module, "BaseMonitor")
                logging.info(f"Успешно импортирован BaseMonitor из {base_monitor_path}")
                return BaseMonitor
            else:
                logging.error(f"Файл base_monitor.py не найден по пути {base_monitor_path}")
        except Exception as e:
            logging.error(f"Ошибка при импорте BaseMonitor: {e}")
            import traceback
            traceback.print_exc()
        
        # Создаем минимальную реализацию BaseMonitor если не удалось импортировать
        logging.warning("Создаем минимальную реализацию BaseMonitor")
        
        class BaseMonitor:
            def get_raw_data(self): pass
            def render(self): pass
        
        return BaseMonitor
    
    def register(self, name: str, component_class, dependencies=None):
        """
        Регистрирует компонент в реестре.
        
        Args:
            name: Имя компонента
            component_class: Класс компонента
            dependencies: Список зависимостей
        """
        self.registry[name] = component_class
        self.dependencies[name] = dependencies or []
        logging.info(f"Зарегистрирован монитор: {name}")
    
    def discover_components(self):
        """Обнаруживает и регистрирует мониторы из директории monitoring."""
        try:
            # Проверяем существование директории
            if not os.path.exists(self.monitoring_dir):
                logging.error(f"Директория мониторов {self.monitoring_dir} не существует")
                return
            
            # Получаем список файлов Python в директории
            python_files = [f for f in os.listdir(self.monitoring_dir) 
                           if f.endswith('_monitor.py') and not f.startswith('__')]
            
            logging.info(f"Найдено {len(python_files)} файлов мониторов: {', '.join(python_files)}")
            
            # Добавляем родительский каталог в sys.path
            parent_dir = os.path.dirname(self.monitoring_dir)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
                was_added = True
            else:
                was_added = False
            
            try:
                # Импортируем модули и ищем мониторы
                for file_name in python_files:
                    module_name = file_name[:-3]  # Убираем .py
                    monitor_name = module_name  # task_monitor.py -> task_monitor
                    
                    try:
                        # Импортируем модуль
                        full_module_name = f"monitoring.{module_name}"
                        module = importlib.import_module(full_module_name)
                        
                        # Ищем класс монитора в модуле
                        for name, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and 
                                name.endswith('Monitor') and 
                                obj != self.BaseMonitor):
                                
                                # Получаем зависимости из конструктора
                                dependencies = self._get_constructor_dependencies(obj)
                                
                                # Регистрируем компонент
                                self.register(monitor_name, obj, dependencies)
                                logging.info(f"Найден монитор {name} в модуле {module_name}")
                                break
                        else:
                            logging.warning(f"В модуле {module_name} не найден класс монитора")
                            
                    except Exception as e:
                        logging.error(f"Ошибка при импорте модуля {module_name}: {e}")
                        import traceback
                        traceback.print_exc()
            finally:
                # Удаляем добавленный путь из sys.path
                if was_added and parent_dir in sys.path:
                    sys.path.remove(parent_dir)
            
            logging.info(f"Успешно зарегистрировано {len(self.registry)} мониторов")
            
        except Exception as e:
            logging.error(f"Ошибка при обнаружении мониторов: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_constructor_dependencies(self, cls) -> List[str]:
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
    
    def create(self, name: str, dependencies: Dict[str, Any] = None):
        """
        Создает экземпляр монитора с указанным именем.
        
        Args:
            name: Имя монитора
            dependencies: Словарь зависимостей (имя -> объект)
            
        Returns:
            Экземпляр монитора
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
    
    def create_monitors(self, monitor_names: List[str], dependencies: Dict[str, Any]) -> List:
        """
        Создает список мониторов на основе их имен и зависимостей.
        
        Args:
            monitor_names: Список имен мониторов для создания
            dependencies: Словарь зависимостей (имя -> объект)
            
        Returns:
            Список экземпляров мониторов
        """
        monitors = []
        failed_monitors = []
        
        # Первый проход: попытка создать мониторы
        for name in monitor_names:
            try:
                # Проверяем наличие всех зависимостей перед созданием монитора
                deps_satisfied = True
                required_deps = self.dependencies.get(name, [])
                
                for dep_name in required_deps:
                    if dep_name not in dependencies:
                        logging.warning(f"Отсутствует зависимость '{dep_name}' для компонента '{name}'")
                        deps_satisfied = False
                        break
                
                if deps_satisfied:
                    monitor = self.create(name, dependencies)
                    monitors.append(monitor)
                    logging.info(f"Создан монитор: {name}")
                else:
                    failed_monitors.append(name)
                    logging.warning(f"Не удалось создать монитор {name} из-за отсутствия зависимостей")
            except Exception as e:
                failed_monitors.append(name)
                logging.error(f"Ошибка при создании монитора {name}: {e}")
        
        # Если есть неудачные попытки, сообщаем о них
        if failed_monitors:
            logging.warning(f"Не удалось создать мониторы через factory: {set(failed_monitors)}")
        
        return monitors
    
    def create_all_monitors(self, dependencies: Dict[str, Any]) -> List:
        """
        Создает все доступные мониторы.
        
        Args:
            dependencies: Словарь зависимостей (имя -> объект)
            
        Returns:
            Список экземпляров всех мониторов
        """
        return self.create_monitors(list(self.registry.keys()), dependencies)
    
    def get_available_components(self) -> List[str]:
        """
        Возвращает список имен всех доступных компонентов.
        
        Returns:
            Список имен компонентов
        """
        return list(self.registry.keys())
