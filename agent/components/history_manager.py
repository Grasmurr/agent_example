# history_manager.py
import json
import logging
import redis
from typing import Optional, List, Dict, Any
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage

import time, os, re, uuid, xml
import difflib
from lxml import etree
from xml.sax.saxutils import escape
from datetime import datetime

from .utils import (serialize_message, deserialize_message, indent_xml, clean_message, remove_invalid_xml_chars,
                   xmlescape, escape_text_preserving_tags)


class HistoryManager:
    def __init__(self,
                max_history_length=10,
                redis_host: Optional[str] = None,
                redis_port: Optional[int] = None,
                redis_db: int = 0,
                redis_prefix: str = "history:",
                vector_store=None):
        self.history = []
        self.max_history_length = max_history_length
        self.redis_client = None
        self.redis_prefix = redis_prefix
        self.vector_store = vector_store

        if redis_host and redis_port:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True,
                    password=os.getenv("REDIS_PASSWORD")
                )
                logging.info("Successfully connected to Redis")
            except Exception as e:
                logging.error(f"Failed to connect to Redis: {e}")
                self.redis_client = None

    def get_redis_key(self, msg_id: str) -> str:
        """Генерирует ключ Redis для сообщения."""
        return f"{self.redis_prefix}{msg_id}"

    def _clean_message(self, message):
        """Преобразует сообщение в словарь и удаляет ненужные поля"""
        msg_dict = message.dict() if not isinstance(message, dict) else message.copy()

        fields_to_remove = [
            'response_metadata',
            'usage_metadata',
            'additional_kwargs',
            'artifact',
            'status',
            'invalid_tool_calls',
        ]

        for field in fields_to_remove:
            msg_dict.pop(field, None)

        return msg_dict

    def _recreate_message(self, msg_dict):
        """Воссоздает объекты сообщений, игнорируя ID и проверяя только контент."""
        msg_data = msg_dict.copy()
        content = msg_data.pop('content', '')

        print(f"Processing message: {msg_dict}")  # Отладочный вывод

        # Проверяем, что у нас есть контент
        if not content:
            print("Skipping message: empty content")
            return None  # Если контент пустой, не создаем сообщение

        msg_type = msg_data.get('type')

        print(f"Message type: {msg_type}")  # Проверяем, какой тип сообщения

        # Создаем сообщение в зависимости от типа
        if msg_type == 'ai':
            message = AIMessage(content=content)
        elif msg_type == 'tool':
            message = ToolMessage(content=content)
        elif msg_type == 'human':
            message = HumanMessage(content=content)
        else:
            print(f"Skipping message: unknown type {msg_type}")
            return None

        print(f"Created message: {message}")
        return message

    def _sync_with_redis(self):
        """Синхронизирует локальную историю с Redis."""
        if not self.redis_client:
            return

        # Очищаем старые сообщения из Redis
        for msg in self.history:
            msg_id = msg.get('id')
            if msg_id:
                key = self.get_redis_key(msg_id)
                if not self.redis_client.exists(key):
                    self.redis_client.set(key, self._serialize_message(msg))

    def delete_last_message(self):
        """Удаляет последнее сообщение из Redis и локальной истории."""
        if not self.history:
            logging.warning("История пуста, нечего удалять.")
            return
        logging.info(f'message: {self.history[-1]}, type: {type(self.history[-1])}')
        # message: {'content': '<monitoring_data timestamp="2025-02-14 14:10:32">\n    <telegram_chat source="telegram">\n\n</telegram_chat>\n    <tasks>No pending tasks</tasks>\n    <system_prompt>Think about current situation and act accordingly.</system_prompt>\n    </monitoring_data>', 'type': 'human', 'name': None, 'id': None, 'example': False, 'timestamp': 1739542232}

        if "monitoring_data" not in self.history[-1]['content']:
            logging.warning(f'СООБЩЕНИЕ {self.history[-1]} НЕТТ ТУТ НИКАКОГО МОНИТОРИНГА ВТФ ЭТОТ ФОРМАТ ДАННЫХ????? {type(self.history[-1])}')
            return
        
        last_message = self.history.pop()
        msg_id = last_message.get('id')

        if msg_id and self.redis_client:
            key = self.get_redis_key(msg_id)
            try:
                self.redis_client.delete(key)
                logging.info(f"Удалено последнее сообщение с ID {msg_id} из Redis")
            except Exception as e:
                logging.error(f"Не удалось удалить сообщение из Redis: {e}")

        self._load_from_redis()

        logging.info("Последнее сообщение удалено из локальной истории")

    def _load_from_redis(self):
        """Загружает историю из Redis."""
        if not self.redis_client:
            return

        # Получаем все ключи с префиксом
        keys = self.redis_client.keys(f"{self.redis_prefix}*")
        if not keys:
            return

        # Загружаем сообщения и сортируем по времени создания
        messages = []
        for key in keys:
            msg_str = self.redis_client.get(key)
            if msg_str:
                try:
                    msg = self._deserialize_message(msg_str)
                    messages.append(msg)
                except json.JSONDecodeError:
                    logging.error(f"Failed to decode message from Redis: {msg_str}")

        # Сортируем сообщения по времени и обновляем историю
        messages.sort(key=lambda x: x.get('timestamp', 0))
        self.history = messages[-self.max_history_length:]

    def _indent_xml(self, elem, level=0):
        """Добавляет отступы к XML элементам рекурсивно без лишних пробелов перед закрывающим корневым тегом."""
        i = "\n" + "    " * level

        if len(elem):  # Если есть дочерние элементы
            if not elem.text or not elem.text.strip():
                elem.text = i + "    "
            for child in elem:
                self._indent_xml(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if elem.text:
                elem.text = i + elem.text.strip()
            elif not elem.text or not elem.text.strip():
                elem.text = i

            if not elem.tail or not elem.tail.strip():
                elem.tail = i if level > 0 else "\n"

    def _add_to_vector_store(self, message):
        """Добавляет сообщение в векторное хранилище"""
        if not hasattr(self, 'vector_store'):
            return

        content = message.get('content', '')
        if not content or len(content.strip()) < 10:  # Игнорируем короткие сообщения
            return

        metadata = {
            'id': message['id'],
            'type': message['type'],
            'timestamp': message['timestamp'],
            'source': 'history_manager'
        }

        try:
            self.vector_store.add_document(content, metadata)
            logging.info(f"Added message to vector store with ID: {message['id']}")
        except Exception as e:
            logging.error(f"Failed to add message to vector store: {e}")

    def add_to_history(self, message):
        """Добавляет сообщение в историю в виде словаря"""
        cleaned = self._clean_message(message)

        # print(f'cleaned: {cleaned}')
        
        # Добавляем timestamp если его нет
        if 'timestamp' not in cleaned:
            cleaned['timestamp'] = int(time.time())

        if 'id' not in cleaned or not cleaned['id']:
            cleaned['id'] = f"{cleaned['type']}_{cleaned['timestamp']}_{uuid.uuid4().hex[:8]}"
        
        self.history.append(cleaned)

        self._add_to_vector_store(cleaned)
        
        # # Сохраняем в Redis если есть подключение
        # if self.redis_client and cleaned.get('id'):
        #     key = self.get_redis_key(cleaned['id'])
        #     try:
        #         self.redis_client.set(key, self._serialize_message(cleaned))
        #     except Exception as e:
        #         logging.error(f"Failed to save message to Redis: {e}")
        
        self.truncate_history()

    def truncate_history(self):
        self.filter_out_empty_history()
        self.history = self.history[-self.max_history_length:]
        # self.remove_duplicates_from_history()  # раскомментировали для удаления дубликатов

    def filter_out_empty_history(self):
        filtered = []
        for msg in self.history:
            # Проверяем по ключам словаря
            if msg.get('type') == 'human' and not msg.get('content'):
                continue
            filtered.append(msg)
        self.history = filtered

    def remove_duplicates_from_history(self):
        """
        Удаляет дубликаты сообщений из истории, основываясь на их содержании и типе.
        Сообщения считаются дубликатами, если у них одинаковый контент и тип.
        При обнаружении дубликатов сохраняется последнее появление сообщения.
        """
        filtered = []
        seen_messages = {}  # dict для хранения {(content, type): index}
        
        # Проходим по истории в обратном порядке, чтобы сохранить последние появления
        for i, msg in enumerate(reversed(self.history)):
            content = msg.get('content', '')
            msg_type = msg.get('type', '')
            key = (content, msg_type)
            
            # Если это новое уникальное сообщение или у него другой тип
            if key not in seen_messages:
                seen_messages[key] = i
                filtered.append(msg)
            else:
                # Логируем информацию об удалённом дубликате
                logging.info(
                    'Removed duplicate message:\n'
                    'Type: %s\n'
                    'Content: %s\n'
                    'Original position: %d\n'
                    'Duplicate position: %d',
                    msg_type, content[:100], seen_messages[key], i
                )
        
        # Восстанавливаем правильный порядок сообщений
        self.history = list(reversed(filtered))

    def get_context(self, program, query=None):
        """Собирает контекст с уникальными сообщениями, учитывая схожесть."""
        seen_messages = set()
        unique_messages = []
        res = [SystemMessage(content=program)]

        if query and self.vector_store:
            try:
                relevant_docs = self.vector_store.similarity_search_with_score(query, k=3)
                for doc, score in relevant_docs:
                    if score > 0.7:
                        msg_id = doc.metadata.get('id')
                        msg_type = doc.metadata.get('type')
                        logging.info(f'msg_type: {msg_type}, msg_id: {msg_id}')
                        if msg_type == 'ai':
                            res.append(AIMessage(content=doc.page_content))
                        elif msg_type == 'human':
                            res.append(HumanMessage(content=doc.page_content))
            except Exception as e:
                logging.error(f"Error searching vector store: {e}")

        for i in self.history:
            res.append(i)

        return res

    def remove_invalid_xml_chars(self, s: str) -> str:
        """
        Remove any characters that are invalid in XML 1.0.
        """
        return ''.join(
            ch
            for ch in s
            if (
                    ch == '\t' or ch == '\n' or ch == '\r'
                    or (0x20 <= ord(ch) <= 0xD7FF)
                    or (0xE000 <= ord(ch) <= 0xFFFD)
                    or (0x10000 <= ord(ch) <= 0x10FFFF)
            )
        )

    def xmlescape(self, data):
        """
        Escape only text content while preserving valid XML tags and removing invalid control characters.
        """

        # Remove ANSI escape codes (ESC chars and sequences)
        data = self.remove_invalid_xml_chars(data)

        # 2. If you still want to remove ANSI color codes specifically:
        data = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', data)

        # 3. Now parse and selectively escape text nodes while preserving tags:
        try:
            wrapped = f"<root>{data}</root>"
            root = etree.fromstring(wrapped)
            for element in root.iter():
                if element.text:
                    element.text = xml.sax.saxutils.escape(element.text)
                if element.tail:
                    element.tail = xml.sax.saxutils.escape(element.tail)
            # Remove the dummy root
            return etree.tostring(root, encoding='unicode')[6:-7]
        except Exception:
            # Fallback: fully escape everything
            return xml.sax.saxutils.escape(data)

    def escape_text_preserving_tags(self, text):
        text = self.remove_invalid_xml_chars(text)

        """Escape only the text nodes while preserving valid XML tags like <think>."""
        try:
            # Wrap in a dummy root to safely parse as XML
            root = etree.fromstring(f"<root>{text}</root>")

            for element in root.iter():
                if element.text:
                    element.text = xml.sax.saxutils.escape(element.text)
                if element.tail:
                    element.tail = xml.sax.saxutils.escape(element.tail)

            # Convert back to string and remove the dummy root tags
            escaped_text = etree.tostring(root, encoding='unicode')[6:-7]
            return escaped_text

        except Exception:
            # If it can't parse as XML, assume it's plain text and escape entirely
            return xml.sax.saxutils.escape(text)

    def pack_chain_output(self, messages):
        """Форматирование вывода для словарей"""

        headers = {
            "ai": "your_action",
            "tool": "tool_response"
        }

        content = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        # logging.info(f'messages: {messages}')
        
        for msg in messages:
            msg_dict = self._clean_message(msg)
            if msg_dict.get('type') == 'human':
                continue

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if msg_dict.get('content'):
                content_text = msg_dict['content']
                safe_text = self.escape_text_preserving_tags(content_text)
                # if len(safe_text) > 8100:
                #     formatted_text = safe_text[:4000] + '\n\n---TRUNCATED---\n\n' + safe_text[-4000:]
                # else:
                #     formatted_text = safe_text
                formatted_text = safe_text
                content.append(f'<{headers[msg_dict['type']]} timestamp="{timestamp}">'
                               f'\n{formatted_text}\n'
                               f'</{headers[msg_dict['type']]}>')

            elif msg_dict.get('tool_calls'):
                formatted_text = str(json.dumps(msg_dict['tool_calls']))
                content.append(f'<{headers[msg_dict['type']]} timestamp="{timestamp}>"'
                               f'\n{formatted_text}\n'
                               f'</{headers[msg_dict['type']]}>')
            else:
                logging.warning("TOOL НИЧЕГО НЕ ВЕРНУЛ")
                continue

        s = f'<journal>\n{"\n\n".join(content)}\n</journal>'
        
        if not content:
            # logging.warning("NO CONTENT")
            return
        
        try:
            root = etree.fromstring(s)
            self._indent_xml(root)
            res = etree.tostring(root, encoding='unicode')
            if res.endswith('\n'):
                res = res.rstrip('\n')

            return HumanMessage(content=res)
        except Exception as e:
            logging.error(f'ВОТ ИЗНАЧАЛЬНЫЙ КОНТЕНТ: {s}')
            raise e

    def extend_history(self, messages, callback_handler=None):
        """Добавляет сообщения с проверкой дубликатов по ID и содержимому"""
        new_messages = []
        content_hashes = []
        ai_message = None
        
        for msg in messages:
            if hasattr(msg, 'content'):
                logging.info(f'MSG_TYPE: {msg.type} LEN: {len(msg.content)}')
                
                if msg.type == 'ai':
                    ai_message = msg
                if hasattr(msg, 'tool_calls'):
                    if msg.tool_calls:
                        tool_calls = json.dumps(msg.tool_calls, ensure_ascii=False)
                        logging.info(f'TOOL CALLS!: {tool_calls}')
                        msg.content = f'{msg.content}\n{tool_calls}'
                if msg.content.strip():
                    content_hash = hash(msg.content)
                else:
                    continue
            else:
                continue
            if content_hash in content_hashes:
                continue
            content_hashes.append(content_hash)
            new_messages.append(msg)

        if new_messages:
            journal_message = self.pack_chain_output(new_messages if not ai_message else new_messages[:-1])
            logging.info(f'C_MESSAGE: {journal_message}')
            
            if journal_message:
                self.add_to_history(journal_message)
            
            if ai_message:
                if "</think>" in ai_message.content:
                    ai_message.content = f'<think>{ai_message.content}'
                    
                self.add_to_history(ai_message)
        
        if callback_handler:
            callback_handler.dump_data(self.history, 'history')
