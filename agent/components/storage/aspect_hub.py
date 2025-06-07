import json
import os
import logging
from typing import List, Dict, Any, Optional, Union


class AspectHubObject:
    """
    Класс для представления объектов AspectHub с унифицированным интерфейсом.
    """

    def __init__(self, name: str, description: str, content: str):
        """
        Инициализация объекта.

        Args:
            name: Имя объекта
            description: Описание объекта
            content: Содержимое объекта
        """
        self.name = name
        self.description = description
        self.content = content

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует объект в словарь"""
        return {
            'name': self.name,
            'description': self.description,
            'content': self.content
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AspectHubObject':
        """Создает объект из словаря"""
        return cls(
            name=data.get('name', ''),
            description=data.get('description', ''),
            content=data.get('content', '')
        )


class AspectHub:
    """
    Сервис для управления объектами агента в S3 хранилище.
    Поддерживает работу с режимами, аспектами, инструкциями, инструментами и мониторами.
    """

    # Маппинг типов объектов на расширения файлов
    OBJECT_TYPES = {
        'modes': '.json',
        'aspects': '.json',
        'instructions': '.txt',
        'tools': '.py',
        'monitors': '.py'
    }

    def __init__(self, storage_service):
        """
        Инициализация сервиса.

        Args:
            storage_service: Экземпляр StorageService для работы с хранилищем
        """
        self.storage = storage_service
        logging.info("AspectHub initialized with StorageService")

    def _get_prefix(self, object_type: str) -> str:
        """
        Возвращает префикс для хранения определенного типа объектов.

        Args:
            object_type: Тип объекта ('modes', 'aspects', etc.)

        Returns:
            Префикс для S3 ключа
        """
        if object_type not in self.OBJECT_TYPES:
            raise ValueError(f"Unsupported object type: {object_type}")

        return f"{object_type}/"

    def _get_extension(self, object_type: str) -> str:
        """
        Возвращает расширение файла для типа объекта.

        Args:
            object_type: Тип объекта

        Returns:
            Расширение файла
        """
        return self.OBJECT_TYPES.get(object_type, '')

    def _parse_metadata(self, key: str, content: str, object_type: str) -> Dict[str, Any]:
        """
        Извлекает метаданные (имя и описание) из содержимого объекта.

        Args:
            key: Ключ объекта
            content: Содержимое объекта
            object_type: Тип объекта

        Returns:
            Словарь с метаданными (name, description)
        """
        # Извлекаем имя из ключа
        filename = os.path.basename(key)
        name = os.path.splitext(filename)[0]

        # По умолчанию описание пустое
        description = ""

        # Извлекаем описание в зависимости от типа объекта
        if object_type in ('modes', 'aspects'):
            # Для JSON-файлов пытаемся извлечь описание из содержимого
            try:
                data = json.loads(content)
                description = data.get('description', '')
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse JSON from {key}")
        elif object_type == 'instructions':
            # Для TXT-файлов используем первую непустую строку как описание
            lines = content.split('\n')
            for line in lines:
                if line.strip():
                    description = line.strip()
                    break
        elif object_type in ('tools', 'monitors'):
            # Для PY-файлов ищем описание в docstring
            lines = content.split('\n')
            docstring_started = False
            docstring_lines = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    if docstring_started:
                        # Конец docstring
                        break
                    else:
                        # Начало docstring
                        docstring_started = True
                        # Если docstring на одной строке
                        if stripped.endswith('"""') or stripped.endswith("'''"):
                            description = stripped.strip('"""').strip("'''").strip()
                            break
                        else:
                            # Многострочный docstring
                            # Убираем открывающие кавычки
                            if '"""' in stripped:
                                docstring_lines.append(stripped.split('"""', 1)[1])
                            elif "'''" in stripped:
                                docstring_lines.append(stripped.split("'''", 1)[1])
                elif docstring_started:
                    # Внутри docstring
                    if '"""' in stripped or "'''" in stripped:
                        # Конец docstring
                        if '"""' in stripped:
                            docstring_lines.append(stripped.split('"""', 1)[0])
                        elif "'''" in stripped:
                            docstring_lines.append(stripped.split("'''", 1)[0])
                        break
                    else:
                        docstring_lines.append(stripped)

            if docstring_lines:
                description = " ".join(docstring_lines).strip()

        return {
            'name': name,
            'description': description
        }

    def list_objects(self, object_type: str) -> List[Dict[str, str]]:
        """
        Возвращает список объектов указанного типа с их именами и описаниями.

        Args:
            object_type: Тип объекта ('modes', 'aspects', etc.)

        Returns:
            Список словарей с полями name и description
        """
        try:
            if object_type not in self.OBJECT_TYPES:
                logging.error(f"Unsupported object type: {object_type}")
                return []

            prefix = self._get_prefix(object_type)
            objects = self.storage.list_objects(prefix)

            # Проверяем на ошибку в ответе
            if objects and isinstance(objects, list) and len(objects) > 0 and "error" in objects[0]:
                logging.error(f"Error listing objects with prefix {prefix}: {objects[0]['error']}")
                return []

            result = []
            for obj in objects:
                key = obj['key']

                # Пропускаем "директории"
                if key.endswith('/'):
                    continue

                try:
                    # Получаем содержимое объекта
                    content_bytes = self.storage.get_object(key)
                    if content_bytes is None:
                        logging.error(f"Failed to get content for {key}")
                        continue

                    content = content_bytes.decode('utf-8')

                    # Извлекаем метаданные
                    metadata = self._parse_metadata(key, content, object_type)

                    result.append({
                        'name': metadata['name'],
                        'description': metadata['description']
                    })
                except Exception as e:
                    logging.error(f"Error processing object {key}: {str(e)}")

            return result
        except Exception as e:
            logging.error(f"Error listing objects of type {object_type}: {str(e)}")
            return []

    def get_object(self, object_type: str, name: str) -> Optional[AspectHubObject]:
        """
        Возвращает объект указанного типа по имени.

        Args:
            object_type: Тип объекта ('modes', 'aspects', etc.)
            name: Имя объекта

        Returns:
            Объект AspectHubObject или None, если объект не найден
        """
        try:
            if object_type not in self.OBJECT_TYPES:
                logging.error(f"Unsupported object type: {object_type}")
                return None

            extension = self._get_extension(object_type)
            prefix = self._get_prefix(object_type)
            key = f"{prefix}{name}{extension}"

            # Проверяем существование объекта
            if not self.storage.object_exists(key):
                logging.info(f"Object {key} does not exist")
                return None

            # Получаем содержимое объекта
            content_bytes = self.storage.get_object(key)
            if content_bytes is None:
                logging.error(f"Failed to get content for {key}")
                return None

            content = content_bytes.decode('utf-8')

            # Извлекаем метаданные
            metadata = self._parse_metadata(key, content, object_type)

            # Создаем и возвращаем объект
            return AspectHubObject(
                name=metadata['name'],
                description=metadata['description'],
                content=content
            )
        except Exception as e:
            logging.error(f"Error retrieving object {name} of type {object_type}: {str(e)}")
            return None

    def put_object(self, object_type: str, name: str,
                   description: str, content: str) -> bool:
        """
        Сохраняет объект в хранилище.

        Args:
            object_type: Тип объекта ('modes', 'aspects', etc.)
            name: Имя объекта
            description: Описание объекта
            content: Содержимое объекта

        Returns:
            True, если операция успешна
        """
        try:
            if object_type not in self.OBJECT_TYPES:
                logging.error(f"Unsupported object type: {object_type}")
                return False

            extension = self._get_extension(object_type)
            prefix = self._get_prefix(object_type)
            key = f"{prefix}{name}{extension}"

            # Для JSON-файлов, встраиваем описание в содержимое
            modified_content = content
            if object_type in ('modes', 'aspects'):
                try:
                    data = json.loads(content)
                    data['description'] = description
                    modified_content = json.dumps(data, indent=2, ensure_ascii=False)
                except json.JSONDecodeError:
                    logging.warning(f"Cannot embed description in invalid JSON for {key}")

            # Определяем content_type на основе расширения
            content_type = None
            if extension == '.json':
                content_type = "application/json; charset=utf-8"
            elif extension == '.txt':
                content_type = "text/plain; charset=utf-8"
            elif extension == '.py':
                content_type = "text/x-python; charset=utf-8"

            # Метаданные для объекта
            metadata = {
                'description': description[:255]  # Ограничиваем длину для метаданных
            }

            # Сохраняем объект
            success = self.storage.put_object(
                key=key,
                data=modified_content,
                metadata=metadata,
                content_type=content_type
            )

            return success
        except Exception as e:
            logging.error(f"Error saving object {name} of type {object_type}: {str(e)}")
            return False

    def delete_object(self, object_type: str, name: str) -> bool:
        """
        Удаляет объект из хранилища.

        Args:
            object_type: Тип объекта ('modes', 'aspects', etc.)
            name: Имя объекта

        Returns:
            True, если операция успешна
        """
        try:
            if object_type not in self.OBJECT_TYPES:
                logging.error(f"Unsupported object type: {object_type}")
                return False

            extension = self._get_extension(object_type)
            prefix = self._get_prefix(object_type)
            key = f"{prefix}{name}{extension}"

            # Проверяем существование объекта
            if not self.storage.object_exists(key):
                logging.warning(f"Object {key} does not exist, nothing to delete")
                return True  # Считаем успехом, если объекта уже нет

            # Удаляем объект
            return self.storage.delete_object(key)
        except Exception as e:
            logging.error(f"Error deleting object {name} of type {object_type}: {str(e)}")
            return False

    # ======== Обертки для конкретных типов объектов ========

    def list_modes(self) -> List[Dict[str, Any]]:
        """Список режимов"""
        return self.list_objects('modes')

    def list_aspects(self) -> List[Dict[str, Any]]:
        """Список аспектов"""
        return self.list_objects('aspects')

    def list_instructions(self) -> List[Dict[str, Any]]:
        """Список инструкций"""
        return self.list_objects('instructions')

    def list_tools(self) -> List[Dict[str, Any]]:
        """Список инструментов"""
        return self.list_objects('tools')

    def list_monitors(self) -> List[Dict[str, Any]]:
        """Список мониторов"""
        return self.list_objects('monitors')

    def get_mode(self, name: str) -> Optional[AspectHubObject]:
        """Получение режима по имени"""
        return self.get_object('modes', name)

    def get_aspect(self, name: str) -> Optional[AspectHubObject]:
        """Получение аспекта по имени"""
        return self.get_object('aspects', name)

    def get_instruction(self, name: str) -> Optional[AspectHubObject]:
        """Получение инструкции по имени"""
        return self.get_object('instructions', name)

    def get_tool(self, name: str) -> Optional[AspectHubObject]:
        """Получение инструмента по имени"""
        return self.get_object('tools', name)

    def get_monitor(self, name: str) -> Optional[AspectHubObject]:
        """Получение монитора по имени"""
        return self.get_object('monitors', name)

    def put_mode(self, name: str, description: str, content: str) -> bool:
        """Сохранение режима"""
        return self.put_object('modes', name, description, content)

    def put_aspect(self, name: str, description: str, content: str) -> bool:
        """Сохранение аспекта"""
        return self.put_object('aspects', name, description, content)

    def put_instruction(self, name: str, description: str, content: str) -> bool:
        """Сохранение инструкции"""
        return self.put_object('instructions', name, description, content)

    def put_tool(self, name: str, description: str, content: str) -> bool:
        """Сохранение инструмента"""
        return self.put_object('tools', name, description, content)

    def put_monitor(self, name: str, description: str, content: str) -> bool:
        """Сохранение монитора"""
        return self.put_object('monitors', name, description, content)

    def patch_for_timeweb(self) -> bool:
        """
        Патчит внутренние методы для работы с Timeweb Cloud S3.
        В этой реализации патч уже встроен в логику методов.
        """
        logging.info("AspectHub already patched for Timeweb Cloud")
        return True