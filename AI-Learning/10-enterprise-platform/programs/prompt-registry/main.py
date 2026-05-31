"""
Prompt Registry - Version Management for Prompts

Treats prompts as versioned, deployable artifacts with rollback capability.
"""

import re
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Prompt Registry", description="Version management for prompt templates")


# --- Models ---


class PromptCreate(BaseModel):
    id: str
    name: str
    description: str = ""
    author: str = "unknown"
    tags: list[str] = []
    template: str


class PromptVersionCreate(BaseModel):
    template: str
    description: str = ""
    author: str = "unknown"


class ResolveRequest(BaseModel):
    variables: dict[str, str]
    version: Optional[int] = None  # None = active version


class PromptVersion(BaseModel):
    version: int
    template: str
    description: str
    author: str
    created_at: str


class PromptRecord(BaseModel):
    id: str
    name: str
    description: str
    author: str
    tags: list[str]
    active_version: int
    versions: list[PromptVersion]
    created_at: str
    updated_at: str


# --- In-Memory Storage ---

prompts_db: dict[str, PromptRecord] = {}


# --- Seed Data ---

def seed_data():
    """Add example prompts for demonstration."""
    now = datetime.utcnow().isoformat()

    prompts_db["customer-support"] = PromptRecord(
        id="customer-support",
        name="Customer Support Agent",
        description="System prompt for customer support chatbot",
        author="jane@company.com",
        tags=["support", "production"],
        active_version=2,
        versions=[
            PromptVersion(
                version=1,
                template="You are a customer support agent. Help the user.",
                description="Initial version",
                author="jane@company.com",
                created_at=now,
            ),
            PromptVersion(
                version=2,
                template="You are a helpful and empathetic customer support agent for {{company_name}}. "
                         "Always greet the customer warmly. Be concise but thorough. "
                         "If you cannot resolve the issue, escalate to a human agent.",
                description="Added empathy guidelines and escalation instructions",
                author="jane@company.com",
                created_at=now,
            ),
        ],
        created_at=now,
        updated_at=now,
    )

    prompts_db["summarizer"] = PromptRecord(
        id="summarizer",
        name="Document Summarizer",
        description="Summarizes documents to specified length",
        author="bob@company.com",
        tags=["summarization", "production"],
        active_version=1,
        versions=[
            PromptVersion(
                version=1,
                template="Summarize the following document in {{max_sentences}} sentences. "
                         "Focus on key facts and conclusions.\n\nDocument:\n{{document}}",
                description="Initial version",
                author="bob@company.com",
                created_at=now,
            ),
        ],
        created_at=now,
        updated_at=now,
    )


seed_data()


# --- API Endpoints ---


@app.get("/prompts")
async def list_prompts():
    """List all registered prompts."""
    return {
        "prompts": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "tags": p.tags,
                "active_version": p.active_version,
                "total_versions": len(p.versions),
            }
            for p in prompts_db.values()
        ]
    }


@app.post("/prompts", status_code=201)
async def create_prompt(request: PromptCreate):
    """Create a new prompt with initial version."""
    if request.id in prompts_db:
        raise HTTPException(status_code=409, detail=f"Prompt '{request.id}' already exists")

    now = datetime.utcnow().isoformat()
    prompts_db[request.id] = PromptRecord(
        id=request.id,
        name=request.name,
        description=request.description,
        author=request.author,
        tags=request.tags,
        active_version=1,
        versions=[
            PromptVersion(
                version=1,
                template=request.template,
                description="Initial version",
                author=request.author,
                created_at=now,
            )
        ],
        created_at=now,
        updated_at=now,
    )
    return {"message": f"Prompt '{request.id}' created", "version": 1}


