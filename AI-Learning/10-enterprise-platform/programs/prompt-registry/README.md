# Prompt Registry - Version Management for Prompts

A prompt registry API that treats prompts as versioned, deployable artifacts.
Like a package registry (npm/PyPI) but for prompt templates.

## What This Demonstrates

- **CRUD API** for prompt templates
- **Version management** (v1, v2, v3 of the same prompt)
- **Active version tracking** (which version is in production)
- **Instant rollback** to any previous version
- **Template variable resolution** (fill in `{{variable}}` placeholders)
- **Metadata** (author, tags, description, timestamps)

## Running

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

## API Endpoints

```bash
# Create a new prompt
POST /prompts

# List all prompts
GET /prompts

# Get a specific prompt (active version)
GET /prompts/{prompt_id}

# Get a specific version
GET /prompts/{prompt_id}/versions/{version}

# Create new version
POST /prompts/{prompt_id}/versions

# Set active version
PUT /prompts/{prompt_id}/active/{version}

# Rollback to previous version
POST /prompts/{prompt_id}/rollback

# Resolve template variables
POST /prompts/{prompt_id}/resolve
```

## Example

```bash
# Create a customer support prompt
curl -X POST http://localhost:8001/prompts -H "Content-Type: application/json" -d '{
  "id": "customer-support",
  "name": "Customer Support Agent",
  "description": "System prompt for customer support chatbot",
  "author": "jane@company.com",
  "tags": ["support", "production"],
  "template": "You are a helpful support agent for {{company_name}}. Be polite and concise."
}'

# Resolve with variables
curl -X POST http://localhost:8001/prompts/customer-support/resolve \
  -H "Content-Type: application/json" \
  -d '{"variables": {"company_name": "Acme Corp"}}'
```
