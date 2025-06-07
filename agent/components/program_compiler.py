import os
import logging
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()

class ProgramCompiler:
    def __init__(self):
        """По умолчанию PROGRAMS_PATH=app/agent/programs"""
        self.programs_dir = os.getenv('PROGRAMS_PATH')
        if not self.programs_dir:
            raise ValueError("Путь к папке programs должен быть задан в переменной окружения PROGRAMS_PATH")
        if not os.path.exists(self.programs_dir):
            raise FileNotFoundError(f"Папка {self.programs_dir} не найдена")

    def compile_all_programs(self) -> str:
        """
        Проходится по всем файлам и папкам внутри папки PROGRAMS_PATH рекурсивно и компилирует их.
        
        Returns:
            str: Скомпилированная программа
        """
        index_file_path = os.path.join(self.programs_dir, 'default.index')
        if not os.path.exists(index_file_path):
            raise FileNotFoundError(f"Файл default.index не найден в {self.programs_dir}")

        with open(index_file_path, 'r', encoding='utf-8') as index_file:
            file_names = [line.strip() for line in index_file.readlines() if line.strip()]

        return self.compile_from_file_list(file_names)
    
    def compile_specific_programs(self, program_paths: List[str]) -> str:
        """
        Компилирует только указанные программы.
        
        Args:
            program_paths: Список путей к программам (относительно PROGRAMS_PATH)
            
        Returns:
            str: Скомпилированная программа
        """
        return self.compile_from_file_list(program_paths)
    
    def compile_from_file_list(self, file_names: List[str]) -> str:
        """
        Компилирует программу из списка файлов.
        
        Args:
            file_names: Список путей к файлам программ
            
        Returns:
            str: Скомпилированная программа
        """
        program_content = []
        
        for file_name in file_names:
            file_path = os.path.join(self.programs_dir, file_name)
            
            # Проверка на существование файла
            if not os.path.exists(file_path):
                # Проверка на существование индексного файла (для директорий)
                index_file_path = os.path.join(self.programs_dir, f"{file_name}.index")
                if os.path.exists(index_file_path):
                    # Компилируем файлы из индекса
                    with open(index_file_path, 'r', encoding='utf-8') as index_file:
                        index_files = [line.strip() for line in index_file.readlines() if line.strip()]
                    
                    # Получаем содержимое каждого файла из индекса
                    for index_file_name in index_files:
                        index_file_path = os.path.join(self.programs_dir, file_name, index_file_name)
                        if os.path.exists(index_file_path):
                            with open(index_file_path, 'r', encoding='utf-8') as f:
                                program_content.append(f.read().strip())
                        else:
                            logging.warning(f"Файл {index_file_name} из индекса {file_name}.index не найден")
                else:
                    logging.warning(f"Файл или индекс {file_name} не найден в {self.programs_dir}")
            else:
                # Обычный файл
                with open(file_path, 'r', encoding='utf-8') as f:
                    program_content.append(f.read().strip())

        return "\n\n".join(program_content)
    
    def compile_program(self, program_name: str, additional_programs: Optional[List[str]] = None) -> str:
        """
        Компилирует программу с указанным именем и дополнительными программами.
        
        Args:
            program_name: Имя основной программы (например, "default", "pricing")
            additional_programs: Список дополнительных программ
            
        Returns:
            str: Скомпилированная программа
        """
        program_content = []
        
        # Загружаем основную программу
        main_program_path = os.path.join(self.programs_dir, program_name)
        
        # Проверяем, является ли основная программа директорией с индексом
        index_file_path = os.path.join(self.programs_dir, f"{program_name}.index")
        if os.path.exists(index_file_path):
            # Загружаем файлы из индекса
            with open(index_file_path, 'r', encoding='utf-8') as index_file:
                main_files = [line.strip() for line in index_file.readlines() if line.strip()]
            
            # Компилируем файлы из индекса
            for main_file in main_files:
                file_path = os.path.join(self.programs_dir, program_name, main_file)
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        program_content.append(f.read().strip())
                else:
                    logging.warning(f"Файл {main_file} из индекса {program_name}.index не найден")
        elif os.path.exists(main_program_path):
            # Если это обычный файл
            with open(main_program_path, 'r', encoding='utf-8') as f:
                program_content.append(f.read().strip())
        else:
            logging.warning(f"Основная программа {program_name} не найдена")
        
        # Добавляем дополнительные программы
        if additional_programs:
            for additional_program in additional_programs:
                program_path = os.path.join(self.programs_dir, additional_program)
                if os.path.exists(program_path):
                    with open(program_path, 'r', encoding='utf-8') as f:
                        program_content.append(f.read().strip())
                else:
                    logging.warning(f"Дополнительная программа {additional_program} не найдена")
        
        return "\n\n".join(program_content)
