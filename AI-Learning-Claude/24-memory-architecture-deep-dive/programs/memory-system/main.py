"""
Complete Memory System for AI Agents
Demonstrates all 6 memory types with multi-backend storage.
"""

import os
import json
import time
import hashlib
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

# =============================================================================
# MEMORY TYPE 1: Working Memory (In-Context)
# =============================================================================

class WorkingMemory:
    """Manages what's currently in the LLM's context window."""

    def __init__(self, max_tokens=4000):
        self.max_tokens = max_tokens
        self.system_prompt = ""
        self.memory_injection = ""
        self.conversation = []

    def set_system_prompt(self, prompt: str):
        self.system_prompt = prompt

    def set_memory_injection(self, memories: str):
        self.memory_injection = memories

    def add_message(self, role: str, content: str):
        self.conversation.append({"role": role, "content": content})

    def get_messages(self) -> list:
        """Build the full message list for LLM call."""
        messages = []
        system = self.system_prompt
        if self.memory_injection:
            system += f"\n\n## Relevant Memories\n{self.memory_injection}"
        messages.append({"role": "system", "content": system})
        messages.extend(self.conversation)
        return messages

    def estimate_tokens(self) -> int:
        total_text = self.system_prompt + self.memory_injection
        total_text += " ".join(m["content"] for m in self.conversation)
        return len(total_text) // 4  # Rough estimate

    def __repr__(self):
        return (f"WorkingMemory(tokens≈{self.estimate_tokens()}, "
                f"messages={len(self.conversation)})")


# =============================================================================
# MEMORY TYPE 2: Short-Term Memory (Session Buffer)
# =============================================================================

class ShortTermMemory:
    """Session-scoped memory buffer with configurable capacity."""

    def __init__(self, max_items=50):
        self.buffer = deque(maxlen=max_items)
        self.session_start = datetime.now()

    def add(self, role: str, content: str, metadata: dict = None):
        self.buffer.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "turn": len(self.buffer),
            "metadata": metadata or {}
        })

    def get_recent(self, n=10) -> list:
        return list(self.buffer)[-n:]

    def search(self, keyword: str) -> list:
        """Simple keyword search over buffer."""
        results = []
        for item in self.buffer:
            if keyword.lower() in item["content"].lower():
                results.append(item)
        return results

    def get_stats(self) -> dict:
        return {
            "total_messages": len(self.buffer),
            "session_duration": str(datetime.now() - self.session_start),
            "capacity_used": f"{len(self.buffer)}/{self.buffer.maxlen}"
        }

    def __repr__(self):
        return f"ShortTermMemory(items={len(self.buffer)}/{self.buffer.maxlen})"


# =============================================================================
# MEMORY TYPE 3: Long-Term Memory (Persistent File Storage)
# =============================================================================

class LongTermMemory:
    """Persistent memory stored as JSON file with semantic-ish search."""

    def __init__(self, storage_path="long_term_memory.json"):
        self.storage_path = storage_path
        self.memories = self._load()

    def _load(self) -> list:
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r") as f:
                return json.load(f)
        return []

    def _save(self):
        with open(self.storage_path, "w") as f:
            json.dump(self.memories, f, indent=2)

    def store(self, content: str, memory_type: str, importance: float = 0.5,
              metadata: dict = None):
        memory = {
            "id": hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:12],
            "content": content,
            "type": memory_type,
            "importance": importance,
            "access_count": 0,
            "created_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.memories.append(memory)
        self._save()
        return memory["id"]

    def recall(self, query: str, top_k: int = 5) -> list:
        """Simple keyword-based recall (production would use embeddings)."""
        scored = []
        query_words = set(query.lower().split())

        for mem in self.memories:
            mem_words = set(mem["content"].lower().split())
            overlap = len(query_words & mem_words)
            if overlap > 0:
                score = overlap / len(query_words) * mem["importance"]
                scored.append((mem, score))
                mem["access_count"] += 1
                mem["last_accessed"] = datetime.now().isoformat()

        scored.sort(key=lambda x: x[1], reverse=True)
        self._save()
        return [m for m, s in scored[:top_k]]

    def forget(self, memory_id: str):
        self.memories = [m for m in self.memories if m["id"] != memory_id]
        self._save()

    def get_all(self) -> list:
        return self.memories

    def __repr__(self):
        return f"LongTermMemory(count={len(self.memories)})"


# =============================================================================
# MEMORY TYPE 4: Episodic Memory (Events/Interactions)
# =============================================================================

