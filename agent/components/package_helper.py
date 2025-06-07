import sys
import os
import importlib
import importlib.util
import logging
import types
import re
from typing import Dict, Any, Optional

class PackageHelper:
    """
    Вспомогательный класс для работы с пакетами Python при динамической загрузке
    компонентов. Решает проблемы с относительными импортами.
    """
    
    @staticmethod
    def create_package(package_name: str) -> types.ModuleType:
        """
        Создает пакет Python и регистрирует его в sys.modules.
        
        Args:
            package_name: Имя пакета
            
        Returns:
            Созданный модуль
        """
        if package_name not in sys.modules:
            module = types.ModuleType(package_name)
            module.__path__ = []
            sys.modules[package_name] = module
            logging.info(f"Создан пакет Python: {package_name}")
            return module
        return sys.modules[package_name]
    
    @staticmethod
    def load_module_from_file(file_path: str, module_name: str = None, package_name: str = None) -> Optional[types.ModuleType]:
        """
        Загружает модуль из файла с поддержкой относительных импортов.
        
        Args:
            file_path: Путь к файлу с модулем
            module_name: Имя модуля (если None, берется из имени файла)
            package_name: Имя пакета (если None, модуль загружается как верхнеуровневый)
            
        Returns:
            Загруженный модуль или None в случае ошибки
        """
        try:
            if not os.path.exists(file_path):
                logging.error(f"Файл модуля не существует: {file_path}")
                return None
                
            # Определяем имя модуля из имени файла, если не указано
            if module_name is None:
                base_name = os.path.basename(file_path)
                module_name = os.path.splitext(base_name)[0]
            
            # Формируем полное имя модуля
            full_module_name = f"{package_name}.{module_name}" if package_name else module_name
            
            # Если модуль уже загружен, возвращаем его
            if full_module_name in sys.modules:
                return sys.modules[full_module_name]
            
            # Создаем пакет, если указан
            if package_name:
                PackageHelper.create_package(package_name)
            
            # Загружаем модуль
            spec = importlib.util.spec_from_file_location(full_module_name, file_path)
            if spec is None:
                logging.error(f"Не удалось создать спецификацию для модуля: {full_module_name}")
                return None
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[full_module_name] = module
            
            # Если у модуля есть родительский пакет, добавляем модуль в атрибуты пакета
            if package_name and "." not in package_name:
                parent_module = sys.modules[package_name]
                setattr(parent_module, module_name, module)
            
            # Выполняем код модуля
            spec.loader.exec_module(module)
            
            logging.info(f"Успешно загружен модуль: {full_module_name}")
            return module
            
        except Exception as e:
            logging.error(f"Ошибка при загрузке модуля из файла {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def fix_relative_imports(file_content: str, package_name: str) -> str:
        """
        Заменяет относительные импорты на абсолютные.
        
        Args:
            file_content: Содержимое файла
            package_name: Имя пакета для абсолютных импортов
            
        Returns:
            Скорректированное содержимое файла
        """
        # Заменяем "from ." на "from package_name"
        content = re.sub(r'from\s+\.', f'from {package_name}', file_content)
        
        # Заменяем "from .subpackage" на "from package_name.subpackage"
        content = re.sub(r'from\s+\.([a-zA-Z0-9_]+)', f'from {package_name}.\\1', content)
        
        return content
    
    @staticmethod
    def execute_module_content(content: str, globals_dict: Dict[str, Any] = None, module_name: str = "__main__") -> Dict[str, Any]:
        """
        Выполняет содержимое модуля с указанным globals словарем.
        
        Args:
            content: Содержимое модуля для выполнения
            globals_dict: Словарь globals (если None, создается новый)
            module_name: Имя модуля
            
        Returns:
            Словарь с результатами выполнения кода
        """
        try:
            if globals_dict is None:
                globals_dict = {
                    "__name__": module_name,
                    "__file__": f"<{module_name}>",
                    "__builtins__": __builtins__
                }
            
            # Компилируем и выполняем код
            code = compile(content, f"<{module_name}>", "exec")
            exec(code, globals_dict)
            
            return globals_dict
            
        except Exception as e:
            logging.error(f"Ошибка при выполнении кода модуля: {e}")
            import traceback
            traceback.print_exc()
            return {}
