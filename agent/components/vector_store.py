import logging
import chromadb
import os
from typing import List, Dict, Tuple, Optional
from chromadb import Settings

from langchain_chroma import Chroma
from langchain_core.documents import Document

class VectorStore:
    def __init__(self, embedding):
        os.environ["ANONYMIZED_TELEMETRY"] = 'False'
        os.environ['CHROMA_TELEMETRY'] = '0'
        
        # Создаем путь к директории векторов относительно текущего файла
        current_dir = os.path.dirname(os.path.abspath(__file__))
        vectors_dir = os.path.join(current_dir, '..', '..', 'data', 'vectors')
        
        # Создаем директорию если она не существует
        os.makedirs(vectors_dir, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=vectors_dir)
        try:
            self.store = Chroma(client=self.client, embedding_function=embedding.function)
        except AttributeError:
            self.store = Chroma(client=self.client, embedding_function=embedding)
        
        logging.info('Векторное хранилище инициализировано')
    
    def add_document(self, text: str, metadata: Optional[Dict] = None):
        document = Document(page_content=text, metadata=metadata or {})
        self.store.add_documents([document])
        logging.info('Документ добавлен в векторное хранилище')

    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict]] = None) -> None:
        if metadatas is None:
            metadatas = [{} for _ in texts]
        documents = [Document(page_content=text, metadata=metadata) 
                for text, metadata in zip(texts, metadatas)]
        self.store.add_documents(documents)
        logging.info(f'Добавлено {len(texts)} документов в векторное хранилище')

    def retrieve_documents(self, query: str, top_k: int = 10) -> List[str]:
        results = self.store.similarity_search(query, k=top_k)
        relevant_documents = [doc.page_content for doc in results]
        print(relevant_documents)
        return relevant_documents
        
    def similarity_search_with_score(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        return self.store.similarity_search_with_score(query, k=k)
        
    def clear(self) -> None:
        """Clear all documents from the store."""
        self.store.delete_collection()
        self.store = Chroma(
            client=self.client,
            embedding_function=self.store._embedding_function
        )
        logging.info('Векторное хранилище очищено')
    
    def delete_document_by_content(self, content: str) -> None:
        try:
            self.collection.delete(where_document={"$eq": {"text": content}})
            logging.info(f'Знание "{content}" удалено из долгосрочной памяти!')
        except Exception as e:
            logging.error(f'Ошибка при удалении знания "{content}": {e}')
            
    def delete(self, filter: Dict) -> None:
        """Delete documents matching the filter criteria."""
        try:
            self.store.delete(filter)
            logging.info(f'Документы удалены по фильтру: {filter}')
        except Exception as e:
            logging.error(f'Ошибка при удалении документов: {e}')
        

