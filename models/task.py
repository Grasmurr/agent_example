from datetime import datetime
from pydantic import BaseModel

# Define your Pydantic model
class TaskInput(BaseModel):
    id: int

class TaskOutput(BaseModel):
    id: int
    result: str

class Task(BaseModel):
    id: int
    task_type_id: int
    ai_agent_id: int
    process_id: int
    prompt: str
    data: str
    result: str
    status: str
    created_at: datetime
    finished_at: datetime
    cancelled_at: datetime