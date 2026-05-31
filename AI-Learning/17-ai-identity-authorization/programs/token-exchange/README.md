# Token Exchange

Simulates the OAuth2 On-Behalf-Of (OBO) token exchange flow, demonstrating how user tokens are exchanged for agent tokens with narrowed scope.

## Concepts Demonstrated
- User token → OBO token exchange
- Scope narrowing (agent gets less than user)
- Delegation chains (User → Agent A → Agent B)
- Full audit trail of delegation
- Scope violation detection

## Run
```bash
pip install -r requirements.txt
python main.py
```
