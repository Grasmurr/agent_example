from .base_monitor import BaseMonitor
import re
import logging

class SSHMonitor(BaseMonitor):
    """
    Монитор SSH-соединения с расширенной поддержкой отображения 
    вывода интерактивных программ, таких как nano, vim, htop.
    """
    def __init__(self, ssh_tool):
        """
        Инициализация монитора SSH с ссылкой на SSH инструмент.
        
        Args:
            ssh_tool: Экземпляр класса SSHTool
        """
        self.ssh_tool = ssh_tool
        self.last_command = None
        self.last_output = None
        self.current_program = None  # Текущая запущенная программа (nano, vim, htop и т.д.)
        self.terminal_state = {
            "active": False,
            "screen_content": "",
            "program": None,
            "program_mode": None
        }
        
    def update_command(self, command, output):
        """
        Обновляет информацию о последней выполненной команде и её выводе.
        Обнаруживает запуск интерактивных программ.
        
        Args:
            command: Выполненная команда
            output: Вывод команды
        """
        self.last_command = command
        
        # Определяем, запущена ли интерактивная программа
        if command.strip() in ['nano', 'vim', 'vi', 'htop', 'top', 'less', 'more']:
            self.current_program = command.strip()
            self.terminal_state["active"] = True
            self.terminal_state["program"] = self.current_program
        
        # Если вывод содержит характерные признаки nano/htop
        if output:
            if "GNU nano" in output or "File:" in output and "^G Get Help" in output:
                self.current_program = "nano"
                self.terminal_state["active"] = True
                self.terminal_state["program"] = "nano"
                # Извлекаем имя файла, если возможно
                file_match = re.search(r"File: (.+?)(?:\s+Modified|\s*$)", output)
                if file_match:
                    self.terminal_state["program_mode"] = f"Редактирование файла: {file_match.group(1)}"
            elif "Tasks:" in output and "Mem:" in output and "Swp:" in output:
                self.current_program = "htop"
                self.terminal_state["active"] = True
                self.terminal_state["program"] = "htop"
                self.terminal_state["program_mode"] = "Мониторинг системы"
        
        # Сохраняем вывод для отображения
        # Для интерактивных программ сохраняем полный вывод
        if self.current_program in ['nano', 'vim', 'vi', 'htop', 'top']:
            self.last_output = output
            self.terminal_state["screen_content"] = output
        else:
            # Для обычных команд ограничиваем вывод
            if output and len(output) > 2000:
                summary = output[:950] + "\n\n...[содержимое сокращено]...\n\n" + output[-950:]
                self.last_output = summary
            else:
                self.last_output = output

    def update_terminal_state(self, state, output=None):
        """
        Обновляет текущее состояние терминала.
        
        Args:
            state: Состояние терминала ("active"/"inactive")
            output: Новый вывод терминала (если есть)
        """
        self.terminal_state["active"] = (state == "active")
        
        if output:
            self.terminal_state["screen_content"] = output
            
        if state == "inactive":
            self.current_program = None
            self.terminal_state["program"] = None
            self.terminal_state["program_mode"] = None

    def get_raw_data(self) -> str:
        """
        Получение данных о статусе SSH соединения и текущем состоянии терминала.
        
        Returns:
            Строка с информацией о статусе SSH и содержимом терминала
        """
        # Проверяем статус SSH соединения
        is_connected = False
        try:
            if hasattr(self.ssh_tool, 'channel') and self.ssh_tool.channel:
                is_connected = True
        except Exception as e:
            logging.error(f"Ошибка при проверке статуса SSH: {e}")
        
        status = "Подключен" if is_connected else "Отключен"
        
        output = [f"Статус SSH терминала: {status}"]
        
        # Добавляем информацию о состоянии терминала
        if self.terminal_state["active"] and self.terminal_state["program"]:
            program_info = f"Программа: {self.terminal_state['program']}"
            if self.terminal_state["program_mode"]:
                program_info += f" ({self.terminal_state['program_mode']})"
            output.append(program_info)
            
            # Добавляем содержимое экрана для интерактивных программ
            if self.terminal_state["screen_content"]:
                output.append("\nСодержимое экрана:")
                
                # Для htop и подобных программ вывод уже хорошо структурирован
                if self.terminal_state["program"] in ["htop", "top"]:
                    output.append(self.terminal_state["screen_content"])
                
                # Для редакторов делаем вывод более читаемым
                elif self.terminal_state["program"] in ["nano", "vim", "vi"]:
                    screen_content = self.terminal_state["screen_content"]
                    
                    # Удаляем ANSI-последовательности
                    screen_content = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', screen_content)
                    
                    # Помечаем строки с управляющими элементами
                    if "^G Get Help" in screen_content:
                        screen_content = re.sub(r'((\^[A-Z])\s+[A-Za-z\s]+)+', 
                                              '[Меню управления nano]', screen_content)
                    
                    output.append(screen_content)
        
        # Если нет активной программы, показываем последнюю команду
        elif self.last_command:
            output.append(f"\nПоследняя команда: {self.last_command}")
            
            if self.last_output:
                output.append(f"\nВывод команды:\n{self.last_output}")
        
        return "\n".join(output)

    def render(self) -> str:
        """
        Рендеринг данных о SSH соединении в XML формате.
        Не показывает монитор, если нет активного соединения или команд.
        
        Returns:
            XML представление статуса SSH или пустая строка
        """
        content = self.get_raw_data()
        
        if "Статус SSH терминала: Отключен" in content and not self.last_command:
            return ""  # Не показываем монитор если нет соединения и истории
            
        return self.wrap_in_xml(
            "ssh_terminal",
            f"\n{content}\n",
            {"source": "vm"}
        )
