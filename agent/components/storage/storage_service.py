import logging
import boto3
import hashlib
import requests
from typing import List, Dict, Any, Optional, Union, BinaryIO
import os
import botocore.client
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError


class StorageService:
    """
    Сервис для работы с S3-совместимым хранилищем.
    Отвечает за низкоуровневую работу с API хранилища.
    Специфически настроен для работы с Timeweb Cloud.
    """

    def __init__(self,
                 access_key: str = None,
                 secret_key: str = None,
                 bucket_name: str = None,
                 endpoint_url: str = 'https://s3.timeweb.cloud',
                 region: str = 'ru-1'):
        """
        Инициализация сервиса для работы с хранилищем.

        Args:
            access_key: Ключ доступа (можно также установить через переменную окружения S3_ACCESS_KEY)
            secret_key: Секретный ключ (можно также установить через переменную окружения S3_SECRET_KEY)
            bucket_name: Имя бакета/контейнера (можно также установить через переменную окружения S3_BUCKET_NAME)
            endpoint_url: URL для S3-совместимого API (по умолчанию для Timeweb Cloud)
            region: Регион (по умолчанию для Timeweb Cloud - ru-1)
        """
        # Получаем значения из параметров или переменных окружения
        self.access_key = access_key or os.getenv('S3_ACCESS_KEY')
        self.secret_key = secret_key or os.getenv('S3_SECRET_KEY')
        self.bucket_name = bucket_name or os.getenv('S3_BUCKET_NAME')
        self.region = region
        self.endpoint_url = endpoint_url

        # Проверяем наличие необходимых данных
        if not self.access_key or not self.secret_key:
            logging.warning("Учетные данные не указаны. Используйте параметры access_key и secret_key "
                            "или установите переменные окружения S3_ACCESS_KEY и S3_SECRET_KEY")

        if not self.bucket_name:
            logging.warning("Имя бакета/контейнера не указано. Используйте параметр bucket_name "
                            "или установите переменную окружения S3_BUCKET_NAME")

        # Создаем конфигурацию для совместимости с Timeweb Cloud
        self.s3_config = botocore.client.Config(
            s3={'addressing_style': 'path'},  # Используем path-style адресацию
            signature_version='s3v4',  # Используем SigV4 для подписи запросов
            retries={'max_attempts': 3, 'mode': 'standard'}
        )

        # Создаем клиент boto3 для S3
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=self.s3_config
        )

        # Создаем сессию для низкоуровневых запросов
        self.session = boto3.session.Session(
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )
        self.credentials = self.session.get_credentials()

        logging.info(f"StorageService initialized with endpoint {self.endpoint_url} "
                     f"and bucket {self.bucket_name}")

    def list_objects(self, prefix: str = '', max_keys: int = 1000) -> List[Dict[str, str]]:
        """
        Получает список объектов в бакете с указанным префиксом.

        Args:
            prefix: Префикс для фильтрации объектов
            max_keys: Максимальное количество объектов для получения

        Returns:
            Список метаданных объектов
        """
        try:
            response = self.s3_client.list_objects(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )

            result = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    result.append({
                        'key': obj['Key'],
                        'last_modified': str(obj['LastModified']),
                        'size': str(obj['Size']),
                        'etag': obj.get('ETag', '').strip('"')
                    })

            return result
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logging.error(f"S3 ClientError: {error_code} - {error_message}")
            return [{"error": f"{error_code}: {error_message}"}]
        except Exception as e:
            logging.error(f"Ошибка при получении списка объектов: {e}")
            return [{"error": str(e)}]

    def get_object(self, key: str) -> Optional[bytes]:
        """
        Получает объект из хранилища.

        Args:
            key: Ключ объекта

        Returns:
            Данные объекта в виде байтов или None при ошибке
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )

            return response['Body'].read()
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logging.error(f"S3 ClientError при получении объекта '{key}': {error_code} - {error_message}")
            return None
        except Exception as e:
            logging.error(f"Ошибка при получении объекта '{key}': {e}")
            return None

    def put_object(self, key: str, data: Union[bytes, str, BinaryIO],
                   metadata: Dict[str, str] = None,
                   content_type: str = None) -> bool:
        """
        Сохраняет объект в хранилище, используя низкоуровневый API для обхода проблем с хешированием.

        Args:
            key: Ключ для сохранения
            data: Данные для сохранения
            metadata: Метаданные объекта (опционально)
            content_type: Тип содержимого (опционально)

        Returns:
            True, если операция успешна
        """
        try:
            # Преобразуем строку в байты, если передана строка
            if isinstance(data, str):
                data = data.encode('utf-8')

            # Определяем content_type, если не указан
            if content_type is None:
                if isinstance(data, str) or (hasattr(data, 'name') and data.name.endswith(('.txt', '.md'))):
                    content_type = 'text/plain; charset=utf-8'
                elif hasattr(data, 'name') and data.name.endswith('.json'):
                    content_type = 'application/json; charset=utf-8'
                elif hasattr(data, 'name') and data.name.endswith('.py'):
                    content_type = 'text/x-python; charset=utf-8'
                else:
                    content_type = 'application/octet-stream'

            # Используем низкоуровневый API для прямой загрузки с собственной подписью
            url = f"{self.endpoint_url}/{self.bucket_name}/{key}"

            # Создаем headers
            headers = {
                'Content-Type': content_type,
            }

            # Добавляем метаданные, если они предоставлены
            if metadata:
                for key, value in metadata.items():
                    headers[f'x-amz-meta-{key}'] = value

            # Создаем и подписываем запрос
            request = AWSRequest(
                method='PUT',
                url=url,
                data=data,
                headers=headers
            )

            # Используем SigV4Auth для подписи запроса
            auth = SigV4Auth(self.credentials, 's3', self.region)
            auth.add_auth(request)

            # Преобразуем к формату requests
            prepared_request = request.prepare()

            # Отправляем запрос с использованием библиотеки requests
            response = requests.put(
                url=prepared_request.url,
                data=data,
                headers=prepared_request.headers
            )

            if response.status_code in [200, 201, 204]:
                logging.info(f"Объект '{key}' успешно сохранен, статус: {response.status_code}")
                return True
            else:
                logging.error(f"Ошибка при сохранении объекта '{key}': HTTP {response.status_code}, {response.text}")
                return False

        except Exception as e:
            logging.error(f"Ошибка при сохранении объекта '{key}': {e}")
            return False

    def delete_object(self, key: str) -> bool:
        """
        Удаляет объект из хранилища.

        Args:
            key: Ключ объекта

        Returns:
            True, если операция успешна
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            logging.info(f"Объект '{key}' успешно удален")
            return True
        except Exception as e:
            logging.error(f"Ошибка при удалении объекта '{key}': {e}")
            return False

    def object_exists(self, key: str) -> bool:
        """
        Проверяет существование объекта.

        Args:
            key: Ключ объекта

        Returns:
            True, если объект существует
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except ClientError as e:
            if e.response.get('Error', {}).get('Code', '') in ['NoSuchKey', '404']:
                return False
            logging.error(f"Ошибка при проверке объекта '{key}': {e}")
            return False
        except Exception as e:
            logging.error(f"Непредвиденная ошибка при проверке объекта '{key}': {e}")
            return False

    def check_connection(self) -> Dict[str, Any]:
        """
        Проверяет соединение с хранилищем.

        Returns:
            Словарь с информацией о соединении
        """
        result = {
            'success': False,
            'endpoint': self.endpoint_url,
            'bucket_name': self.bucket_name,
            'bucket_exists': False,
            'error': None
        }

        try:
            # Проверяем наличие бакета простым запросом
            self.s3_client.list_objects(
                Bucket=self.bucket_name,
                MaxKeys=1
            )

            result['success'] = True
            result['bucket_exists'] = True
            return result
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))

            if error_code == 'NoSuchBucket':
                result['error'] = f"Бакет {self.bucket_name} не существует"
            elif error_code == 'AccessDenied':
                result[
                    'error'] = f"Доступ к бакету {self.bucket_name} запрещен. Проверьте учетные данные и права доступа"
            else:
                result['error'] = f"{error_code}: {error_message}"

            return result
        except Exception as e:
            result['error'] = str(e)
            return result