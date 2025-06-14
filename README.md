# AI Agent Project

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg)

Интеллектуальный AI-агент для автоматизации бизнес-процессов с поддержкой множественных режимов работы, управления сотрудниками и интеграции с внешними сервисами.

## Содержание

- [Возможности](#возможности)
- [Структура проекта](#структура-проекта)
- [Установка и настройка](#установка-и-настройка)
- [Запуск](#запуск)
- [Режимы работы](#режимы-работы)
- [Основные команды](#основные-команды)
- [Архитектура](#архитектура)
- [Разработка](#разработка)
- [Безопасность](#безопасность)

## Возможности

### Основные функции

- **Многорежимная архитектура** - переключение между различными режимами работы (разработка, анализ данных, управление контрактами)
- **Управление сотрудниками** - автоматизированное планирование задач, отчетность, коммуникация через Telegram
- **Анализ данных** - интеграция с MySQL, pandas, Google Sheets для обработки и анализа данных
- **Долгосрочная память** - векторное хранилище на базе ChromaDB для контекстной памяти
- **Планировщик задач** - система таймеров и автоматического выполнения действий
- **SSH доступ** - удаленное управление виртуальными машинами и выполнение команд

### Интеграции

| Сервис | Описание |
|--------|----------|
| :robot: **Telegram Bot API** | Основной интерфейс взаимодействия |
| :bar_chart: **Google Sheets** | Синхронизация задач и данных |
| :card_file_box: **MySQL/Redis** | Хранение данных и очередей |
| :link: **S3-совместимое хранилище** | Backup компонентов системы |
| :brain: **LangChain + LLM** | Обработка естественного языка |
| :zap: **Kafka** | Обработка очередей задач |

## Структура проекта

```
├── agent/                          # Основное приложение агента
│   ├── components/                 # Ядро системы
│   │   ├── tools/                 # Инструменты агента
│   │   ├── monitoring/            # Система мониторинга
│   │   └── storage/               # Работа с хранилищами
│   ├── aspects/                   # Конфигурации аспектов
│   ├── modes/                     # Режимы работы агента
│   ├── message_handlers/          # Обработчики сообщений
│   └── agent.py                   # Главный файл агента
├── tg_webhook/                    # Telegram webhook сервер
├── models/                        # Модели данных
└── main.py                       # Kafka queue processor
```

## Установка и настройка

### Требования

- Python 3.8+
- Redis Server
- MySQL Server
- ChromaDB

### Установка зависимостей

```bash
pip install -r agent/requirements.txt
```

### Переменные окружения

Создайте файл `.env` с необходимыми переменными:

```bash
# API ключи для LLM
OPENAI_API_KEY=your_openai_api_key
API_BASE=https://api.openai.com/v1
MODEL=gpt-4

# Или для Ollama
USE_OLLAMA=0
EMBEDDINGS_API_BASE=http://localhost:11434

# База данных
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_user
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=your_database

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Telegram
TG_BOT_TOKEN=your_telegram_bot_token
TG_CHAT_ID=your_chat_id
TG_BASE_THREAD_ID=1
TG_WEBHOOK_URL=https://your-domain.com/webhook

# Google Sheets
GOOGLE_FILE_PATH=path/to/service_account.json
GOOGLE_SHEET_ID=your_google_sheet_id

# S3 Storage
S3_ACCESS_KEY=your_s3_access_key
S3_SECRET_KEY=your_s3_secret_key
S3_BUCKET_NAME=your_bucket_name

# VM доступ
VM_HOST=your_vm_host
VM_PORT=22
VM_USER=your_vm_user
VM_PASSWORD=your_vm_password

# Прочее
MACHINE_NAME=your_machine_name
PROGRAMS_PATH=path/to/programs
```

### Конфигурация модели

Создайте файл конфигурации в `model_configs/`:

```toml
# model_configs/openai.toml
api_key = "your_openai_api_key"
api_base = "https://api.openai.com/v1"
model = "gpt-4"
llm_provider = "openai"
temperature = 0.7
```

Обновите `model_configs/current.index`:

```
openai
```

## Запуск

### 1. Запуск Telegram webhook сервера

```bash
cd tg_webhook
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. Запуск основного агента

```bash
cd agent
python agent.py
```

### 3. Запуск обработчика очередей Kafka (опционально)

```bash
python main.py
```

## Режимы работы

Агент поддерживает несколько режимов работы:

### Доступные режимы

| ID | Режим | Описание |
|----|-------|----------|
| 1 | **Basic Mode** | Минимальная функциональность |
| 2 | **Development Mode** | Полный доступ к VM и инструментам разработки |
| 3 | **Data Analysis Mode** | Анализ данных с pandas и базами данных |
| 4 | **Pricing Mode** | Управление ценообразованием |
| 5 | **Contract Mode** | Работа с договорами и сотрудниками |

### Переключение режимов

Через Telegram:

```
/modes - показать доступные режимы
/set_mode 2 - переключиться на режим разработки
/current_mode - показать текущий режим
```

## Основные команды

### Управление задачами

```python
create_task("описание")      # создать задачу
finish_task(id)              # завершить задачу
show_pending_tasks()         # показать активные задачи
```

### Работа с сотрудниками

```python
open_telegram_chat("@username")                    # открыть чат с сотрудником
send_telegram_message_to("@username", "сообщение") # отправить сообщение
get_staff_tasks_summary("@username")               # получить сводку задач сотрудника
```

### Анализ данных

```python
query_to_df("SELECT * FROM table", "df_name")  # выполнить SQL запрос
execute_pandas("df.head()")                     # выполнить pandas операцию
update_sheet_from_df("df_name")                 # обновить Google Sheets из DataFrame
```

### Работа с таймерами

```python
create_timer("через 5 минут", "название", action="действие")  # создать таймер
list_timers()                                                  # показать активные таймеры
```

## Архитектура

### Компоненты системы

- **Agent** - основной класс агента
- **ModeManager** - управление режимами работы
- **Toolset** - набор инструментов
- **MonitoringSet** - система мониторинга
- **MemoryManager** - управление долгосрочной памятью
- **VectorStore** - векторное хранилище для поиска

### Аспекты (Aspects)

Аспекты определяют набор инструментов, мониторов и программ для конкретной функциональности:

- **staff_aspect** - управление сотрудниками
- **pandas_aspect** - анализ данных
- **vm_aspect** - работа с виртуальными машинами
- **telegram_aspect** - Telegram коммуникация

## Разработка

### Добавление нового инструмента

1. Создайте файл `components/tools/your_tool.py`:

```python
class YourTool:
    def __init__(self, dependency):
        self.dependency = dependency

    def your_function(self, param: str) -> str:
        """Описание функции для LLM"""
        return f"Result: {param}"
```

2. Инструмент автоматически будет обнаружен и зарегистрирован

### Добавление нового монитора

1. Создайте файл `components/monitoring/your_monitor.py`:

```python
from .base_monitor import BaseMonitor

class YourMonitor(BaseMonitor):
    def get_raw_data(self) -> str:
        return "monitoring data"

    def render(self) -> str:
        return self.wrap_in_xml("your_monitor", self.get_raw_data())
```

### Создание нового аспекта

Создайте файл `aspects/your_aspect.json`:

```json
{
  "name": "Your Aspect",
  "description": "Описание функциональности",
  "tools": ["your_function"],
  "monitors": [
    {
      "name": "your_monitor",
      "path": "components.monitoring.your_monitor",
      "class": "YourMonitor",
      "dependencies": ["your_tool"]
    }
  ],
  "programs": []
}
```

## Мониторинг

Система включает встроенные мониторы для:

- :white_check_mark: Статуса задач
- :speech_balloon: Telegram чатов
- :computer: SSH соединений
- :green_book: Google Sheets данных
- :busts_in_silhouette: Активности сотрудников
- :bar_chart: DataFrame операций

## Безопасность

> **:warning: Важно:** Убедитесь, что все чувствительные данные (токены, пароли, ключи) хранятся в переменных окружения, а не в коде.

### Чек-лист безопасности

- [ ] Все токены и пароли в переменных окружения
- [ ] `.env` файл добавлен в `.gitignore`
- [ ] Созданы резервные копии ключей
- [ ] Настроены права доступа к базам данных
- [ ] Проверены настройки S3 bucket

## Вклад в развитие

1. Fork проекта
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Внесите изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Создайте Pull Request

## Известные проблемы

- Требует стабильное подключение к Redis
- Некоторые операции с Google Sheets могут быть медленными
- SSH соединения могут прерываться при длительной неактивности

## Лицензия

Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE) для деталей.

## Поддержка

Для вопросов и поддержки:

- Создавайте [Issues](../../issues) в репозитории
- Ознакомьтесь с [Wiki](../../wiki) для дополнительной документации

---

<div align="center">

**[⬆ Наверх](#ai-agent-project)**

</div>