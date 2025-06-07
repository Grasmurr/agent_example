from datetime import datetime
from typing import List, Optional
from .base_monitor import BaseMonitor
from lxml import etree
import re, xml, traceback, logging

class MonitoringSet:
    """
    Управляет набором мониторов и объединяет их вывод.
    """
    
    def __init__(self, monitors: List[BaseMonitor] = None):
        """
        Инициализирует набор мониторов.
        
        Args:
            monitors: Список объектов-мониторов
        """
        self.monitors = monitors or []
        logging.info(f"Initialized MonitoringSet with {len(self.monitors)} monitors")

    def add_monitor(self, monitor: BaseMonitor) -> None:
        """
        Добавляет монитор в набор.
        
        Args:
            monitor: Объект-монитор
        """
        if monitor not in self.monitors:
            self.monitors.append(monitor)
            logging.info(f"Added monitor {monitor.__class__.__name__} to monitoring set")

    def remove_monitor(self, monitor_type: str) -> None:
        """
        Удаляет монитор указанного типа из набора.
        
        Args:
            monitor_type: Имя класса монитора
        """
        for i, monitor in enumerate(self.monitors):
            if monitor.__class__.__name__ == monitor_type:
                del self.monitors[i]
                logging.info(f"Removed monitor {monitor_type} from monitoring set")
                return

    def replace_monitors(self, new_monitors: List[BaseMonitor]) -> None:
        """
        Заменяет все мониторы на новые.
        
        Args:
            new_monitors: Новый список мониторов
        """
        self.monitors = new_monitors
        logging.info(f"Replaced all monitors with {len(new_monitors)} new monitors")

    def get_chrono_mark(self) -> str:
        """
        Возвращает текущую временную метку.
        
        Returns:
            Строка с датой и временем
        """
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def indent_xml(self, elem, level=0):
        """
        Добавляет отступы к XML элементам рекурсивно без лишних пробелов перед закрывающим корневым тегом.
        
        Args:
            elem: XML элемент
            level: Уровень отступа
        """
        i = "\n" + "    " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "    "
            for child in elem:
                self.indent_xml(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if not elem.tail or not elem.tail.strip():
                elem.tail = i if level > 0 else "\n"

    def xmlescape(self, data):
        """
        Экранирует специальные XML символы и удаляет управляющие символы.
        
        Args:
            data: Исходная строка
            
        Returns:
            Экранированная строка
        """
        # Удаляем управляющие символы ANSI и другие непечатаемые символы
        data = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', data)  # Удаляем ANSI escape codes

        # Удаляем символы управления ASCII (кроме допустимых \t, \n, \r)
        data = ''.join(c if c >= ' ' or c in '\n\r\t' else '' for c in data)

        # Используем стандартное экранирование XML
        escaped_data = xml.sax.saxutils.escape(data, entities={
            "'": "&apos;",
            '"': "&quot;"
        })

        # Дополнительное экранирование спецсимволов
        escaped_data = escaped_data.replace('\n', '&#10;')
        escaped_data = escaped_data.replace('\r', '&#13;')
        escaped_data = escaped_data.replace('\t', '&#9;')

        return escaped_data

    def render(self) -> str:
        """
        Объединяет все мониторы в один структурированный документ.
        
        Returns:
            XML документ с данными всех мониторов
        """
        monitor_outputs = []

        for monitor in self.monitors:
            try:
                output = monitor.render()
                if output:
                    # Assuming monitor.render() returns valid XML, no escaping here
                    monitor_outputs.append(output)
            except Exception as e:
                logging.error(f"Error rendering monitor {monitor.__class__.__name__}: {e}")
                traceback.print_exc()

        content = '\n'.join(monitor_outputs)
        timestamp = self.get_chrono_mark()

        # Construct the raw XML structure directly
        s = (f'<monitoring_data timestamp="{timestamp}">\n{content}\n'
             f'<system_prompt>Think about current situation and act accordingly.</system_prompt>\n'
             f'</monitoring_data>')

        res = s

        try:
            # Now it should be valid XML without escape issues
            root = etree.fromstring(s)
            self.indent_xml(root)
            res = etree.tostring(root, encoding='unicode')
            if res.endswith('\n'):
                res = res.rstrip('\n')
        except Exception as e:
            traceback.print_exc()
            logging.error(f'ОШИБКА XML ВОТ ПОЛНЫЙ ТЕКСТ: {s}')
            logging.error(f'Ошибка парсинга XML: {e}')

        return res
