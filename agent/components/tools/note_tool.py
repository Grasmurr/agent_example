from typing import Union

class NoteTool:
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager

    def take_note(self, knowledge: str) -> str:
        """Record valuable information."""
        relevant_memories = self.memory_manager.search_memories(knowledge)
        for memory in relevant_memories:
            if memory == knowledge:
                return f'You already have that note that says "{knowledge}"!'

        result = self.memory_manager.add_memory(
            content=knowledge,
            metadata={'source': 'ltm_tool'}
        )
        return result

    def discard_note(self, id: Union[str, int]) -> str:
        """Discard a note by content or ID."""
        if isinstance(id, int):
            # Forget by ID
            if self.memory_manager.delete_memory(id):
                return f'Note with ID {id} was successfully destoyed!'
            return f'Note with ID {id} not found!'
        elif isinstance(id, str):
            # Forget by content
            memory = self.memory_manager.get_memory_by_content(id)
            if memory:
                self.memory_manager.delete_memory(memory['id'])
                return f'Note \"{id}\" was successfully destroyed!'
            return f'Note \"{id}\" not found!'
        else:
            return "Invalid ID type. Provide either a note ID (int) or note content (str)."

    def forget_by_id(self, memory_id: int) -> str:
        """Forget specific memory by ID."""
        if self.memory_manager.delete_memory(memory_id):
            return f'Memory with ID {memory_id} was successfully forgotten!'
        return f'Memory with ID {memory_id} not found!'




