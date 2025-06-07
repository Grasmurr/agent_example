import os
import paramiko
import time
import re

class SSHTool:
    def __init__(self):
        self.hostname = os.getenv('VM_HOST')
        self.port = os.getenv('VM_PORT')
        self.username = os.getenv('VM_USER')
        self.password = os.getenv('VM_PASSWORD')
        self.ssh = self._connect()
        self.channel = self.ssh.invoke_shell(term='xterm-256color', width=100, height=40)
        self.monitor = None  # Ссылка на монитор будет установлена позже
        self.interactive_programs = ['nano', 'vim', 'vi', 'htop', 'top', 'less', 'more']
        self.current_program = None

    def _connect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.hostname, username=self.username, password=self.password, port=self.port)
        return ssh

    def run_command(self, command):
        # Проверяем, запускается ли интерактивная программа
        cmd_parts = command.strip().split()
        program = cmd_parts[0] if cmd_parts else ""
        
        is_interactive = program in self.interactive_programs
        if is_interactive:
            self.current_program = program
            
        # Отправляем команду
        self.channel.send(command + '\n')
        output = ""
        
        # Ждем выполнения команды
        start_time = time.time()
        buffer_update_time = start_time
        
        # Для интерактивных программ увеличиваем максимальное время ожидания
        max_idle_time = 10 if is_interactive else 5
        
        while True:
            if self.channel.recv_ready():
                new_output = self.channel.recv(65535).decode('utf-8', errors='replace')
                output += new_output
                
                # Обновляем буфер и сбрасываем таймер
                start_time = time.time()
                buffer_update_time = time.time()
                
                # Если прошло некоторое время с последнего обновления буфера
                # и это интерактивная программа, обновляем монитор
                if is_interactive and self.monitor and time.time() - buffer_update_time > 0.5:
                    self.monitor.update_terminal_state("active", output)
                    buffer_update_time = time.time()
            
            # Выходим из цикла если долго нет новых данных
            elif time.time() - start_time > max_idle_time:
                break
                
            time.sleep(0.1)  # Короткая пауза для предотвращения активной загрузки CPU
        
        # Если запущена интерактивная программа, обновляем состояние монитора
        if is_interactive and self.monitor:
            self.monitor.update_terminal_state("active", output)
        
        return output

    def detect_program_exit(self, output):
        """Определяет, завершилась ли интерактивная программа"""
        if not self.current_program:
            return False
            
        # Признаки завершения разных программ
        if self.current_program == 'nano':
            if re.search(r'\n\$\s*$|\n#\s*$', output):
                return True
        elif self.current_program in ['vim', 'vi']:
            if re.search(r'\n\$\s*$|\n#\s*$', output):
                return True
        elif self.current_program in ['htop', 'top']:
            if re.search(r'\n\$\s*$|\n#\s*$', output):
                return True
        
        return False

    def terminal(self, input: str) -> str:
        """Send input to stdin of your virtual machine running linux using SSH in terminal mode."""
        output = self.run_command(input)
        
        # Обновляем монитор
        if hasattr(self, 'monitor') and self.monitor:
            self.monitor.update_command(input, output)
            
            # Проверяем, завершилась ли программа
            if self.current_program and self.detect_program_exit(output):
                self.current_program = None
                self.monitor.update_terminal_state("inactive")
        
        return output

    def set_monitor(self, monitor):
        """Устанавливает ссылку на монитор SSH."""
        self.monitor = monitor
