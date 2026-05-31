# Agent Identity Manager

Simulates the full lifecycle of AI agent identity management: registration, authentication, authorization, credential rotation, and revocation.

## Concepts Demonstrated
- Agent identity registration with certificates
- Authentication flow (prove identity)
- Scope checking (agent can't exceed its permissions)
- Credential rotation
- Emergency revocation

## Run
```bash
pip install -r requirements.txt
python main.py
```

## Expected Output
Shows the full lifecycle of an agent identity from creation through revocation.
