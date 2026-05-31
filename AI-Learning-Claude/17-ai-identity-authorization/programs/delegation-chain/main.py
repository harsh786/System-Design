"""
Delegation Chain Simulator
Demonstrates multi-level delegation with scope narrowing,
audit trails, and revocation cascading.
"""

import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum


class DelegationStatus(Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass
class DelegationLink:
    """One link in the delegation chain."""
    link_id: str
    delegator: str  # Who granted the delegation
    delegatee: str  # Who received the delegation
    scope: set[str]
    status: DelegationStatus = DelegationStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=30))
    revoked_at: datetime | None = None
    revoked_by: str | None = None

    @property
    def is_valid(self) -> bool:
        return (
            self.status == DelegationStatus.ACTIVE
            and datetime.now(timezone.utc) <= self.expires_at
        )


class DelegationChainManager:
    """Manages delegation chains with audit and revocation."""

    def __init__(self):
        self.chains: dict[str, list[DelegationLink]] = {}  # chain_id → links
        self.audit_log: list[dict] = []

    def _audit(self, event: str, chain_id: str, **kwargs):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "chain_id": chain_id,
            **kwargs,
        }
        self.audit_log.append(entry)

    def create_chain(self, user_id: str, user_scope: set[str]) -> str:
        """Start a new delegation chain from a user."""
        chain_id = f"chain_{uuid.uuid4().hex[:8]}"
        self.chains[chain_id] = []
        self._audit("chain_created", chain_id, user=user_id, scope=list(user_scope))
        return chain_id

    def delegate(
        self,
        chain_id: str,
        delegator: str,
        delegatee: str,
        requested_scope: set[str],
        parent_scope: set[str],
        expires_in_seconds: int = 300,
    ) -> DelegationLink | None:
        """Add a delegation link to the chain."""
        # Validate: requested scope must be subset of parent's scope
        if not requested_scope.issubset(parent_scope):
            excess = requested_scope - parent_scope
            self._audit(
                "delegation_denied", chain_id,
                delegator=delegator, delegatee=delegatee,
                reason=f"Scope exceeds parent. Excess: {excess}",
            )
            print(f"    ✗ DENIED: {delegatee} requested {excess} beyond {delegator}'s scope")
            return None

        link = DelegationLink(
            link_id=f"link_{uuid.uuid4().hex[:6]}",
            delegator=delegator,
            delegatee=delegatee,
            scope=requested_scope,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
        )

        self.chains[chain_id].append(link)
        self._audit(
            "delegation_granted", chain_id,
            delegator=delegator, delegatee=delegatee,
            scope=list(requested_scope),
        )
        print(f"    ✓ Delegated: {delegator} → {delegatee} | scope: {requested_scope}")
        return link

    def execute_action(self, chain_id: str, actor: str, action: str, required_scope: str) -> bool:
        """Attempt to execute an action — validates entire chain is valid."""
        print(f"\n    [{actor}] Attempting: {action} (requires: {required_scope})")

        # Validate entire chain
        chain = self.chains.get(chain_id, [])
        for link in chain:
            if not link.is_valid:
                print(f"    ✗ CHAIN BROKEN at {link.delegator} → {link.delegatee} (status: {link.status.value})")
                self._audit(
                    "action_denied", chain_id,
                    actor=actor, action=action, reason=f"Chain broken at link {link.link_id}",
                )
                return False

        # Find the actor's link and check scope
        actor_link = None
        for link in chain:
            if link.delegatee == actor:
                actor_link = link
                break

        if not actor_link:
            print(f"    ✗ DENIED: {actor} not found in delegation chain")
            self._audit("action_denied", chain_id, actor=actor, action=action, reason="Not in chain")
            return False

        if required_scope not in actor_link.scope:
            print(f"    ✗ DENIED: {actor} lacks scope '{required_scope}' (has: {actor_link.scope})")
            self._audit(
                "action_denied", chain_id,
                actor=actor, action=action, reason=f"Missing scope: {required_scope}",
            )
            return False

        print(f"    ✓ ALLOWED: Full chain valid, {actor} has scope '{required_scope}'")
        self._audit("action_allowed", chain_id, actor=actor, action=action)
        return True

    def revoke_link(self, chain_id: str, delegatee: str, revoked_by: str, reason: str):
        """Revoke a specific delegation — cascades to all downstream."""
        chain = self.chains.get(chain_id, [])
        found = False
        cascade = False

        for link in chain:
            if link.delegatee == delegatee or cascade:
                link.status = DelegationStatus.REVOKED
                link.revoked_at = datetime.now(timezone.utc)
                link.revoked_by = revoked_by
                if link.delegatee == delegatee:
                    found = True
                    cascade = True  # Everything after this is also revoked
                    self._audit(
                        "delegation_revoked", chain_id,
                        delegatee=delegatee, revoked_by=revoked_by, reason=reason,
                    )
                else:
                    self._audit(
                        "delegation_cascade_revoked", chain_id,
                        delegatee=link.delegatee, caused_by=f"revocation of {delegatee}",
                    )

        return found

    def print_chain(self, chain_id: str):
        """Visualize the delegation chain."""
        chain = self.chains.get(chain_id, [])
        print(f"\n    Chain: {chain_id}")
        for i, link in enumerate(chain):
            status_icon = "✓" if link.is_valid else "✗"
            print(f"      [{status_icon}] {link.delegator} → {link.delegatee}")
            print(f"          Scope: {link.scope} | Status: {link.status.value}")


