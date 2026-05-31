# Delegation Chain

Simulates a 3-level delegation chain where each level narrows permissions. Demonstrates audit trails and revocation cascading.

## Concepts Demonstrated
- Multi-level delegation: User → Coordinator → Specialist → Tool
- Scope narrowing at each level
- Full audit trail of authorization decisions
- Revocation: breaking one level breaks all downstream

## Run
```bash
pip install -r requirements.txt
python main.py
```