class EpisodicMemory:
    """Stores specific events with context and outcomes."""

    def __init__(self, storage_path="episodic_memory.json"):
        self.storage_path = storage_path
        self.episodes = self._load()

    def _load(self) -> list:
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r") as f:
                return json.load(f)
        return []

    def _save(self):
        with open(self.storage_path, "w") as f:
            json.dump(self.episodes, f, indent=2)

    def record_episode(self, summary: str, topic: str, outcome: str,
                       user_satisfaction: str = "neutral", lessons: list = None):
        episode = {
            "id": f"ep_{len(self.episodes)+1:03d}",
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "topic": topic,
            "outcome": outcome,
            "user_satisfaction": user_satisfaction,
            "lessons": lessons or [],
        }
        self.episodes.append(episode)
        self._save()
        return episode

    def recall_similar(self, topic: str, n=3) -> list:
        """Find episodes about similar topics."""
        topic_words = set(topic.lower().split())
        scored = []
        for ep in self.episodes:
            ep_words = set(ep["topic"].lower().split() + ep["summary"].lower().split())
            overlap = len(topic_words & ep_words)
            if overlap > 0:
                scored.append((ep, overlap))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [ep for ep, s in scored[:n]]

    def get_recent(self, n=5) -> list:
        return self.episodes[-n:]

    def __repr__(self):
        return f"EpisodicMemory(episodes={len(self.episodes)})"


# =============================================================================
# MEMORY TYPE 5: Semantic Memory (Knowledge Graph)
# =============================================================================

class SemanticMemory:
    """Structured entity-relationship knowledge."""

    def __init__(self):
        self.entities = {}  # entity_name -> {attributes}
        self.relations = []  # (subject, predicate, object)

    def add_entity(self, name: str, attributes: dict):
        if name in self.entities:
            self.entities[name].update(attributes)
        else:
            self.entities[name] = attributes

    def add_relation(self, subject: str, predicate: str, obj: str):
        relation = (subject, predicate, obj)
        if relation not in self.relations:
            self.relations.append(relation)

    def query_entity(self, name: str) -> dict:
        return self.entities.get(name, {})

    def query_relations(self, subject=None, predicate=None, obj=None) -> list:
        results = self.relations
        if subject:
            results = [r for r in results if r[0] == subject]
        if predicate:
            results = [r for r in results if r[1] == predicate]
        if obj:
            results = [r for r in results if r[2] == obj]
        return results

    def get_summary(self) -> str:
        """Get compact text representation."""
        lines = []
        for entity, attrs in self.entities.items():
            attr_str = ", ".join(f"{k}={v}" for k, v in attrs.items())
            lines.append(f"  {entity}: {attr_str}")
        for s, p, o in self.relations:
            lines.append(f"  {s} --[{p}]--> {o}")
        return "Entities:\n" + "\n".join(lines[:10]) if lines else "(empty)"

    def __repr__(self):
        return f"SemanticMemory(entities={len(self.entities)}, relations={len(self.relations)})"


# =============================================================================
# MEMORY TYPE 6: Procedural Memory (Learned Patterns)
# =============================================================================

class ProceduralMemory:
    """Learned behaviors and response patterns."""

    def __init__(self):
        self.procedures = []

    def add_procedure(self, trigger: str, actions: list, learned_from: str = ""):
        self.procedures.append({
            "trigger": trigger,
            "actions": actions,
            "learned_from": learned_from,
            "created_at": datetime.now().isoformat(),
            "times_applied": 0
        })

    def match(self, context: str) -> list:
        """Find procedures that match current context."""
        matched = []
        context_lower = context.lower()
        for proc in self.procedures:
            if proc["trigger"].lower() in context_lower:
                proc["times_applied"] += 1
                matched.append(proc)
        return matched

    def get_all(self) -> list:
        return self.procedures

    def __repr__(self):
        return f"ProceduralMemory(procedures={len(self.procedures)})"


# =============================================================================
# UNIFIED MEMORY SYSTEM
# =============================================================================

