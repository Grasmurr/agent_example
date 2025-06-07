import os, traceback, logging, time, pathlib, importlib
from datetime import datetime
from dotenv import load_dotenv

from components.tools.toolset import Toolset

from langchain_core.messages import HumanMessage
from langchain_ollama import OllamaEmbeddings
from langgraph.prebuilt import create_react_agent
from langfuse.callback import CallbackHandler as LangfuseCallbackHandler
from phoenix.otel import register
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.instrumentation.langchain import LangChainInstrumentor

from threading import Thread
from multiprocessing import Manager

from components import (
    HistoryManager, InputFormatter, load_model_config, transcribe, 
    MemoryManager, VectorStore, LanguageModel, ProgramCompiler, Embedding,
    MonitoringSet, BaseMonitor, ModeManager
)

# Import monitor factory - улучшенное использование фабрики
from components.monitor_factory import MonitorFactory

from components.storage.storage_service import StorageService
from components.storage.aspect_hub import AspectHub

import redis

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s:%(message)s')


class Agent:
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    DB_PATH = os.path.join(DATA_DIR, "memories.db")

    def __init__(self):
        self.API_KEY = os.getenv('OPENAI_API_KEY')
        self.API_BASE = os.getenv("API_BASE")
        self.EMBEDDINGS_API_BASE = os.getenv('EMBEDDINGS_API_BASE')
        self.MODEL_NAME = os.getenv("MODEL")
        self.USE_OLLAMA = os.getenv("USE_OLLAMA")
        self.TG_WINDOW = int(os.getenv('TG_WINDOW'))
        self.PROGRAM = os.getenv('PROGRAM')
        self.TG_CHAT_ID = int(os.getenv('TG_CHAT_ID'))
        self.TG_BASE_THREAD_ID = int(os.getenv('TG_BASE_THREAD_ID'))


        pathlib.Path(self.DATA_DIR).mkdir(parents=True, exist_ok=True)

        if int(self.USE_OLLAMA):
            self.embedding = OllamaEmbeddings(
                model=self.MODEL_NAME,
                base_url=self.EMBEDDINGS_API_BASE
            )
        else:
            self.embedding = Embedding(self.API_KEY, self.API_BASE)

        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True
        )
        self.redis_chat_key = "agent:chat_messages"
        self.redis_inbox_key = "agent:inbox_messages"
        
        self.inbox = []
        self.history = []
        self.tg_messages = Manager().list()
        self.is_running = False
        self.tg_thread = None

        self.input_formatter = InputFormatter(
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", 6379)),
            redis_password=os.getenv("REDIS_PASSWORD")
        )

        self.langfuse_handler = LangfuseCallbackHandler()

        tracer_provider = register(
            project_name=os.getenv("PHOENIX_PROJECT_NAME", "default"),
            endpoint=f"{os.getenv('PHOENIX_COLLECTOR_ENDPOINT', 'http://193.108.115.84:6006')}/v1/traces",
            set_global_tracer_provider=False
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

        self.vector_store = VectorStore(embedding=self.embedding)
        self.memory_manager = MemoryManager(self.DB_PATH, self.vector_store)
        self.llm = LanguageModel(self.MODEL_NAME, self.API_KEY, self.API_BASE)
        
        self.aspects_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aspects")
        self.modes_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modes")
        
        pathlib.Path(self.aspects_dir).mkdir(parents=True, exist_ok=True)
        pathlib.Path(self.modes_dir).mkdir(parents=True, exist_ok=True)
        
        # Инициализация фабрики мониторов
        self.monitor_factory = MonitorFactory()
        self.monitor_factory.discover_components()
        logging.info(f"Обнаружено мониторов: {len(self.monitor_factory.registry)}")
        
        # Показываем обнаруженные мониторы для отладки
        if self.monitor_factory.registry:
            registered_monitors = ", ".join(self.monitor_factory.registry.keys())
            logging.info(f"Зарегистрированные мониторы: {registered_monitors}")
        else:
            logging.warning("Мониторы не обнаружены")
        
        # Списки для хранения активных компонентов
        self.active_tools = []
        self.active_monitors = []
        self.active_programs = []
        
        self.monitors_info = []

        self.storage_service = StorageService()
        self.aspect_hub = AspectHub(self.storage_service)
        self.toolset = Toolset(self.memory_manager, self.tg_messages, self)
        self.mode_manager = ModeManager(self, self.aspects_dir, self.modes_dir, aspect_hub=self.aspect_hub, init_mode=False)
        self.initialize_components()
        self.mode_manager.load_default_mode()
        self.recreate_executor()

    def initialize_contract_mode(self):
        logging.info("Initializing Contract Mode...")

        # Проверяем наличие необходимых инструментов
        if not hasattr(self.toolset, "staff_tool"):
            logging.error("StaffTool not available, cannot initialize Contract Mode")
            return "StaffTool not available"

        if not hasattr(self.toolset, "timer_tool"):
            logging.error("TimerTool not available, cannot initialize Contract Mode")
            return "TimerTool not available"

        if not hasattr(self.toolset, "google_sheets_tool"):
            logging.error("GoogleSheetsTool not available, cannot initialize Contract Mode")
            return "GoogleSheetsTool not available"

        # Синхронизируем задачи сотрудников с Redis
        try:
            result = self.toolset.staff_tool.sync_sheet_tasks_with_redis()
            logging.info(f"Tasks synchronized with Redis: {result}")
        except Exception as sync_error:
            logging.error(f"Error synchronizing tasks with Redis: {sync_error}")

        # Инициализируем таймеры для сотрудников
        try:
            result = self.toolset.staff_tool.setup_all_staff_timers()
            logging.info(f"Contract Mode initialized with staff timers: {result}")

            # Добавляем проверку статуса задач для каждого сотрудника
            try:
                staff_list = self.toolset.staff_tool.data_manager.get_staff_list()
                for staff in staff_list:
                    telegram_username = staff.get('telegram_username')
                    if telegram_username:
                        logging.info(f"Checking tasks for {telegram_username}")
                        tasks_summary = self.toolset.staff_tool.get_staff_tasks_summary(telegram_username)
                        logging.info(f"Tasks for {telegram_username}: {tasks_summary[:100]}...")
            except Exception as task_check_error:
                logging.error(f"Error checking staff tasks: {task_check_error}")

            return f"Contract Mode initialized successfully"
        except Exception as e:
            logging.error(f"Error initializing Contract Mode: {e}")
            return f"Error initializing Contract Mode: {str(e)}"

    def setup_task_sync_timer(self):
        """
        Настраивает таймер для периодической синхронизации задач с Redis.
        """
        try:
            if not hasattr(self.agent.toolset, "timer_tool"):
                return "TimerTool not available"

            timer_tool = self.agent.toolset.timer_tool

            timer_name = "Синхронизация задач с Redis"
            time_spec = "каждые 30 минут"

            # Создаем действие для таймера
            action = (
                "Синхронизировать задачи сотрудников с Redis. "
                "Используй staff_tool.sync_sheet_tasks_with_redis() для обновления данных в Redis."
            )

            result = timer_tool.create_timer(
                time_spec=time_spec,
                name=timer_name,
                action=action
            )

            return result

        except Exception as e:
            logging.error(f"Error setting up task sync timer: {e}")
            return f"Error setting up task sync timer: {str(e)}"

    def initialize_components(self):
        """Инициализирует компоненты на основе текущего режима и аспектов"""
        logging.info("Инициализация компонентов для текущего режима...")
        
        tool_dependencies = {"agent": self}
        
        for tool_name, tool_instance in self.toolset.tool_instances.items():
            dep_name = tool_name.replace("_tool", "") if tool_name.endswith("_tool") else tool_name
            tool_dependencies[dep_name] = tool_instance
            tool_dependencies[tool_name] = tool_instance
            
            if tool_name == "mysql_pandas_tool":
                tool_dependencies["sql_pandas_tool"] = tool_instance
        
        active_monitors = []
        
        try:
            if hasattr(self, 'monitors_info') and self.monitors_info:
                for monitor_info in self.monitors_info:
                    if "path" in monitor_info and "class" in monitor_info:
                        try:
                            module = importlib.import_module(monitor_info["path"])
                            monitor_class = getattr(module, monitor_info["class"])
                            deps = monitor_info.get("dependencies", [])
                            self.monitor_factory.register(monitor_info["name"], monitor_class, deps)
                            logging.info(f"Динамически зарегистрирован монитор {monitor_info['name']} из {monitor_info['path']}")
                        except Exception as e:
                            logging.error(f"Ошибка при динамической регистрации монитора {monitor_info['name']}: {e}")
            
            active_monitors = self.monitor_factory.create_monitors(
                self.active_monitors, 
                tool_dependencies
            )
            logging.info(f"Создано {len(active_monitors)} мониторов через factory")
        except Exception as e:
            logging.error(f"Ошибка при создании мониторов через factory: {e}")
        
        if len(active_monitors) < len(self.active_monitors):
            missing_monitors = set(self.active_monitors) - set(monitor.__class__.__name__.lower().replace('monitor', '_monitor') 
                                                      for monitor in active_monitors)
            logging.warning(f"Не удалось создать мониторы через factory: {missing_monitors}")
            
            for monitor_name in missing_monitors:
                monitor = self._create_monitor_directly(monitor_name, tool_dependencies)
                if monitor:
                    active_monitors.append(monitor)
        
        self._setup_component_relationships(active_monitors)
        
        self.monitoring_set = MonitoringSet(active_monitors)
        
        self.program = self.compile_program()
        
        logging.info(f"Компоненты для текущего режима успешно инициализированы")
    
    def _create_monitor_directly(self, monitor_name: str, dependencies):
        """Создает монитор напрямую по имени"""
        # Карта имен мониторов к модулям и классам
        monitor_map = {
            "task_monitor": ("components.monitoring.task_monitor", "TaskMonitor", ["task_tool"]),
            "telegram_chat_monitor": ("components.monitoring.tchat_monitor", "TelegramChatMonitor", ["agent"]),
            "staff_monitor": ("components.monitoring.staff_monitor", "StaffMonitor", ["staff_tool"]),
            "messages_monitor": ("components.monitoring.messages_monitor", "MessagesMonitor", ["staff_tool"]),
            "dataframe_monitor": ("components.monitoring.dataframe_monitor", "DataFrameMonitor", ["sql_pandas_tool"]),
            "sketch_monitor": ("components.monitoring.sketch_monitor", "SketchMonitor", ["sketch_tool"]),
            "ssh_monitor": ("components.monitoring.ssh_monitor", "SSHMonitor", ["ssh_tool"]),
            "google_sheets_monitor": ("components.monitoring.google_sheets_monitor", "GoogleSheetsMonitor", ["google_sheets_tool"]),
            "python_cli_monitor": ("components.monitoring.python_cli_monitor", "PythonCliMonitor", ["python_cli_tool"])
        }
        
        monitor_info = None
        if hasattr(self, 'monitors_info'):
            for info in self.monitors_info:
                if info.get("name") == monitor_name:
                    monitor_info = info
                    break
        
        # Если нашли информацию в monitors_info, используем ее
        if monitor_info and "path" in monitor_info and "class" in monitor_info:
            module_path = monitor_info["path"]
            class_name = monitor_info["class"]
            deps = monitor_info.get("dependencies", [])
        # Иначе используем встроенную карту
        elif monitor_name in monitor_map:
            module_path, class_name, deps = monitor_map[monitor_name]
        else:
            logging.warning(f"Монитор {monitor_name} не найден ни в monitors_info, ни в встроенной карте")
            return None
        
        try:
            # Импортируем модуль
            module = importlib.import_module(module_path)
            # Получаем класс
            monitor_class = getattr(module, class_name)
            
            # Собираем аргументы конструктора
            args = []
            for dep in deps:
                if dep in dependencies:
                    args.append(dependencies[dep])
                elif dep == "sql_pandas_tool" and "mysql_pandas_tool" in dependencies:
                    # Fix for dataframe_monitor - use mysql_pandas_tool if sql_pandas_tool not available
                    args.append(dependencies["mysql_pandas_tool"])
                    logging.info(f"Using mysql_pandas_tool as a replacement for sql_pandas_tool dependency")
                else:
                    logging.warning(f"Зависимость {dep} для {monitor_name} не найдена")
                    return None
            
            # Создаем экземпляр монитора
            monitor = monitor_class(*args)
            logging.info(f"Создан монитор {monitor_name} напрямую")
            return monitor
        except Exception as e:
            logging.error(f"Ошибка при создании монитора {monitor_name} напрямую: {e}")
            return None
    
    def _setup_component_relationships(self, monitors):
        """Устанавливает связи между компонентами"""
        # Связываем SSH tool и SSH monitor
        ssh_monitor = next((m for m in monitors if hasattr(m, "__class__") and 
                           m.__class__.__name__ == "SSHMonitor"), None)
        if ssh_monitor and hasattr(self.toolset, "ssh_tool") and hasattr(self.toolset.ssh_tool, 'set_monitor'):
            self.toolset.ssh_tool.set_monitor(ssh_monitor)
            logging.info("Установлена связь между ssh_tool и ssh_monitor")
    
    def recreate_executor(self):
        """Recreates executor with current tools"""
        logging.info(f"Recreating executor with tools: {self.active_tools}")

        self.history_manager = HistoryManager(
            redis_host='localhost',
            redis_port=6379,
            vector_store=self.vector_store
        )

        # Use existing monitoring_set or create new one if it doesn't exist
        if not hasattr(self, 'monitoring_set') or not self.monitoring_set:
            self.initialize_components()

        self.executor = create_react_agent(
            self.llm.instance,
            self.toolset.tools(self.active_tools),  # Pass active tools
            # interrupt_after=['tools']
        )
        logging.info("Executor recreated successfully")

    def compile_program(self, default_program=None, additional_programs=None):
        """Compiles program for agent"""
        loader = ProgramCompiler()
        
        # If main program is specified, use it with additional programs
        if default_program:
            program = loader.compile_program(default_program, additional_programs)
        # If only additional programs are specified, use them
        elif additional_programs:
            program = loader.compile_specific_programs(additional_programs)
        else:
            # Otherwise use active programs or compile all programs
            if self.active_programs:
                program = loader.compile_specific_programs(self.active_programs)
            else:
                program = loader.compile_all_programs()
        
        logging.info(f"Compiled program with {len(program.split()) if program else 0} words")
        return program

    def run(self):
        print("Starting agent run method")
        self.is_running = True
        print("Creating telegram listening thread")
        self.tg_thread = Thread(target=self.start_listening)
        print("Starting telegram thread")
        self.tg_thread.start()
        print("Telegram thread started")
        
        # Время последней проверки тайм-аутов
        last_timeout_check = time.time()
    
        while self.is_running:
            try:
                print("Main loop iteration")
    
                # Проверяем тайм-ауты задач каждые 60 секунд
                current_time = time.time()
                if current_time - last_timeout_check > 60:  # Проверяем каждую минуту
                    if hasattr(self.toolset, "task_tool"):
                        result = self.toolset.task_tool.check_timeouts()
                        logging.info(f"Task timeout check result: {result}")
                    last_timeout_check = current_time

                # Проверяем наличие задач
                pending_tasks = self.check_for_pending_tasks()
    
                # Если нет задач, делаем паузу
                if not pending_tasks:
                    print("No pending tasks, sleeping for 5 seconds")
                    time.sleep(5)
                    continue
    
                input_text = self.input_formatter.format_chat_input(
                    task_tool=self.toolset.task_tool,
                )
                # print(f"Formatted input: {input_text}")
                self.call(input_text)
            except Exception as e:
                logging.error(f"Error in main loop: {e}")
                traceback.print_exc()

    def check_for_pending_tasks(self):
        """Проверяет наличие ожидающих задач"""
        try:
            if not hasattr(self.toolset, "task_tool"):
                return False

            # Получаем все ID задач из отсортированного набора
            task_ids = self.toolset.task_tool.redis_client.zrange(self.toolset.task_tool.tasks_key, 0, -1)

            # Проверяем статус каждой задачи
            for task_id in task_ids:
                task_key = self.toolset.task_tool.task_key(int(task_id))
                status = self.toolset.task_tool.redis_client.hget(task_key, "status")

                if status == "pending":
                    return True  # Найдена хотя бы одна ожидающая задача

            return False  # Нет ожидающих задач
        except Exception as e:
            logging.error(f"Error checking for pending tasks: {e}")
            return True  # В случае ошибки предполагаем, что есть задачи, чтобы продолжить работу

    def start_listening(self):
        print("Start_listening method initiated")
        if not hasattr(self.toolset, "tg_tool"):
            logging.error("TG tool not initialized")
            return

        print("Redis client status:", self.toolset.tg_tool.redis_client)
        
        while True:
            try:
                print("Starting update loop")
                for event in self.toolset.tg_tool.process_updates():
                    logging.info(f"Got event from process_updates: {event}")
                    if (
                        'message' in event and
                        'from' in event['message'] and
                        'text' in event['message']
                    ):
                        # if event['message']['chat']['id'] != self.TG_CHAT_ID:
                        #     continue
                        
                        # if self.TG_BASE_THREAD_ID != 1:
                        #     if event['message']['message_thread_id'] != self.TG_BASE_THREAD_ID:
                        #         continue
                        
                        # Проверяем, является ли сообщение командой
                        message_text = event['message']['text']
                        
                        # Проверяем, является ли сообщение командой для переключения режима
                        # и другими специальными командами
                        if self.toolset.tg_tool.process_command(message_text, event['message']):
                            logging.info(f"Processed command: {message_text}")
                            continue
                        
                        name = event['message']['from'].get('first_name', 'Неизвестный пользователь')
                        text = message_text
                        logging.info(f"Сообщение от {name}: {text}")
                    else:
                        logging.info(event)
                    self.add_inbox_message(event)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"Error in Telegram listening: {e}")
                traceback.print_exc()

    def log_rendered_template(self, input):
        prompt = self.llm.instance.get_prompts()[0]
        logging.info(f'RENDERED TEMPLATE: {prompt.format_prompt(**input)}')

    def add_inbox_message(self, data):
        """
        Обрабатывает входящее сообщение, определяя его тип и выбирая соответствующий обработчик.
        
        Args:
            data: Данные входящего сообщения от Telegram API
        """
        # Проверка, что сообщение содержит нужные поля
        if 'message' not in data:
            logging.warning("No 'message' field in data")
            return
        
        message = data['message']
        
        try:
            # Lazy-инициализация фабрики обработчиков при первом использовании
            if not hasattr(self, 'message_handler_factory'):
                # Импортируем здесь, чтобы избежать циклических импортов
                from message_handlers import MessageHandlerFactory
                self.message_handler_factory = MessageHandlerFactory(self)
            
            # Получаем подходящий обработчик для типа сообщения
            handler = self.message_handler_factory.get_handler(message)
            
            if handler:
                # Делегируем обработку сообщения выбранному обработчику
                try:
                    handler.handle(data)
                except Exception as e:
                    logging.error(f"Error in message handler {handler.__class__.__name__}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                logging.warning(f"No handler found for message: {message.keys()}")
        except Exception as e:
            logging.error(f"Error in add_inbox_message main flow: {e}")
            import traceback
            traceback.print_exc()

    def call(self, input_from_user):
        monitoring_data = self.monitoring_set.render()
        self.history_manager.add_to_history(HumanMessage(content=monitoring_data))
        logging.info(f'MONITOR: {monitoring_data}')
        steps = []
        for step in self.executor.stream(
            {"messages": self.get_context(query=input_from_user)},
            config={"callbacks": [self.langfuse_handler], "recursion_limit": 50},
            stream_mode="updates"
        ):
            logging.info(f'STEP: {step}')
            match list(step.keys())[0]:
                case 'agent':
                    steps.extend(step['agent']['messages'])
                case 'tools':
                    steps.extend(step['tools']['messages'])
                case _:
                    steps.extend(list(step.keys())[0]['messages'])
        logging.info(f'CHAIN: {steps}')
        self.history_manager.extend_history(steps)
        # self.callbacks.flush_buffer()

    def get_relevant_memories(self, query):
        return self.memory_manager.search_similar(query)

    def rebuild_vector_store(self):
        self.memory_manager.rebuild_vector_store()


    def get_context(self, query=None):
        return self.history_manager.get_context(self.program, query=query)

    def add_message_to_redis(self, message: str):
        """Добавляет сообщение в Redis (лимитируем до 100 сообщений)"""
        self.redis_client.lpush(self.redis_chat_key, message)
        self.redis_client.ltrim(self.redis_chat_key, 0, 99)

    def get_last_messages(self, count=15) -> list:
        """Получает последние N сообщений из Redis"""
        return self.redis_client.lrange(self.redis_chat_key, 0, count - 1) or []

    def store_inbox_message(self, message: str):
        """Добавляет сообщение в inbox (непрочитанные сообщения)"""
        self.redis_client.lpush(self.redis_inbox_key, message)

    def get_unseen_messages(self) -> list:
        """Получает все непрочитанные сообщения и очищает inbox"""
        messages = self.redis_client.lrange(self.redis_inbox_key, 0, -1)
        self.redis_client.delete(self.redis_inbox_key)
        return messages

    def reload_component(self, component_type: str, name: str) -> bool:
        """
        Динамически перезагружает компонент из S3 хранилища.

        Args:
            component_type: Тип компонента ('modes', 'aspects', 'tools', 'monitors')
            name: Имя компонента

        Returns:
            True если компонент успешно перезагружен
        """
        try:
            if component_type == 'modes':
                return self.mode_manager.reload_mode_from_s3(name)
            elif component_type == 'aspects':
                return self.mode_manager.reload_aspect_from_s3(name)
            elif component_type == 'tools':
                return self._reload_tool(name)
            elif component_type == 'monitors':
                return self._reload_monitor(name)
            elif component_type == 'instructions':
                return self._reload_instruction(name)
            else:
                logging.warning(f"Unsupported component type: {component_type}")
                return False
        except Exception as e:
            logging.error(f"Error reloading component {name}: {str(e)}")
            return False

    def _reload_tool(self, name: str) -> bool:
        """
        Перезагружает инструмент из S3 хранилища.

        Args:
            name: Имя инструмента

        Returns:
            True если инструмент успешно перезагружен
        """
        tool_obj = self.aspect_hub.get_tool(name)
        if not tool_obj:
            logging.warning(f"Tool {name} not found in S3")
            return False

        try:
            # Определяем путь для сохранения инструмента
            tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "components", "tools")
            tool_path = os.path.join(tools_dir, f"{name}.py")

            # Сохраняем инструмент на диск
            with open(tool_path, 'w', encoding='utf-8') as f:
                f.write(tool_obj.content)

            logging.info(f"Tool {name} saved to {tool_path}")

            # Переинициализируем toolset для загрузки нового инструмента
            if hasattr(self.toolset, 'reload_tools'):
                self.toolset.reload_tools()
                logging.info(f"Toolset reloaded with new tool {name}")
            else:
                # Если метод reload_tools не реализован, инициализируем заново все инструменты
                self.initialize_components()
                self.recreate_executor()
                logging.info(f"Components reinitialized with new tool {name}")

            return True
        except Exception as e:
            logging.error(f"Error reloading tool {name}: {str(e)}")
            return False

    def _reload_monitor(self, name: str) -> bool:
        """
        Перезагружает монитор из S3 хранилища.

        Args:
            name: Имя монитора

        Returns:
            True если монитор успешно перезагружен
        """
        monitor_obj = self.aspect_hub.get_monitor(name)
        if not monitor_obj:
            logging.warning(f"Monitor {name} not found in S3")
            return False

        try:
            # Определяем путь для сохранения монитора
            monitors_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "components", "monitoring")
            monitor_path = os.path.join(monitors_dir, f"{name}.py")

            # Сохраняем монитор на диск
            with open(monitor_path, 'w', encoding='utf-8') as f:
                f.write(monitor_obj.content)

            logging.info(f"Monitor {name} saved to {monitor_path}")

            # Переинициализируем мониторы
            self.monitor_factory.registry.clear()
            self.monitor_factory.dependencies.clear()
            self.monitor_factory.discover_components()

            # Переинициализируем компоненты
            self.initialize_components()

            logging.info(f"Monitors reinitialized with new monitor {name}")
            return True
        except Exception as e:
            logging.error(f"Error reloading monitor {name}: {str(e)}")
            return False

    def _reload_instruction(self, name: str) -> bool:
        """
        Перезагружает инструкцию из S3 хранилища.

        Args:
            name: Имя инструкции

        Returns:
            True если инструкция успешно перезагружена
        """
        instruction_obj = self.aspect_hub.get_instruction(name)
        if not instruction_obj:
            logging.warning(f"Instruction {name} not found in S3")
            return False

        try:
            # Определяем путь для сохранения инструкции
            instructions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "programs", "instructions")
            os.makedirs(instructions_dir, exist_ok=True)
            instruction_path = os.path.join(instructions_dir, f"{name}.txt")

            # Сохраняем инструкцию на диск
            with open(instruction_path, 'w', encoding='utf-8') as f:
                f.write(instruction_obj.content)

            logging.info(f"Instruction {name} saved to {instruction_path}")

            # Перекомпилируем программу для загрузки новой инструкции
            self.program = self.compile_program()

            logging.info(f"Program recompiled with new instruction {name}")
            return True
        except Exception as e:
            logging.error(f"Error reloading instruction {name}: {str(e)}")
            return False


if __name__ == '__main__':
    load_dotenv()
    load_model_config()
    agent = Agent()
    agent.run()
