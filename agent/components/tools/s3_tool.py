import logging
import json
from typing import List, Dict, Any, Optional, Union


class S3Tool:
    """
    Инструмент для управления объектами в S3 хранилище.
    Предоставляет высокоуровневый интерфейс для агента.
    """

    def __init__(self, agent):
        """
        Инициализация инструмента.

        Args:
            agent: Экземпляр агента
        """
        self.agent = agent
        self.aspect_hub = agent.aspect_hub
        self.storage_service = self.aspect_hub.storage

        logging.info(f"S3Tool initialized")

    def list_s3_objects(self, prefix: str = '') -> str:
        """
        Получает список объектов в S3 хранилище с указанным префиксом.

        Args:
            prefix: Префикс для фильтрации объектов (например, "aspects/" или "modes/")

        Returns:
            Форматированная строка с результатами
        """
        try:
            if not self.storage_service:
                return "Ошибка: StorageService не инициализирован"

            objects = self.storage_service.list_objects(prefix=prefix)

            # Проверяем наличие ошибок в ответе
            if objects and isinstance(objects, list) and len(objects) > 0 and "error" in objects[0]:
                return f"Ошибка при получении списка объектов: {objects[0]['error']}"
            if not objects:
                return f"Объекты с префиксом '{prefix}' не найдены в хранилище S3"
            result = f"Найдено {len(objects)} объектов в S3 с префиксом '{prefix or '[корневая директория]'}':\n\n"

            # Группируем объекты по директориям
            directories = {}
            for obj in objects:
                key = obj['key']
                parts = key.split('/')
                if len(parts) > 1:
                    dir_name = parts[0] + "/"
                    if dir_name not in directories:
                        directories[dir_name] = []
                    directories[dir_name].append(obj)
                else:
                    # Корневые файлы
                    if "root" not in directories:
                        directories["root"] = []
                    directories["root"].append(obj)
            for dir_name, dir_objects in directories.items():
                if dir_name == "root":
                    result += "Файлы в корневой директории:\n"
                else:
                    result += f"Директория '{dir_name}':\n"

                for obj in dir_objects:
                    key = obj['key']
                    size = obj['size']
                    last_modified = obj['last_modified'].split(".")[0].replace("T", " ")  # Форматируем дату

                    # Для файлов в директориях показываем только имя файла
                    if "/" in key and dir_name != "root":
                        filename = key.split("/")[-1]
                        if filename:  # Пропускаем пустые имена (это сами директории)
                            result += f"  - {filename} ({size} байт, изменен {last_modified})\n"
                    else:
                        result += f"  - {key} ({size} байт, изменен {last_modified})\n"

                result += "\n"

            return result

        except Exception as e:
            logging.error(f"Ошибка в list_s3_objects: {e}")
            return f"Произошла ошибка при получении списка объектов из S3: {str(e)}"

    def get_s3_object(self, key: str) -> str:
        """
        Получает содержимое объекта из S3.

        Args:
            key: Ключ объекта

        Returns:
            Содержимое объекта или сообщение об ошибке
        """
        try:
            if not self.storage_service:
                return "Ошибка: StorageService не инициализирован"

            # Проверяем существование объекта
            if not self.storage_service.object_exists(key):
                return f"Объект с ключом '{key}' не найден в хранилище S3"

            # Получаем объект
            content = self.storage_service.get_object(key)

            if content is None:
                return f"Ошибка при получении объекта '{key}'"

            try:
                # Пробуем декодировать как текст (UTF-8)
                text_content = content.decode('utf-8')

                # Определяем тип файла по расширению
                if key.endswith(".json"):
                    # Для JSON файлов пытаемся форматировать вывод
                    try:
                        json_data = json.loads(text_content)
                        return f"Содержимое объекта '{key}':\n\n{json.dumps(json_data, indent=2, ensure_ascii=False)}"
                    except json.JSONDecodeError:
                        # Если не удалось распарсить как JSON, выводим как обычный текст
                        pass

                # Для других текстовых файлов или если не удалось распарсить JSON
                return f"Содержимое объекта '{key}':\n\n{text_content}"

            except UnicodeDecodeError:
                # Если не удалось декодировать как текст, считаем бинарным
                return f"Объект '{key}' содержит двоичные данные размером {len(content)} байт"

        except Exception as e:
            logging.error(f"Ошибка в get_s3_object: {e}")
            return f"Произошла ошибка при получении объекта '{key}' из S3: {str(e)}"

    def put_s3_object(self, key: str, content: str, description: str = "") -> str:
        """
        Сохраняет объект в S3.

        Args:
            key: Ключ объекта
            content: Содержимое объекта
            description: Описание объекта (для метаданных)

        Returns:
            Результат операции
        """
        try:
            if not self.storage_service:
                return "Ошибка: StorageService не инициализирован"

            # Определяем тип контента по расширению
            content_type = None
            if key.endswith(".json"):
                content_type = "application/json; charset=utf-8"
                # Проверяем валидность JSON
                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    return f"Ошибка: Невалидный JSON: {str(e)}"
            elif key.endswith((".txt", ".md")):
                content_type = "text/plain; charset=utf-8"
            elif key.endswith(".html"):
                content_type = "text/html; charset=utf-8"
            elif key.endswith(".py"):
                content_type = "text/x-python; charset=utf-8"

            # Создаем метаданные
            metadata = {"description": description[:255]} if description else None

            # Сохраняем объект
            success = self.storage_service.put_object(
                key=key,
                data=content,
                metadata=metadata,
                content_type=content_type
            )

            if success:
                return f"Объект '{key}' успешно сохранен в S3"
            else:
                return f"Не удалось сохранить объект '{key}' в S3"

        except Exception as e:
            logging.error(f"Ошибка в put_s3_object: {e}")
            return f"Произошла ошибка при сохранении объекта '{key}' в S3: {str(e)}"

    def delete_s3_object(self, key: str) -> str:
        """
        Удаляет объект из S3.

        Args:
            key: Ключ объекта

        Returns:
            Результат операции
        """
        try:
            if not self.storage_service:
                return "Ошибка: StorageService не инициализирован"

            # Проверяем существование объекта
            if not self.storage_service.object_exists(key):
                return f"Объект с ключом '{key}' не найден в хранилище S3"

            # Удаляем объект
            success = self.storage_service.delete_object(key)

            if success:
                return f"Объект '{key}' успешно удален из S3"
            else:
                return f"Не удалось удалить объект '{key}' из S3"

        except Exception as e:
            logging.error(f"Ошибка в delete_s3_object: {e}")
            return f"Произошла ошибка при удалении объекта '{key}' из S3: {str(e)}"

    def check_s3_connection(self) -> str:
        """
        Проверяет соединение с S3 хранилищем.

        Returns:
            Результат проверки
        """
        try:
            if not self.storage_service:
                return "Ошибка: StorageService не инициализирован"

            connection_info = self.storage_service.check_connection()

            if connection_info['success']:
                if connection_info['bucket_exists']:
                    # Получаем количество объектов
                    objects = self.storage_service.list_objects(max_keys=100)
                    object_count = len(objects) if isinstance(objects, list) else 0

                    return (f"Соединение с S3 успешно установлено.\n"
                            f"Хранилище: {self.storage_service.endpoint_url}\n"
                            f"Бакет: {self.storage_service.bucket_name}\n"
                            f"Объектов найдено: {object_count}")
                else:
                    return f"Соединение с S3 успешно, но бакет '{self.storage_service.bucket_name}' не существует"
            else:
                return f"Ошибка соединения с S3: {connection_info.get('error', 'Неизвестная ошибка')}"

        except Exception as e:
            logging.error(f"Ошибка в check_s3_connection: {e}")
            return f"Произошла ошибка при проверке соединения с S3: {str(e)}"

    def reload_component(self, component_type: str, name: str) -> str:
        """
        Перезагружает компонент из S3 хранилища.

        Args:
            component_type: Тип компонента ('modes', 'aspects', 'tools', 'monitors', 'instructions')
            name: Имя компонента

        Returns:
            Результат операции
        """
        try:
            if not self.agent:
                return "Ошибка: ссылка на агента не установлена"

            # Делегируем вызов методу reload_component агента
            success = self.agent.reload_component(component_type, name)

            if success:
                return f"Компонент '{name}' типа '{component_type}' успешно перезагружен"
            else:
                return f"Не удалось перезагрузить компонент '{name}' типа '{component_type}'"

        except Exception as e:
            logging.error(f"Ошибка в reload_component: {e}")
            return f"Произошла ошибка при перезагрузке компонента '{name}' типа '{component_type}': {str(e)}"

    def patch_aspect_hub_for_timeweb(self) -> str:
        """
        Патчит методы AspectHub для работы с Timeweb Cloud S3.

        Returns:
            Результат операции
        """
        try:
            if not hasattr(self.aspect_hub, 'storage'):
                self.aspect_hub.storage = self.storage_service
                logging.info("Установлена ссылка на StorageService в AspectHub")
            if hasattr(self.aspect_hub, 'patch_for_timeweb'):
                success = self.aspect_hub.patch_for_timeweb()
                if success:
                    return "AspectHub успешно патчен для работы с Timeweb Cloud S3"
                else:
                    return "Не удалось патчить AspectHub для работы с Timeweb Cloud S3"

            return "AspectHub успешно настроен для работы с Timeweb Cloud S3"

        except Exception as e:
            logging.error(f"Ошибка в patch_aspect_hub_for_timeweb: {e}")
            return f"Произошла ошибка при патчинге AspectHub: {str(e)}"