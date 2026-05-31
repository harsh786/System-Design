# A2A Agent Card Server
#
# Implements:
# - /.well-known/agent.json endpoint (agent discovery)
# - Task submission and lifecycle
# - Skill-based capabilities

import uuid
import asyncio
import logging
from datetime import datetime
from enum import Enum

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="A2A Agent Card Server")


# =============================================================================
# MODELS - A2A Protocol Data Structures
# =============================================================================

class TaskStatus(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class Part(BaseModel):
    type: str = "text"
    text: str | None = None


class Message(BaseModel):
    role: str  # "user" or "agent"
    parts: list[Part]


class Artifact(BaseModel):
    name: str
    parts: list[Part]


class TaskRequest(BaseModel):
    message: Message


class Task(BaseModel):
    id: str
    status: TaskStatus
    created_at: str
    updated_at: str
    messages: list[Message] = []
    artifacts: list[Artifact] = []


# =============================================================================
# AGENT CARD - Defines this agent's capabilities
# =============================================================================

AGENT_CARD = {
    "name": "Research Summary Agent",
    "description": "Summarizes topics by synthesizing information into clear, concise reports",
    "url": "http://localhost:8000",
    "version": "1.0.0",
    "provider": {
        "organization": "Learning Demo",
        "url": "http://localhost:8000"
    },
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
        "stateTransitionHistory": True
    },
    "authentication": {
        "schemes": []  # No auth for demo
    },
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "skills": [
        {
            "id": "summarize-topic",
            "name": "Topic Summarization",
            "description": "Provide a concise summary of any given topic",
            "tags": ["summarization", "research", "writing"],
            "examples": [
                "Summarize the key points of quantum computing",
                "Give me an overview of climate change solutions"
            ],
            "inputModes": ["text"],
            "outputModes": ["text"]
        },
        {
            "id": "compare-topics",
            "name": "Topic Comparison",
            "description": "Compare and contrast two or more topics",
            "tags": ["comparison", "analysis"],
            "examples": [
                "Compare REST vs GraphQL",
                "What are the differences between Python and Go?"
            ],
            "inputModes": ["text"],
            "outputModes": ["text"]
        }
    ]
}


# =============================================================================
# IN-MEMORY TASK STORE
# =============================================================================

tasks: dict[str, Task] = {}


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/.well-known/agent.json")
async def get_agent_card():
    """Agent Card discovery endpoint.
    
    Other agents and clients fetch this to learn about our capabilities.
    This is the A2A equivalent of a 'business card'.
    """
    logger.info("Agent Card requested")
    return AGENT_CARD


@app.post("/tasks/send")
async def submit_task(request: TaskRequest) -> Task:
    """Submit a new task to this agent.
    
    Creates a task, starts processing it asynchronously,
    and returns the task with initial 'submitted' status.
    """
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    task = Task(
        id=task_id,
        status=TaskStatus.SUBMITTED,
        created_at=now,
        updated_at=now,
        messages=[request.message]
    )
    tasks[task_id] = task
    
    logger.info(f"Task submitted: {task_id}")
    
    # Start async processing (simulates agent doing work)
    asyncio.create_task(_process_task(task_id))
    
    return task


@app.get("/tasks/{task_id}")
async def get_task(task_id: str) -> Task:
    """Get the current status of a task.
    
    Clients poll this endpoint to check if work is complete.
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return tasks[task_id]


# =============================================================================
# TASK PROCESSING (Simulated)
# =============================================================================

async def _process_task(task_id: str):
    """Simulate agent processing a task through its lifecycle.
    
    In a real agent, this would invoke an LLM or perform actual work.
    """
    task = tasks[task_id]
    
    # Transition: submitted → working
    await asyncio.sleep(1)
    task.status = TaskStatus.WORKING
    task.updated_at = datetime.utcnow().isoformat()
    logger.info(f"Task {task_id}: working")
    
    # Simulate work
    await asyncio.sleep(2)
    
    # Get the user's request text
    user_text = ""
    for msg in task.messages:
        if msg.role == "user":
            for part in msg.parts:
                if part.text:
                    user_text = part.text
    
    # Generate a simulated response
    response_text = (
        f"Summary of '{user_text}':\n\n"
        f"This is a simulated response from the Research Summary Agent. "
        f"In a real implementation, this would contain an actual AI-generated "
        f"summary of the requested topic. The agent would use its LLM backbone "
        f"to research and synthesize information.\n\n"
        f"Key points would be listed here with supporting details."
    )
    
    # Transition: working → completed
    task.status = TaskStatus.COMPLETED
    task.updated_at = datetime.utcnow().isoformat()
    task.artifacts = [
        Artifact(
            name="summary",
            parts=[Part(type="text", text=response_text)]
        )
    ]
    
    # Add agent response message
    task.messages.append(
        Message(role="agent", parts=[Part(type="text", text=response_text)])
    )
    
    logger.info(f"Task {task_id}: completed")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    logger.info("Starting A2A Agent Card Server on http://localhost:8000")
    logger.info("Agent Card: http://localhost:8000/.well-known/agent.json")
    uvicorn.run(app, host="0.0.0.0", port=8000)
