import os
import tomli
import logging
from pathlib import Path

def load_model_config():
    """Загружает конфигурацию модели из папки model_configs"""
    base_dir = Path(__file__).parent.parent.parent
    config_dir = base_dir / "model_configs"
    
    # Определяем текущую конфигурацию
    current_index = config_dir / "current.index"
    if not current_index.exists():
        raise FileNotFoundError(f"Missing current.index in {config_dir}")
    
    config_name = current_index.read_text().strip()
    config_file = config_dir / f"{config_name}.toml"
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file {config_file} not found")

    # Загружаем и применяем конфигурацию
    with open(config_file, "rb") as f:
        config = tomli.load(f)
    
    env_mapping = {
        "api_key": "OPENAI_API_KEY",
        "api_base": "API_BASE",
        "embeddings_api_base": "EMBEDDINGS_API_BASE",
        "model": "MODEL",
        "llm_provider": "LLM_PROVIDER",
        "use_ollama": "USE_OLLAMA",
        "temperature" : "TEMPERATURE"
    }
    for key, env_var in env_mapping.items():
        if value := config.get(key):
            os.environ[env_var] = str(value)
            logging.info(f"Setting {env_var} to {value}")
