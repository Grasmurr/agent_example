import logging
import os
from langchain_openai import OpenAIEmbeddings
from langchain_ollama import OllamaEmbeddings
# from langchain_anthropic 
from langchain_mistralai import MistralAIEmbeddings

class Embedding:
    def __init__(self, api_key, api_base):
        provider = os.getenv("LLM_PROVIDER", "openai")
        
        match provider:
            case "ollama":
                self.function = OllamaEmbeddings(base_url=api_base, model=os.getenv("MODEL", "text-embedding-ada-002"))
            case "openai":
                self.function = OpenAIEmbeddings(openai_api_key=api_key, openai_api_base=api_base)
            case "anthropic":
                #self.function = OpenAIEmbeddings(openai_api_key=api_key, openai_api_base=api_base)
                self.function = OllamaEmbeddings(base_url='https://ollama-ss.berht.dev', model='nomic-embed-text')
            case "mistral":
                self.function = MistralAIEmbeddings(api_key=api_key)
            case "...":
                self.function = OllamaEmbeddings(base_url='https://ollama-ss.berht.dev', model='nomic-embed-text')
            case _:
                self.function = OpenAIEmbeddings(openai_api_key=api_key, openai_api_base=api_base)
        
        logging.info('Эмбеддинг работает')