@app.get("/prompts/{prompt_id}")
async def get_prompt(prompt_id: str):
    """Get a prompt (returns active version template + metadata)."""
    if prompt_id not in prompts_db:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")

    prompt = prompts_db[prompt_id]
    active = next(v for v in prompt.versions if v.version == prompt.active_version)

    return {
        "id": prompt.id,
        "name": prompt.name,
        "description": prompt.description,
        "author": prompt.author,
        "tags": prompt.tags,
        "active_version": prompt.active_version,
        "total_versions": len(prompt.versions),
        "template": active.template,
        "variables": _extract_variables(active.template),
    }


@app.get("/prompts/{prompt_id}/versions/{version}")
async def get_prompt_version(prompt_id: str, version: int):
    """Get a specific version of a prompt."""
    if prompt_id not in prompts_db:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")

    prompt = prompts_db[prompt_id]
    ver = next((v for v in prompt.versions if v.version == version), None)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    return {
        "id": prompt_id,
        "version": ver.version,
        "template": ver.template,
        "description": ver.description,
        "author": ver.author,
        "created_at": ver.created_at,
        "is_active": ver.version == prompt.active_version,
        "variables": _extract_variables(ver.template),
    }


@app.post("/prompts/{prompt_id}/versions", status_code=201)
async def create_version(prompt_id: str, request: PromptVersionCreate):
    """Create a new version of an existing prompt."""
    if prompt_id not in prompts_db:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")

    prompt = prompts_db[prompt_id]
    new_version = len(prompt.versions) + 1
    now = datetime.utcnow().isoformat()

    prompt.versions.append(PromptVersion(
        version=new_version,
        template=request.template,
        description=request.description,
        author=request.author,
        created_at=now,
    ))
    prompt.updated_at = now

    return {
        "message": f"Version {new_version} created",
        "version": new_version,
        "note": "Not yet active. Use PUT /prompts/{id}/active/{version} to activate.",
    }


@app.put("/prompts/{prompt_id}/active/{version}")
async def set_active_version(prompt_id: str, version: int):
    """Set which version is active (in production)."""
    if prompt_id not in prompts_db:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")

    prompt = prompts_db[prompt_id]
    if not any(v.version == version for v in prompt.versions):
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    old_version = prompt.active_version
    prompt.active_version = version
    prompt.updated_at = datetime.utcnow().isoformat()

    return {
        "message": f"Active version changed: v{old_version} → v{version}",
        "prompt_id": prompt_id,
        "active_version": version,
    }


@app.post("/prompts/{prompt_id}/rollback")
async def rollback(prompt_id: str):
    """Rollback to the previous version."""
    if prompt_id not in prompts_db:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")

    prompt = prompts_db[prompt_id]
    if prompt.active_version <= 1:
        raise HTTPException(status_code=400, detail="Cannot rollback: already at version 1")

    old_version = prompt.active_version
    prompt.active_version -= 1
    prompt.updated_at = datetime.utcnow().isoformat()

    return {
        "message": f"Rolled back: v{old_version} → v{prompt.active_version}",
        "prompt_id": prompt_id,
        "active_version": prompt.active_version,
    }


@app.post("/prompts/{prompt_id}/resolve")
async def resolve_prompt(prompt_id: str, request: ResolveRequest):
    """Resolve template variables and return the final prompt."""
    if prompt_id not in prompts_db:
        raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found")

    prompt = prompts_db[prompt_id]
    version = request.version or prompt.active_version
    ver = next((v for v in prompt.versions if v.version == version), None)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    # Resolve variables
    resolved = ver.template
    required_vars = _extract_variables(ver.template)
    missing = [v for v in required_vars if v not in request.variables]

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing variables: {missing}. Required: {required_vars}"
        )

    for key, value in request.variables.items():
        resolved = resolved.replace(f"{{{{{key}}}}}", value)

    return {
        "prompt_id": prompt_id,
        "version": version,
        "resolved_template": resolved,
        "variables_used": request.variables,
    }


# --- Helpers ---


def _extract_variables(template: str) -> list[str]:
    """Extract {{variable}} placeholders from template."""
    return re.findall(r'\{\{(\w+)\}\}', template)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
