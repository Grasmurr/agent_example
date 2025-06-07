import os
import logging
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic
from langchain_mistralai import ChatMistralAI
from langchain_core.rate_limiters import InMemoryRateLimiter

class LanguageModel:
    def __init__(self, model_name, api_key, api_base):
        provider = os.getenv("LLM_PROVIDER")
        temperature = os.getenv("TEMPERATURE")
        
        if provider == 'mistral':
            rps = 0.5
        else:
            rps = 1

        rate_limiting_handler = InMemoryRateLimiter(requests_per_second=rps)
        logging.info(f'Создан обработчик rate limiting с ограничением {rps} rps')
        
        match provider:
            case "openai":
                self.instance = ChatOpenAI(
                    model=model_name,
                    api_key=api_key,
                    base_url=api_base,
                    rate_limiter=rate_limiting_handler,
                    temperature=temperature
                )
            case "anthropic":
                self.instance = ChatAnthropic(
                    model=model_name,
                    api_key=api_key,
                    base_url=api_base,
                    rate_limiter=rate_limiting_handler,
                    temperature=temperature,
                    timeout=None
                )
                # )
            case "mistral":
                self.instance = ChatMistralAI(
                    model=model_name,
                    mistral_api_key=api_key,
                    rate_limiter=rate_limiting_handler,
                    temperature=temperature
                    # endpoint=api_base
                )
            case "ollama":
                self.instance = ChatOllama(
                    model=model_name,
                    base_url=api_base,
                    temperature=temperature
                )
            case _:
                self.instance = ChatOpenAI(
                    model=model_name,
                    api_key=api_key,
                    base_url=api_base,
                    rate_limiter=rate_limiting_handler,
                    temperature=temperature
                )

        logging.info(f'Инициализирована модель {model_name} от {provider}')
