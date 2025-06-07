import json
import logging
import re
import xml.sax.saxutils
from lxml import etree
from typing import Any, Dict, Optional


def serialize_message(message: Dict[str, Any]) -> str:
    """Сериализует сообщение в JSON строку."""
    return json.dumps(message)


def deserialize_message(message_str: str) -> Dict[str, Any]:
    """Десериализует сообщение из JSON строки."""
    return json.loads(message_str)


def remove_invalid_xml_chars(s: str) -> str:
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


def xmlescape(data: str) -> str:
    """
    Escape only text content while preserving valid XML tags and removing invalid control characters.
    """
    # Remove invalid XML characters
    data = remove_invalid_xml_chars(data)

    # Remove ANSI escape codes (ESC chars and sequences)
    data = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', data)

    # Now parse and selectively escape text nodes while preserving tags
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


def escape_text_preserving_tags(text: str) -> str:
    """Escape only the text nodes while preserving valid XML tags."""
    text = remove_invalid_xml_chars(text)

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


def indent_xml(elem, level=0):
    """Добавляет отступы к XML элементам рекурсивно без лишних пробелов перед закрывающим корневым тегом."""
    i = "\n" + "    " * level

    if len(elem):  # Если есть дочерние элементы
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        for child in elem:
            indent_xml(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if elem.text:
            elem.text = i + elem.text.strip()
        elif not elem.text or not elem.text.strip():
            elem.text = i

        if not elem.tail or not elem.tail.strip():
            elem.tail = i if level > 0 else "\n"


def clean_message(message: Any) -> Dict[str, Any]:
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