"""
Token Exchange - OAuth2 On-Behalf-Of Flow Simulation
Demonstrates scope narrowing and delegation chains.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field


@dataclass
class Token:
    subject: str  # Who this token represents
    actor: str | None  # Who is acting (for OBO tokens)
    scope: set[str]
    audience: str
    issued_at: datetime
    expires_at: datetime
    token_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    delegation_chain: list[dict] = field(default_factory=list)
    token_type: str = "bearer"

    def to_dict(self) -> dict:
        return {
            "jti": self.token_id,
            "sub": self.subject,
            "act": {"sub": self.actor} if self.actor else None,
            "scope": " ".join(sorted(self.scope)),
            "aud": self.audience,
            "iat": self.issued_at.isoformat(),
            "exp": self.expires_at.isoformat(),
            "delegation_chain": self.delegation_chain,
        }


class TokenExchangeError(Exception):
    pass


class SecurityTokenService:
    """Simulates an OAuth2 Security Token Service with OBO support."""

    def __init__(self):
        self.issued_tokens: list[dict] = []
        self.audit_log: list[dict] = []

    def _log(self, event: str, details: dict):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **details}
        self.audit_log.append(entry)

    def issue_user_token(self, user_id: str, scope: set[str], audience: str = "ai-platform") -> Token:
        """Issue a token for a user (simulates login)."""
        token = Token(
            subject=user_id,
            actor=None,
            scope=scope,
            audience=audience,
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        self._log("user_token_issued", {"user": user_id, "scope": list(scope)})
        self.issued_tokens.append(token.to_dict())
        return token

    def exchange_token(
        self,
        subject_token: Token,
        actor_id: str,
        requested_scope: set[str],
        audience: str,
        expires_in_seconds: int = 300,
    ) -> Token:
        """
        RFC 8693 Token Exchange - On-Behalf-Of.
        Creates a new token where actor acts on behalf of subject.
        """
        print(f"\n    [STS] Token exchange request:")
        print(f"         Subject: {subject_token.subject}")
        print(f"         Actor: {actor_id}")
        print(f"         Requested scope: {requested_scope}")
        print(f"         Subject's scope: {subject_token.scope}")

        # Validation 1: Subject token must not be expired
        if datetime.now(timezone.utc) > subject_token.expires_at:
            raise TokenExchangeError("Subject token expired")

        # Validation 2: Requested scope must be subset of subject's scope
        if not requested_scope.issubset(subject_token.scope):
            excess = requested_scope - subject_token.scope
            raise TokenExchangeError(
                f"Scope violation! Requested scope exceeds subject's scope. "
                f"Excess: {excess}"
            )

        # Build delegation chain
        chain = list(subject_token.delegation_chain)
        chain.append({
            "actor": actor_id,
            "delegated_at": datetime.now(timezone.utc).isoformat(),
            "scope_granted": list(requested_scope),
        })

        # Issue OBO token with narrowed scope
        obo_token = Token(
            subject=subject_token.subject,  # Original user stays as subject
            actor=actor_id,
            scope=requested_scope,  # Narrowed!
            audience=audience,
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
            delegation_chain=chain,
        )

        self._log("token_exchanged", {
            "subject": subject_token.subject,
            "actor": actor_id,
            "original_scope": list(subject_token.scope),
            "granted_scope": list(requested_scope),
            "audience": audience,
        })

        print(f"    [STS] ✓ Token issued. Effective scope: {requested_scope}")
        self.issued_tokens.append(obo_token.to_dict())
        return obo_token


class DownstreamService:
    """Simulates a downstream service that validates OBO tokens."""

    def __init__(self, name: str, required_scope: str):
        self.name = name
        self.required_scope = required_scope

    def handle_request(self, token: Token, action: str) -> dict:
        """Process request, checking the USER's permissions via OBO token."""
        print(f"\n    [{self.name}] Received request: {action}")
        print(f"         Token subject (user): {token.subject}")
        print(f"         Token actor (agent): {token.actor}")
        print(f"         Token scope: {token.scope}")

        if self.required_scope not in token.scope:
            print(f"    [{self.name}] ✗ DENIED - requires '{self.required_scope}'")
            return {"status": "denied", "reason": f"Missing scope: {self.required_scope}"}

        print(f"    [{self.name}] ✓ ALLOWED - user {token.subject} has required scope")
        return {"status": "success", "data": f"Results for {action}"}