class MemorySystem:
    """Unified memory system combining all 6 memory types."""

    def __init__(self):
        self.working = WorkingMemory()
        self.short_term = ShortTermMemory(max_items=50)
        self.long_term = LongTermMemory(storage_path="/tmp/lt_memory_demo.json")
        self.episodic = EpisodicMemory(storage_path="/tmp/episodic_demo.json")
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()

        # Set up base system prompt
        self.working.set_system_prompt(
            "You are a helpful AI assistant with persistent memory. "
            "You remember user preferences and past interactions. "
            "Use your memories to provide personalized, contextual responses. "
            "Keep responses concise."
        )

    def process_user_input(self, user_input: str):
        """Process input through all memory systems."""
        # 1. Add to short-term
        self.short_term.add("user", user_input)

        # 2. Check procedural memory for matching patterns
        procedures = self.procedural.match(user_input)

        # 3. Recall from long-term memory
        relevant_memories = self.long_term.recall(user_input, top_k=3)

        # 4. Check episodic memory for similar past interactions
        similar_episodes = self.episodic.recall_similar(user_input, n=2)

        # 5. Build memory injection for working memory
        injection = self._build_injection(relevant_memories, similar_episodes, procedures)
        self.working.set_memory_injection(injection)

        # 6. Add to working memory conversation
        self.working.add_message("user", user_input)

    def _build_injection(self, memories, episodes, procedures) -> str:
        parts = []

        # Semantic memory (always include if available)
        semantic_summary = self.semantic.get_summary()
        if semantic_summary != "(empty)":
            parts.append(f"**Known Facts:**\n{semantic_summary}")

        # Relevant long-term memories
        if memories:
            mem_text = "\n".join(f"- {m['content']}" for m in memories)
            parts.append(f"**Relevant Memories:**\n{mem_text}")

        # Similar past episodes
        if episodes:
            ep_text = "\n".join(
                f"- [{e['timestamp'][:10]}] {e['summary']} (outcome: {e['outcome']})"
                for e in episodes
            )
            parts.append(f"**Similar Past Interactions:**\n{ep_text}")

        # Procedural guidance
        if procedures:
            proc_text = "\n".join(
                f"- When '{p['trigger']}': {', '.join(p['actions'])}"
                for p in procedures
            )
            parts.append(f"**Learned Behaviors:**\n{proc_text}")

        return "\n\n".join(parts) if parts else ""

    def generate_response(self, user_input: str) -> str:
        """Generate a response using the full memory system."""
        self.process_user_input(user_input)

        # Call LLM
        messages = self.working.get_messages()

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            assistant_msg = response.choices[0].message.content
        except Exception as e:
            assistant_msg = f"[LLM call failed: {e}. Using mock response.]"
            assistant_msg = self._mock_response(user_input)

        # Post-processing: update memories
        self.working.add_message("assistant", assistant_msg)
        self.short_term.add("assistant", assistant_msg)
        self._extract_and_store(user_input, assistant_msg)

        return assistant_msg

    def _mock_response(self, user_input: str) -> str:
        """Fallback mock response when LLM is unavailable."""
        memories = self.long_term.recall(user_input, top_k=2)
        if memories:
            return f"Based on what I remember ({memories[0]['content']}), I can help with that."
        return "I'll remember this for next time. How can I help?"

    def _extract_and_store(self, user_input: str, response: str):
        """Extract facts and preferences from the exchange."""
        input_lower = user_input.lower()

        # Detect preferences
        preference_signals = ["i prefer", "i like", "i want", "i need", "please always"]
        for signal in preference_signals:
            if signal in input_lower:
                self.long_term.store(
                    user_input, "preference", importance=0.8,
                    metadata={"source": "explicit_statement"}
                )
                break

        # Detect facts about user
        fact_signals = ["i work", "my name", "i am", "i'm a", "my project", "my team"]
        for signal in fact_signals:
            if signal in input_lower:
                self.long_term.store(
                    user_input, "fact", importance=0.7,
                    metadata={"source": "user_statement"}
                )
                # Also add to semantic memory
                self.semantic.add_entity("user", {"stated": user_input[:100]})
                break

    def record_interaction_episode(self, topic: str, outcome: str,
                                    satisfaction: str = "neutral"):
        """Record the current interaction as an episode."""
        recent = self.short_term.get_recent(5)
        summary = " | ".join(m["content"][:50] for m in recent)
        self.episodic.record_episode(
            summary=summary, topic=topic, outcome=outcome,
            user_satisfaction=satisfaction
        )

    def print_state(self):
        """Print the full state of all memory systems."""
        print("\n" + "=" * 60)
        print("MEMORY SYSTEM STATE")
        print("=" * 60)
        print(f"\n  Working Memory:    {self.working}")
        print(f"  Short-Term Memory: {self.short_term}")
        print(f"  Long-Term Memory:  {self.long_term}")
        print(f"  Episodic Memory:   {self.episodic}")
        print(f"  Semantic Memory:   {self.semantic}")
        print(f"  Procedural Memory: {self.procedural}")

        # Details
        if self.long_term.get_all():
            print("\n  Long-Term Contents:")
            for m in self.long_term.get_all()[-5:]:
                print(f"    [{m['type']}] {m['content'][:60]}... (importance: {m['importance']})")

        if self.semantic.entities:
            print(f"\n  Semantic Knowledge:\n    {self.semantic.get_summary()}")

        if self.procedural.get_all():
            print("\n  Procedures:")
            for p in self.procedural.get_all():
                print(f"    Trigger: '{p['trigger']}' → {p['actions']}")

        print("=" * 60 + "\n")


