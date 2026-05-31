# A2A Task Flow - Two agents communicating via A2A protocol
#
# Agent 1 (Coordinator, port 8001): Receives user requests, delegates to specialist
# Agent 2 (Specialist, port 8002): Performs the actual work
#
# Demonstrates: task submission, status polling, result retrieval, error handling

import uuid
import asyncio
import logging
from datetime import datetime
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# SHARED MODELS
# =============================================================================

class TaskStatus(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"


class Part(BaseModel):
    type: str = "text"
    text: str | None = None


class Message(BaseModel):
    role: str
    parts: list[Part]


class Artifact(BaseModel):
    name: str
    parts: list[Part]


class Task(BaseModel):
    id: str
    status: TaskStatus
    created_at: str
    updated_at: str
    messages: list[Message] = []
    artifacts: list[Artifact] = []


class TaskRequest(BaseModel):
    message: Message


# =============================================================================
# SPECIALIST AGENT (Port 8002) - Does the actual work
# =============================================================================

specialist_app = FastAPI(title="Specialist Agent")
specialist_tasks: dict[str, Task] = {}

SPECIALIST_CARD = {
    "name": "Analysis Specialist Agent",
    "description": "Performs deep analysis on technical topics",
    "url": "http://localhost:8002",
    "version": "1.0.0",
    "capabilities": {"streaming": False, "pushNotifications": False},
    "skills": [
        {
            "id": "technical-analysis",
            "name": "Technical Analysis",
            "description": "Analyze technical topics with pros, cons, and recommendations",
            "tags": ["analysis", "technical", "comparison"],
        }
    ],
}


@specialist_app.get("/.well-known/agent.json")
async def specialist_card():
    return SPECIALIST_CARD


@specialist_app.post("/tasks/send")
async def specialist_submit(request: TaskRequest) -> Task:
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    task = Task(id=task_id, status=TaskStatus.SUBMITTED, created_at=now, updated_at=now, messages=[request.message])
    specialist_tasks[task_id] = task
    logger.info(f"[Specialist] Task received: {task_id}")
    asyncio.create_task(_specialist_process(task_id))
    return task


@specialist_app.get("/tasks/{task_id}")
async def specialist_get_task(task_id: str) -> Task:
    if task_id not in specialist_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return specialist_tasks[task_id]


async def _specialist_process(task_id: str):
    """Simulate specialist doing deep analysis work."""
    task = specialist_tasks[task_id]
    
    task.status = TaskStatus.WORKING
    task.updated_at = datetime.utcnow().isoformat()
    logger.info(f"[Specialist] Processing task {task_id}...")
    
    # Simulate work (3 seconds)
    await asyncio.sleep(3)
    
    # Extract user request
    user_text = ""
    for msg in task.messages:
        if msg.role == "user":
            for part in msg.parts:
                if part.text:
                    user_text = part.text
    
    # Generate analysis result
    analysis = (
        f"## Analysis: {user_text}\n\n"
        f"### Pros\n"
        f"1. Scalability - independent deployment of services\n"
        f"2. Technology diversity - use the best tool for each service\n"
        f"3. Team autonomy - teams own their services end-to-end\n\n"
        f"### Cons\n"
        f"1. Complexity - distributed systems are hard\n"
        f"2. Data consistency - eventual consistency challenges\n"
        f"3. Operational overhead - more services to monitor\n\n"
        f"### Recommendation\n"
        f"Consider your team size and domain complexity before adopting.\n"
        f"(This is simulated output for demonstration purposes)"
    )
    
    task.status = TaskStatus.COMPLETED
    task.updated_at = datetime.utcnow().isoformat()
    task.artifacts = [Artifact(name="analysis", parts=[Part(type="text", text=analysis)])]
    task.messages.append(Message(role="agent", parts=[Part(type="text", text=analysis)]))
    logger.info(f"[Specialist] Task {task_id} completed")


# =============================================================================
# COORDINATOR AGENT (Port 8001) - Delegates to specialist
# =============================================================================

coordinator_app = FastAPI(title="Coordinator Agent")
coordinator_tasks: dict[str, Task] = {}

COORDINATOR_CARD = {
    "name": "Coordinator Agent",
    "description": "Routes user requests to the appropriate specialist agent",
    "url": "http://localhost:8001",
    "version": "1.0.0",
    "capabilities": {"streaming": False, "pushNotifications": False},
    "skills": [
        {
            "id": "coordinate",
            "name": "Task Coordination",
            "description": "Accept any request and delegate to the right specialist",
            "tags": ["coordination", "routing", "delegation"],
        }
    ],
}

SPECIALIST_URL = "http://localhost:8002"


@coordinator_app.get("/.well-known/agent.json")
async def coordinator_card():
    return COORDINATOR_CARD


@coordinator_app.post("/tasks/send")
async def coordinator_submit(request: TaskRequest) -> Task:
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    task = Task(id=task_id, status=TaskStatus.SUBMITTED, created_at=now, updated_at=now, messages=[request.message])
    coordinator_tasks[task_id] = task
    logger.info(f"[Coordinator] Task received: {task_id}")
    asyncio.create_task(_coordinator_process(task_id))
    return task


@coordinator_app.get("/tasks/{task_id}")
async def coordinator_get_task(task_id: str) -> Task:
    if task_id not in coordinator_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return coordinator_tasks[task_id]


async def _coordinator_process(task_id: str):
    """Coordinator discovers specialist, delegates work, polls for result."""
    task = coordinator_tasks[task_id]
    task.status = TaskStatus.WORKING
    task.updated_at = datetime.utcnow().isoformat()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Discover the specialist agent
            logger.info(f"[Coordinator] Discovering specialist at {SPECIALIST_URL}")
            card_resp = await client.get(f"{SPECIALIST_URL}/.well-known/agent.json")
            card_resp.raise_for_status()
            agent_card = card_resp.json()
            logger.info(f"[Coordinator] Found agent: {agent_card['name']}")
            
            # Step 2: Delegate the task
            logger.info(f"[Coordinator] Delegating task {task_id} to specialist")
            delegate_resp = await client.post(
                f"{SPECIALIST_URL}/tasks/send",
                json={"message": task.messages[0].model_dump()}
            )
            delegate_resp.raise_for_status()
            remote_task = delegate_resp.json()
            remote_task_id = remote_task["id"]
            logger.info(f"[Coordinator] Specialist accepted task as {remote_task_id}")
            
            # Step 3: Poll for completion (with timeout)
            max_polls = 15
            for i in range(max_polls):
                await asyncio.sleep(1)
                status_resp = await client.get(f"{SPECIALIST_URL}/tasks/{remote_task_id}")
                status_resp.raise_for_status()
                remote_status = status_resp.json()
                
                logger.info(f"[Coordinator] Poll {i+1}: specialist status = {remote_status['status']}")
                
                if remote_status["status"] == "completed":
                    # Step 4: Return specialist's result
                    task.status = TaskStatus.COMPLETED
                    task.updated_at = datetime.utcnow().isoformat()
                    task.artifacts = [Artifact(**a) for a in remote_status.get("artifacts", [])]
                    task.messages.append(
                        Message(role="agent", parts=[Part(type="text", text="Task delegated and completed by specialist.")])
                    )
                    logger.info(f"[Coordinator] Task {task_id} completed via specialist")
                    return
                
                if remote_status["status"] == "failed":
                    raise Exception("Specialist agent failed the task")
            
            # Timeout
            raise Exception("Specialist agent timed out")
    
    except Exception as e:
        logger.error(f"[Coordinator] Task {task_id} failed: {e}")
        task.status = TaskStatus.FAILED
        task.updated_at = datetime.utcnow().isoformat()
        task.messages.append(
            Message(role="agent", parts=[Part(type="text", text=f"Task failed: {str(e)}")])
        )


# =============================================================================
# MAIN - Run both agents
# =============================================================================

async def main():
    """Run both agents concurrently on different ports."""
    logger.info("=" * 60)
    logger.info("A2A Task Flow Demo")
    logger.info("Coordinator Agent: http://localhost:8001")
    logger.info("Specialist Agent:  http://localhost:8002")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Test with:")
    logger.info('  curl -X POST http://localhost:8001/tasks/send \\')
    logger.info('    -H "Content-Type: application/json" \\')
    logger.info('    -d \'{"message": {"role": "user", "parts": [{"type": "text", "text": "Analyze microservices"}]}}\'')
    logger.info("")
    
    config_specialist = uvicorn.Config(specialist_app, host="0.0.0.0", port=8002, log_level="warning")
    config_coordinator = uvicorn.Config(coordinator_app, host="0.0.0.0", port=8001, log_level="warning")
    
    server_specialist = uvicorn.Server(config_specialist)
    server_coordinator = uvicorn.Server(config_coordinator)
    
    await asyncio.gather(
        server_specialist.serve(),
        server_coordinator.serve()
    )


if __name__ == "__main__":
    asyncio.run(main())