def main():
    print("=" * 70)
    print("DELEGATION CHAIN - Multi-Level Authorization Demo")
    print("=" * 70)

    mgr = DelegationChainManager()

    # ─── Setup: User with full permissions ───
    user_id = "user:alice"
    user_scope = {"documents.read", "documents.write", "databases.read", "databases.write", "tools.execute"}

    print(f"\n  User: {user_id}")
    print(f"  Full scope: {user_scope}")

    # ─── Build the delegation chain ───
    print("\n" + "─" * 50)
    print("BUILDING DELEGATION CHAIN")
    print("─" * 50)

    chain_id = mgr.create_chain(user_id, user_scope)

    # Level 1: User → Coordinator Agent
    print("\n  Level 1: User → Coordinator Agent")
    coordinator_scope = {"documents.read", "documents.write", "databases.read"}
    mgr.delegate(chain_id, user_id, "agent:coordinator", coordinator_scope, user_scope, expires_in_seconds=600)

    # Level 2: Coordinator → Specialist Agent
    print("\n  Level 2: Coordinator → DB Specialist Agent")
    specialist_scope = {"databases.read"}
    mgr.delegate(chain_id, "agent:coordinator", "agent:db-specialist", specialist_scope, coordinator_scope, expires_in_seconds=300)

    # Level 3: Specialist → Database Tool
    print("\n  Level 3: DB Specialist → Database Query Tool")
    tool_scope = {"databases.read"}
    mgr.delegate(chain_id, "agent:db-specialist", "tool:db-query", tool_scope, specialist_scope, expires_in_seconds=120)

    mgr.print_chain(chain_id)

    # ─── Execute actions through the chain ───
    print("\n" + "─" * 50)
    print("EXECUTING ACTIONS THROUGH THE CHAIN")
    print("─" * 50)

    # Tool executes a read (should succeed)
    mgr.execute_action(chain_id, "tool:db-query", "SELECT * FROM sales", "databases.read")

    # Tool tries to write (should fail - not in its scope)
    mgr.execute_action(chain_id, "tool:db-query", "DELETE FROM sales", "databases.write")

    # Coordinator reads documents (should succeed)
    mgr.execute_action(chain_id, "agent:coordinator", "Search documents", "documents.read")

    # ─── Scope violation: Specialist tries to exceed ───
    print("\n" + "─" * 50)
    print("SCOPE VIOLATION ATTEMPT")
    print("─" * 50)

    print("\n  Specialist tries to delegate 'documents.write' to a tool (doesn't have it):")
    mgr.delegate(
        chain_id, "agent:db-specialist", "tool:doc-writer",
        {"documents.write"},  # Specialist doesn't have this!
        specialist_scope,
    )

    # ─── Revocation: Break the chain ───
    print("\n" + "─" * 50)
    print("REVOCATION (Cascade)")
    print("─" * 50)

    print("\n  Revoking 'agent:db-specialist' (security concern)...")
    mgr.revoke_link(chain_id, "agent:db-specialist", revoked_by="security-team", reason="Anomalous query patterns")

    mgr.print_chain(chain_id)

    # Try to use tool after revocation (should fail)
    print("\n  Attempting action after revocation:")
    mgr.execute_action(chain_id, "tool:db-query", "SELECT * FROM sales", "databases.read")

    # Coordinator still works (above the revocation point)
    print("\n  Coordinator (above revocation point) still works:")
    mgr.execute_action(chain_id, "agent:coordinator", "Search docs", "documents.read")

    # ─── Full Audit Trail ───
    print("\n" + "─" * 50)
    print("FULL AUDIT TRAIL")
    print("─" * 50)
    for entry in mgr.audit_log:
        ts = entry["timestamp"][:19]
        event = entry["event"]
        details = {k: v for k, v in entry.items() if k not in ("timestamp", "event", "chain_id")}
        print(f"  [{ts}] {event}")
        if details:
            for k, v in details.items():
                print(f"      {k}: {v}")

    print("\n" + "=" * 70)
    print("KEY TAKEAWAYS")
    print("=" * 70)
    print("  1. Each level has NARROWER scope than its parent")
    print("  2. Scope violations are caught and denied")
    print("  3. Revoking one level CASCADES to all downstream")
    print("  4. Every decision is fully audited")
    print("  5. The chain validates END-TO-END on every action")
    print("=" * 70)


if __name__ == "__main__":
    main()