def main():
    print("=" * 70)
    print("TOKEN EXCHANGE - On-Behalf-Of Flow Demo")
    print("=" * 70)

    sts = SecurityTokenService()

    # ─── Scenario 1: Basic OBO Exchange ───
    print("\n" + "─" * 50)
    print("SCENARIO 1: Basic On-Behalf-Of Exchange")
    print("─" * 50)

    # User logs in with full scope
    user_token = sts.issue_user_token(
        user_id="user:alice",
        scope={"documents.read", "documents.write", "databases.read", "admin.read"},
    )
    print(f"\n  User token issued:")
    print(f"    Subject: {user_token.subject}")
    print(f"    Scope: {user_token.scope}")

    # Agent exchanges for narrower scope
    print("\n  Agent 'coordinator-v2' requests token exchange (read only):")
    agent_token = sts.exchange_token(
        subject_token=user_token,
        actor_id="agent:coordinator-v2",
        requested_scope={"documents.read", "databases.read"},  # Narrower!
        audience="document-service",
        expires_in_seconds=300,
    )

    print(f"\n  OBO Token result:")
    print(f"    Subject (user): {agent_token.subject}")
    print(f"    Actor (agent): {agent_token.actor}")
    print(f"    Scope: {agent_token.scope} (narrower than user's)")
    print(f"    Expires in: 300 seconds")

    # Downstream service checks
    doc_service = DownstreamService("DocumentService", "documents.read")
    doc_service.handle_request(agent_token, "search engineering docs")

    # ─── Scenario 2: Scope Violation (agent tries to exceed user's scope) ───
    print("\n" + "─" * 50)
    print("SCENARIO 2: Scope Violation Attempt")
    print("─" * 50)

    print("\n  Agent tries to request 'payments.execute' (user doesn't have it):")
    try:
        bad_token = sts.exchange_token(
            subject_token=user_token,
            actor_id="agent:coordinator-v2",
            requested_scope={"documents.read", "payments.execute"},  # User doesn't have this!
            audience="payment-service",
        )
    except TokenExchangeError as e:
        print(f"\n  ✗ REJECTED: {e}")

    # ─── Scenario 3: Multi-Level Delegation Chain ───
    print("\n" + "─" * 50)
    print("SCENARIO 3: Delegation Chain (User → Agent A → Agent B → Tool)")
    print("─" * 50)

    # Level 0: User
    print("\n  Level 0 - User 'bob' authenticates:")
    bob_token = sts.issue_user_token(
        user_id="user:bob",
        scope={"documents.read", "documents.write", "databases.read", "databases.write"},
    )
    print(f"    Scope: {bob_token.scope}")

    # Level 1: Coordinator agent (gets read + write docs, read db)
    print("\n  Level 1 - Coordinator agent requests delegation:")
    coordinator_token = sts.exchange_token(
        subject_token=bob_token,
        actor_id="agent:coordinator-v2",
        requested_scope={"documents.read", "documents.write", "databases.read"},
        audience="agent-layer",
        expires_in_seconds=600,
    )

    # Level 2: Specialist agent (gets only db read)
    print("\n  Level 2 - DB Specialist agent requests delegation from coordinator:")
    specialist_token = sts.exchange_token(
        subject_token=coordinator_token,
        actor_id="agent:db-specialist",
        requested_scope={"databases.read"},  # Even narrower
        audience="database-service",
        expires_in_seconds=120,
    )

    # Show full delegation chain
    print("\n  Full Delegation Chain:")
    print(f"    Original subject: {specialist_token.subject}")
    print(f"    Current actor: {specialist_token.actor}")
    print(f"    Effective scope: {specialist_token.scope}")
    print(f"    Chain:")
    for i, link in enumerate(specialist_token.delegation_chain):
        print(f"      Level {i+1}: {link['actor']} → scope: {link['scope_granted']}")

    # Level 2 agent tries to access documents (should fail - not in its scope)
    print("\n  Specialist agent tries to access documents (not in its narrowed scope):")
    doc_service2 = DownstreamService("DocumentService", "documents.read")
    doc_service2.handle_request(specialist_token, "read confidential doc")

    # Level 2 agent accesses database (should succeed)
    print("\n  Specialist agent tries to access database (in its scope):")
    db_service = DownstreamService("DatabaseService", "databases.read")
    db_service.handle_request(specialist_token, "SELECT * FROM sales")

    # ─── Audit Trail ───
    print("\n" + "─" * 50)
    print("FULL AUDIT TRAIL")
    print("─" * 50)
    for entry in sts.audit_log:
        ts = entry["timestamp"][:19]
        event = entry["event"]
        if event == "user_token_issued":
            print(f"  [{ts}] User '{entry['user']}' authenticated, scope={entry['scope']}")
        elif event == "token_exchanged":
            print(f"  [{ts}] Exchange: {entry['actor']} on behalf of {entry['subject']}")
            print(f"           Scope narrowed: {entry['original_scope']} → {entry['granted_scope']}")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
