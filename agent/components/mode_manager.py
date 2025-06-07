import os
import json
import logging
from typing import Dict, List, Optional, Any, Set


class ModeManager:
    """
    Класс для управления режимами и аспектами AI-агента.
    Загружает конфигурацию из JSON-файлов и предоставляет интерфейс
    для переключения между режимами.
    """
    
    def __init__(self, agent, aspects_dir: str, modes_dir: str, aspect_hub=None, init_mode: bool = True):
        """
        Инициализирует менеджер режимов.
        
        Args:
            agent: Экземпляр агента для обновления его компонентов
            aspects_dir: Путь к директории с аспектами
            modes_dir: Путь к директории с режимами
            init_mode: Флаг, указывающий, нужно ли сразу инициализировать режим
        """
        self.agent = agent
        self.aspects_dir = aspects_dir
        self.modes_dir = modes_dir
        self.aspect_hub = aspect_hub

        # Словари для хранения данных
        self.aspects: Dict[str, Dict[str, Any]] = {}
        self.modes: Dict[str, Dict[str, Any]] = {}
        self.mode_config: Dict[str, Any] = {}
        
        # Текущий режим
        self.current_mode_id: Optional[str] = None
        self.current_mode: Optional[Dict[str, Any]] = None
        
        # Загрузка конфигурации
        self.load_config(init_mode)


    def load_config(self, init_mode: bool = True) -> None:
        """Загружает конфигурацию аспектов и режимов из JSON-файлов.

        Args:
            init_mode: Флаг, указывающий, нужно ли сразу инициализировать режим
        """
        try:
            # Загрузка аспектов
            for filename in os.listdir(self.aspects_dir):
                if filename.endswith(".json"):
                    aspect_name = filename.split(".")[0]
                    with open(os.path.join(self.aspects_dir, filename), 'r', encoding='utf-8') as f:
                        self.aspects[aspect_name] = json.load(f)
                        logging.info(f"Loaded aspect: {aspect_name}")
            
            # Загрузка режимов
            for filename in os.listdir(self.modes_dir):
                if filename.endswith(".json") and filename != "mode_config.json":
                    mode_name = filename.split(".")[0]
                    with open(os.path.join(self.modes_dir, filename), 'r', encoding='utf-8') as f:
                        self.modes[mode_name] = json.load(f)
                        logging.info(f"Loaded mode: {mode_name}")
            
            # Загрузка конфигурации режимов
            config_path = os.path.join(self.modes_dir, "mode_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.mode_config = json.load(f)
                    logging.info("Loaded mode configuration")
            
            # Установка начального режима если запрошено
            if init_mode:
                default_mode_id = self.mode_config.get("default_mode", "1")
                self.switch_mode(default_mode_id)


            if self.aspect_hub:
                try:
                    # Загружаем режимы из S3
                    s3_modes = self.aspect_hub.list_modes()
                    for mode_info in s3_modes:
                        mode_name = mode_info['name']
                        mode_obj = self.aspect_hub.get_mode(mode_name)
                        if mode_obj:
                            try:
                                mode_data = json.loads(mode_obj.content)
                                self.modes[mode_name] = mode_data
                                logging.info(f"Loaded mode {mode_name} from S3")
                            except json.JSONDecodeError:
                                logging.error(f"Invalid JSON in S3 mode: {mode_name}")

                    # Загружаем аспекты из S3
                    s3_aspects = self.aspect_hub.list_aspects()
                    for aspect_info in s3_aspects:
                        aspect_name = aspect_info['name']
                        aspect_obj = self.aspect_hub.get_aspect(aspect_name)
                        if aspect_obj:
                            try:
                                aspect_data = json.loads(aspect_obj.content)
                                self.aspects[aspect_name] = aspect_data
                                logging.info(f"Loaded aspect {aspect_name} from S3")
                            except json.JSONDecodeError:
                                logging.error(f"Invalid JSON in S3 aspect: {aspect_name}")
                except Exception as e:
                    logging.error(f"Error loading configurations from S3: {e}")

            
        except Exception as e:
            logging.error(f"Error loading configuration: {e}")
            raise

    def load_default_mode(self):
        """
        Загружает режим по умолчанию.
        """
        try:
            default_mode_id = self.mode_config.get("default_mode", "1")
            self.switch_mode(default_mode_id)
        except Exception as e:
            logging.error(f"Error loading default mode: {e}")
            raise

    def switch_mode(self, mode_id: str) -> str:
        """
        Переключает агента на указанный режим.
        
        Args:
            mode_id: Идентификатор режима
            
        Returns:
            str: Сообщение о результате переключения
        """
        if mode_id not in self.mode_config["modes"]:
            logging.error(f"Mode ID {mode_id} not found in configuration")
            return f"Ошибка: режим с ID {mode_id} не найден."
        
        mode_name = self.mode_config["modes"][mode_id]
        if mode_name not in self.modes:
            logging.error(f"Mode {mode_name} not found")
            return f"Ошибка: конфигурация режима {mode_name} не найдена."
        
        # Установка текущего режима
        self.current_mode_id = mode_id
        self.current_mode = self.modes[mode_name]
        
        # Обновление компонентов агента
        self.update_agent_components()
        
        # Переинициализация компонентов агента
        if hasattr(self.agent, 'initialize_components'):
            self.agent.initialize_components()
            
        # Обновление executor с новыми инструментами
        if hasattr(self.agent, 'recreate_executor'):
            self.agent.recreate_executor()
        
        # Initialize Contract Mode if switching to it
        # Проверяем безопасным способом режим contract
        if mode_name == "mode_contract" and hasattr(self.agent, 'initialize_contract_mode'):
            try:
                self.agent.initialize_contract_mode()
            except Exception as e:
                logging.error(f"Error initializing contract mode: {e}")

        logging.info(f"Switched to mode {mode_id}: {self.current_mode['name']}")
        return f"Режим изменен на '{self.current_mode['name']}' (ID: {mode_id})."

    def reload_mode_from_s3(self, mode_name: str) -> bool:
        """
        Перезагружает режим из S3 хранилища.

        Args:
            mode_name: Имя режима

        Returns:
            True, если операция успешна
        """
        if not self.aspect_hub:
            logging.warning("AspectHub not available")
            return False

        try:
            mode_obj = self.aspect_hub.get_mode(mode_name)
            if not mode_obj:
                logging.warning(f"Mode {mode_name} not found in S3")
                return False

            # Загружаем новую конфигурацию режима
            mode_data = json.loads(mode_obj.content)

            # Обновляем объект режима в памяти
            self.modes[mode_name] = mode_data

            # Если этот режим сейчас активен, перезагружаем компоненты
            if self.current_mode_id and self.mode_config["modes"].get(self.current_mode_id) == mode_name:
                self.update_agent_components()

                # Переинициализируем компоненты агента
                self.agent.initialize_components()

                # Обновляем executor
                self.agent.recreate_executor()

            # Сохраняем режим на диск для резервного копирования
            mode_path = os.path.join(self.modes_dir, f"{mode_name}.json")
            with open(mode_path, 'w', encoding='utf-8') as f:
                json.dump(mode_data, f, indent=2, ensure_ascii=False)

            logging.info(f"Successfully reloaded mode {mode_name} from S3")
            return True
        except Exception as e:
            logging.error(f"Error reloading mode {mode_name}: {str(e)}")
            return False

    def reload_aspect_from_s3(self, aspect_name: str) -> bool:
        """
        Перезагружает аспект из S3 хранилища.

        Args:
            aspect_name: Имя аспекта

        Returns:
            True, если операция успешна
        """
        if not self.aspect_hub:
            logging.warning("AspectHub not available")
            return False

        try:
            aspect_obj = self.aspect_hub.get_aspect(aspect_name)
            if not aspect_obj:
                logging.warning(f"Aspect {aspect_name} not found in S3")
                return False

            # Загружаем новую конфигурацию аспекта
            aspect_data = json.loads(aspect_obj.content)

            # Обновляем объект аспекта в памяти
            self.aspects[aspect_name] = aspect_data

            # Проверяем, используется ли этот аспект в текущем режиме
            if self.current_mode and aspect_name in self.current_mode.get("aspects", []):
                # Обновляем компоненты агента
                self.update_agent_components()

                # Переинициализируем компоненты агента
                self.agent.initialize_components()

                # Обновляем executor
                self.agent.recreate_executor()

            # Сохраняем аспект на диск для резервного копирования
            aspect_path = os.path.join(self.aspects_dir, f"{aspect_name}.json")
            with open(aspect_path, 'w', encoding='utf-8') as f:
                json.dump(aspect_data, f, indent=2, ensure_ascii=False)

            logging.info(f"Successfully reloaded aspect {aspect_name} from S3")
            return True
        except Exception as e:
            logging.error(f"Error reloading aspect {aspect_name}: {str(e)}")
            return False

    def update_agent_components(self) -> None:
        """Обновляет компоненты агента на основе текущего режима."""
        if not self.current_mode:
            logging.error("Cannot update agent components: no current mode set")
            return
        
        # Сбор инструментов, мониторов и программ из всех аспектов текущего режима
        tools = set()
        monitors = set()  # Только имена мониторов
        monitors_info = []  # Полная информация о мониторах
        programs = set()
        
        for aspect_name in self.current_mode["aspects"]:
            if aspect_name not in self.aspects:
                logging.warning(f"Aspect {aspect_name} not found, skipping")
                continue
                
            aspect = self.aspects[aspect_name]
            tools.update(aspect.get("tools", []))
            
            # Обрабатываем мониторы (поддерживаем оба формата)
            for monitor_item in aspect.get("monitors", []):
                if isinstance(monitor_item, dict):
                    # Новый формат - словарь с полной информацией
                    monitors.add(monitor_item["name"])
                    monitors_info.append(monitor_item)
                else:
                    # Старый формат - просто строка
                    monitors.add(monitor_item)
            
            programs.update(aspect.get("programs", []))
        
        # Обновление инструментов агента
        self.update_tools(tools)
        
        # Обновление мониторов агента
        self.update_monitors(monitors)
        
        # Если у агента есть атрибут monitors_info, обновляем его
        if hasattr(self.agent, 'monitors_info'):
            self.agent.monitors_info = monitors_info
            logging.info(f"Updated agent monitors_info with {len(monitors_info)} entries")
        
        # Обновление программы агента
        self.update_program(programs, self.current_mode.get("default_program"))

    def update_tools(self, tools: Set[str]) -> None:
        """
        Обновляет доступные инструменты агента.
        
        Args:
            tools: Набор имен инструментов для активации
        """
        # Обновляем список активных инструментов
        logging.info(f"Updating agent tools: {tools}")
        
        # Обновление toolset в агенте
        if hasattr(self.agent, 'active_tools'):
            # Очищаем текущий список инструментов
            self.agent.active_tools = []
            # Добавляем новые инструменты
            self.agent.active_tools = list(tools)
            
            logging.info(f"Updated agent tools to: {self.agent.active_tools}")
    
    def update_monitors(self, monitors: Set[str]) -> None:
        """
        Обновляет активные мониторы агента.
        
        Args:
            monitors: Набор имен мониторов для активации
        """
        # Обновляем список активных мониторов
        logging.info(f"Updating agent monitors: {monitors}")
        
        # Обновление мониторов в агенте
        if hasattr(self.agent, 'active_monitors'):
            # Очищаем текущий список мониторов
            self.agent.active_monitors = []
            
            # Собираем список мониторов с полной информацией 
            monitors_info = []
            
            # Собираем информацию о мониторах из всех аспектов
            for aspect_name in self.current_mode["aspects"]:
                if aspect_name in self.aspects:
                    aspect = self.aspects[aspect_name]
                    
                    # Проверяем формат мониторов (старый или новый)
                    if isinstance(aspect.get("monitors", []), list) and len(aspect.get("monitors", [])) > 0:
                        if isinstance(aspect["monitors"][0], dict):
                            # Новый формат (расширенный)
                            for monitor in aspect["monitors"]:
                                if monitor["name"] in monitors:
                                    monitors_info.append(monitor)
                        else:
                            # Старый формат (простые строки)
                            for monitor_name in aspect.get("monitors", []):
                                if monitor_name in monitors:
                                    monitors_info.append({"name": monitor_name})
            
            # Сохраняем информацию о мониторах
            self.agent.monitors_info = monitors_info
            
            # Устанавливаем список имен мониторов
            self.agent.active_monitors = list(monitors)
            
            logging.info(f"Updated agent monitors to: {self.agent.active_monitors}")
    
    def update_program(self, programs: Set[str], default_program: Optional[str] = None) -> None:
        """
        Обновляет программу агента.
        
        Args:
            programs: Набор имен программ для компиляции
            default_program: Имя основной программы режима
        """
        # Обновляем список активных программ
        logging.info(f"Updating agent programs: {programs}")
        logging.info(f"Default program: {default_program}")
        
        # Обновление программы в агенте
        if hasattr(self.agent, 'active_programs'):
            # Очищаем текущий список программ
            self.agent.active_programs = []
            # Добавляем новые программы
            self.agent.active_programs = list(programs)
            
            logging.info(f"Updated agent programs to: {self.agent.active_programs}")
        
        # Установка основной программы режима, если указана
        if default_program and hasattr(self.agent, 'program'):
            # Компиляция новой программы
            if hasattr(self.agent, 'compile_program'):
                logging.info(f"Compiling program with default_program={default_program}")
                self.agent.program = self.agent.compile_program(default_program, list(programs))
                logging.info(f"Program compiled successfully")
    
    def get_current_mode_info(self) -> Dict[str, Any]:
        """
        Возвращает информацию о текущем режиме.
        
        Returns:
            Dict[str, Any]: Информация о текущем режиме
        """
        if not self.current_mode:
            return {"error": "No active mode"}
        
        active_aspects = []
        for aspect_name in self.current_mode["aspects"]:
            if aspect_name in self.aspects:
                active_aspects.append({
                    "name": self.aspects[aspect_name]["name"],
                    "description": self.aspects[aspect_name]["description"]
                })
        
        return {
            "id": self.current_mode_id,
            "name": self.current_mode["name"],
            "description": self.current_mode["description"],
            "active_aspects": active_aspects
        }
    
    def list_available_modes(self) -> List[Dict[str, Any]]:
        """
        Возвращает список доступных режимов.
        
        Returns:
            List[Dict[str, Any]]: Список доступных режимов
        """
        result = []
        for mode_id, mode_name in self.mode_config["modes"].items():
            if mode_name in self.modes:
                result.append({
                    "id": mode_id,
                    "name": self.modes[mode_name]["name"],
                    "description": self.modes[mode_name]["description"]
                })
        return result
