import logging

from dotenv import load_dotenv

import chromadb
import os
from app.agent.components.embedding import Embedding

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

load_dotenv()
logging.basicConfig(level=logging.INFO)
api_key = os.getenv('OPENAI_API_KEY')
api_base = os.getenv("LOCAL_API_BASE")
embeddings_api_base = os.getenv('EMBEDDINGS_API_BASE')
model_name = os.getenv("MODEL")
use_ollama = os.getenv("USE_OLLAMA")

logging.info('STEP 1')
if int(use_ollama):
    embedding = OllamaEmbeddings(
        model=model_name,
        base_url=embeddings_api_base
    )
else:
    embedding = Embedding(api_key, api_base)
logging.info('STEP 2')
os.environ["ANONYMIZED_TELEMETRY"] = 'False'
os.environ['CHROMA_TELEMETRY'] = '0'

client = chromadb.PersistentClient(path="test-data/vectors")
logging.info('STEP 3')
try:
    store = Chroma(client=client, embedding_function=embedding.function)
except AttributeError:
    store = Chroma(client=client, embedding_function=embedding)
logging.info('STEP 4')
logging.info(f'{store.get()}')
document = Document(page_content='TEST!')
logging.info('STEP 5')
store.add_documents([document])
logging.info('STEP 6')
results = store.similarity_search("тестирование", k=1)
logging.info('STEP 7')
relevant_documents = [doc.page_content for doc in results]
print(relevant_documents)