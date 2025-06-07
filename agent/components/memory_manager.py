import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import JSON, Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from .vector_store import VectorStore

# Configure logging
logger = logging.getLogger(__name__)

# SQLAlchemy setup
Base = declarative_base()

class Memory(Base):
    """SQLAlchemy model for storing memory entries."""
    __tablename__ = 'memories'

    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    memory_metadata = Column(JSON, nullable=True)

class MemoryManager:
    """Manages both SQLite and vector storage for memory entries."""

    def __init__(self, sqlite_path: str, vector_store: VectorStore):
        """Initialize MemoryManager with SQLite and vector storage.

        Args:
            sqlite_path: Path to SQLite database
            vector_store: Instance of VectorStore
        """
        self.engine = create_engine(f'sqlite:///{sqlite_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.vector_store = vector_store

        logger.info("Initialized MemoryManager with SQLite and vector storage")

    def add_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Union[int, str]:
        """Add a new memory entry to both storages.

        Args:
            content: Text content to store
            metadata: Optional metadata dictionary

        Returns:
            ID of the created memory entry, or message if duplicate
        """
        session = self.Session()
        try:
            # Check if memory already exists
            existing_memory = session.query(Memory).filter(Memory.content == content).first()
            if existing_memory:
                logger.info(f"Memory already exists: {content}")
                return "This memory is already added"

            # Add new memory to SQLite
            memory = Memory(content=content, memory_metadata=metadata)
            session.add(memory)
            session.commit()
            memory_id = memory.id

            # Add to vector store
            self.vector_store.add_texts(
                texts=[content],
                metadatas=[{'id': memory_id, **(metadata or {})}]
            )

            logger.info(f"Added memory entry with ID: {memory_id}")
            return f"Added memory entry with ID: {memory_id}"

        except Exception as e:
            logger.error(f"Failed to add memory: {str(e)}")
            raise
        finally:
            session.close()

    def get_memory(self, memory_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a memory entry by ID.

        Args:
            memory_id: ID of the memory to retrieve

        Returns:
            Dictionary containing memory data or None if not found
        """
        session = self.Session()
        try:
            memory = session.query(Memory).filter(Memory.id == memory_id).first()
            if memory:
                return {
                    'id': memory.id,
                    'content': memory.content,
                    'created_at': memory.created_at,
                    'metadata': memory.memory_metadata
                }
            return None

        except Exception as e:
            logger.error(f"Failed to retrieve memory {memory_id}: {str(e)}")
            raise
        finally:
            session.close()

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory entry from both storages.

        Args:
            memory_id: ID of the memory to delete

        Returns:
            True if successful, False if memory not found
        """
        session = self.Session()
        try:
            memory = session.query(Memory).filter(Memory.id == memory_id).first()
            if not memory:
                return False

            session.delete(memory)
            session.commit()

            # Delete from vector store
            self.vector_store.delete(filter={'id': memory_id})

            logger.info(f"Deleted memory entry with ID: {memory_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {str(e)}")
            raise
        finally:
            session.close()

    def rebuild_vector_store(self) -> None:
        """Rebuild the vector store using all entries from SQLite.

        This is useful when changing the embedding model or after data corruption.
        """
        session = self.Session()
        try:
            # Clear existing vector store
            self.vector_store.clear()

            memories = session.query(Memory).all()
            texts = []
            metadatas = []

            for memory in memories:
                texts.append(memory.content)
                metadatas.append({'id': memory.id, **(memory.memory_metadata or {})})

            if texts:
                self.vector_store.add_texts(texts=texts, metadatas=metadatas)

            logger.info(f"Successfully rebuilt vector store with {len(texts)} entries")

        except Exception as e:
            logger.error(f"Failed to rebuild vector store: {str(e)}")
            raise
        finally:
            session.close()

    def search_similar(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar memories using vector similarity.

        Args:
            query: Text to search for
            k: Number of results to return

        Returns:
            List of similar memories with their metadata
        """
        try:
            results = self.vector_store.similarity_search_with_score(query, k=k)

            memories = []
            for doc, score in results:
                memory_id = doc.metadata.get('id')
                if memory_id:
                    memory = self.get_memory(memory_id)
                    if memory:
                        memories.append(f'{memory['content']} (ID {memory_id})')

            return memories

        except Exception as e:
            logger.error(f"Failed to search similar memories: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Failed to search similar memories: {str(e)}")
            raise

    def search_memories(self, knowledge: str, k: int = 5) -> List[Dict[str, Any]]:
        try:
            return self.search_similar(query=knowledge, k=k)
        except Exception as e:
            logger.error(f"Failed to search memories for knowledge: {str(e)}")
            raise

    def get_memory_by_content(self, content: str) -> Optional[Dict[str, Any]]:
        """Retrieve a memory entry by its content.

        Args:
            content: The text content to search for.

        Returns:
            Dictionary containing memory data or None if not found.
        """
        session = self.Session()
        try:
            memory = session.query(Memory).filter(Memory.content == content).first()
            if memory:
                return {
                    'id': memory.id,
                    'content': memory.content,
                    'created_at': memory.created_at,
                    'metadata': memory.memory_metadata
                }
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve memory by content: {str(e)}")
            raise
        finally:
            session.close()