# =============================================================================
# DEMONSTRATION
# =============================================================================

def main():
    print("=" * 60)
    print("  MEMORY SYSTEM DEMONSTRATION")
    print("  Complete AI Agent Memory Architecture")
    print("=" * 60)

    mem = MemorySystem()

    # Pre-load some procedural memory
    mem.procedural.add_procedure(
        trigger="code",
        actions=["Provide code example", "Add comments", "Suggest best practices"],
        learned_from="Common user pattern"
    )
    mem.procedural.add_procedure(
        trigger="error",
        actions=["Ask for full error message", "Check common causes", "Provide fix"],
        learned_from="Support interaction pattern"
    )

    # Simulate conversation
    interactions = [
        ("I prefer Python and concise answers", "preference_setting"),
        ("I'm working on a RAG system for legal documents", "context_setting"),
        ("My team uses Qdrant for vector search", "fact_sharing"),
        ("How should I chunk legal documents?", "question"),
        ("Show me code for recursive chunking", "code_request"),
        ("We decided on 512 token chunks with 50 token overlap", "decision"),
    ]

    for i, (user_msg, interaction_type) in enumerate(interactions, 1):
        print(f"\n{'─' * 60}")
        print(f"  Turn {i} ({interaction_type})")
        print(f"{'─' * 60}")
        print(f"  User: {user_msg}")

        response = mem.generate_response(user_msg)
        print(f"  Agent: {response[:200]}...")

        # Record episode for significant interactions
        if interaction_type in ("decision", "code_request"):
            mem.record_interaction_episode(
                topic=interaction_type,
                outcome="completed",
                satisfaction="positive"
            )

        # Add semantic facts based on interaction type
        if interaction_type == "context_setting":
            mem.semantic.add_entity("user_project", {"type": "RAG", "domain": "legal"})
            mem.semantic.add_relation("user", "works_on", "RAG system")
        elif interaction_type == "fact_sharing":
            mem.semantic.add_entity("Qdrant", {"type": "vector_db", "role": "primary"})
            mem.semantic.add_relation("user_project", "uses", "Qdrant")
        elif interaction_type == "decision":
            mem.semantic.add_entity("chunking", {"size": "512", "overlap": "50"})
            mem.semantic.add_relation("user_project", "configured", "chunking")

    # Print final state
    mem.print_state()

    # Demonstrate memory recall
    print("\n" + "─" * 60)
    print("  MEMORY RECALL DEMONSTRATION")
    print("─" * 60)

    print("\n  Query: 'What vector database are we using?'")
    results = mem.long_term.recall("vector database Qdrant", top_k=3)
    for r in results:
        print(f"    Found: {r['content'][:80]}")

    print("\n  Query: 'chunking strategy'")
    results = mem.long_term.recall("chunk legal documents", top_k=3)
    for r in results:
        print(f"    Found: {r['content'][:80]}")

    print("\n  Semantic query: relations about user_project")
    rels = mem.semantic.query_relations(subject="user_project")
    for s, p, o in rels:
        print(f"    {s} --[{p}]--> {o}")

    # Show how memory improves next interaction
    print("\n" + "─" * 60)
    print("  MEMORY-ENHANCED RESPONSE")
    print("─" * 60)
    print("\n  User: 'What's the best embedding model for my use case?'")
    response = mem.generate_response("What's the best embedding model for my use case?")
    print(f"  Agent: {response[:300]}")
    print("\n  (Notice: agent has context about RAG, legal docs, Qdrant from memory)")

    # Cleanup demo files
    for f in ["/tmp/lt_memory_demo.json", "/tmp/episodic_demo.json"]:
        if os.path.exists(f):
            os.remove(f)

    print("\n\n  Demo complete. Memory files cleaned up.")


if __name__ == "__main__":
    main()
