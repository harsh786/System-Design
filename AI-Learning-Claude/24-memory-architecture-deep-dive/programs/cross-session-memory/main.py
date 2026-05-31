"""
Cross-Session Memory Demo
Simulates an AI agent that remembers across sessions.
"""

import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

try:
    client = OpenAI()
    USE_LLM = True
except Exception:
    USE_LLM = False
    print("[Note: OpenAI not configured. Using mock responses.]\n")


# =============================================================================
# MEMORY PROFILE (Persists across sessions)
# =============================================================================

class UserMemoryProfile:
    """Persistent user memory that lives across sessions."""

    def __init__(self, user_id: str, storage_path: str = "/tmp"):
        self.user_id = user_id
        self.file_path = os.path.join(storage_path, f"memory_profile_{user_id}.json")
        self.profile = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.file_path):
            with open(self.file_path, "r") as f:
                return json.load(f)
        return {
            "user_id": self.user_id,
            "created_at": datetime.now().isoformat(),
            "session_count": 0,
            "preferences": {},
            "context": {},
            "history": [],
            "pending": [],
            "learned_patterns": [],
            "entities": {}
        }

    def _save(self):
        with open(self.file_path, "w") as f:
            json.dump(self.profile, f, indent=2)

    def add_preference(self, key: str, value: str):
        self.profile["preferences"][key] = value
        self._save()

    def add_context(self, key: str, value):
        self.profile["context"][key] = value
        self._save()

    def add_history(self, topic: str, outcome: str, key_facts: list = None):
        self.profile["history"].append({
            "date": datetime.now().isoformat()[:10],
            "topic": topic,
            "outcome": outcome,
            "key_facts": key_facts or []
        })
        self._save()

    def add_pending(self, item: str):
        self.profile["pending"].append(item)
        self._save()

    def resolve_pending(self, item: str):
        self.profile["pending"] = [p for p in self.profile["pending"] if p != item]
        self._save()

    def add_entity(self, name: str, info: dict):
        self.profile["entities"][name] = info
        self._save()

    def increment_session(self):
        self.profile["session_count"] += 1
        self._save()

    def get_memory_context(self) -> str:
        """Build memory context string for prompt injection."""
        parts = []

        if self.profile["preferences"]:
            prefs = "\n".join(f"  - {k}: {v}" for k, v in self.profile["preferences"].items())
            parts.append(f"**User Preferences:**\n{prefs}")

        if self.profile["context"]:
            ctx = "\n".join(f"  - {k}: {v}" for k, v in self.profile["context"].items())
            parts.append(f"**Current Context:**\n{ctx}")

        if self.profile["pending"]:
            pend = "\n".join(f"  - {p}" for p in self.profile["pending"])
            parts.append(f"**Pending Items:**\n{pend}")

        if self.profile["history"]:
            recent = self.profile["history"][-3:]
            hist = "\n".join(f"  - [{h['date']}] {h['topic']}: {h['outcome']}" for h in recent)
            parts.append(f"**Recent History:**\n{hist}")

        if self.profile["entities"]:
            ents = "\n".join(f"  - {k}: {json.dumps(v)}" for k, v in list(self.profile["entities"].items())[:5])
            parts.append(f"**Known Entities:**\n{ents}")

        return "\n\n".join(parts) if parts else "(No memories yet)"

    def print_profile(self):
        """Pretty print the full profile."""
        print(f"\n  {'─' * 50}")
        print(f"  USER MEMORY PROFILE: {self.user_id}")
        print(f"  {'─' * 50}")
        print(f"  Sessions: {self.profile['session_count']}")
        print(f"  Preferences: {json.dumps(self.profile['preferences'], indent=4)}")
        print(f"  Context: {json.dumps(self.profile['context'], indent=4)}")
        print(f"  Pending: {self.profile['pending']}")
        print(f"  History entries: {len(self.profile['history'])}")
        print(f"  Entities tracked: {len(self.profile['entities'])}")
        print(f"  {'─' * 50}")

    def cleanup(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)


# =============================================================================
# SESSION-END EXTRACTOR
# =============================================================================

class SessionEndExtractor:
    """Extract important information at the end of a session."""

    def extract(self, messages: list, profile: UserMemoryProfile):
        """Extract and store information from session messages."""
        if USE_LLM:
            return self._extract_with_llm(messages, profile)
        else:
            return self._extract_mock(messages, profile)

    def _extract_with_llm(self, messages, profile):
        text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": """Analyze this conversation and extract:
1. User preferences (communication style, technical preferences)
2. Context facts (project info, team info, deadlines)
3. Decisions made
4. Pending/unresolved items
5. Key entities mentioned

Return JSON:
{"preferences": {"key": "value"}, "context": {"key": "value"}, "decisions": ["..."], "pending": ["..."], "entities": {"name": {"attr": "val"}}}"""
            }, {"role": "user", "content": text}],
            max_tokens=500
        )
        try:
            data = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            data = {}

        self._apply_extraction(data, profile)
        return data

    def _extract_mock(self, messages, profile):
        """Mock extraction based on keyword detection."""
        all_text = " ".join(m["content"] for m in messages).lower()

        extracted = {"preferences": {}, "context": {}, "decisions": [], "pending": [], "entities": {}}

        # Detect preferences
        if "concise" in all_text or "brief" in all_text:
            extracted["preferences"]["response_style"] = "concise"
        if "python" in all_text:
            extracted["preferences"]["language"] = "Python"
        if "code" in all_text and "example" in all_text:
            extracted["preferences"]["examples"] = "code examples preferred"

        # Detect context
        if "project" in all_text:
            extracted["context"]["has_active_project"] = True
        if "deadline" in all_text or "march" in all_text:
            extracted["context"]["deadline"] = "March 15"
        if "team" in all_text:
            extracted["context"]["team_mentioned"] = True

        # Detect decisions
        for m in messages:
            if "decided" in m["content"].lower() or "let's go with" in m["content"].lower():
                extracted["decisions"].append(m["content"][:80])

        # Detect pending
        for m in messages:
            if "later" in m["content"].lower() or "todo" in m["content"].lower() or "need to" in m["content"].lower():
                extracted["pending"].append(m["content"][:80])

        self._apply_extraction(extracted, profile)
        return extracted

    def _apply_extraction(self, data, profile):
        """Apply extracted information to profile."""
        for k, v in data.get("preferences", {}).items():
            profile.add_preference(k, v)
        for k, v in data.get("context", {}).items():
            profile.add_context(k, v)
        for item in data.get("pending", []):
            profile.add_pending(item)
        for name, info in data.get("entities", {}).items():
            profile.add_entity(name, info)
        if data.get("decisions"):
            profile.add_history(
                topic="decisions",
                outcome="; ".join(data["decisions"][:3]),
                key_facts=data["decisions"]
            )


# =============================================================================
# AGENT WITH CROSS-SESSION MEMORY
# =============================================================================

class MemoryAgent:
    """AI agent that uses cross-session memory."""

    def __init__(self, profile: UserMemoryProfile):
        self.profile = profile
        self.session_messages = []
        self.extractor = SessionEndExtractor()

    def start_session(self):
        """Initialize session with memory context."""
        self.profile.increment_session()
        self.session_messages = []

        memory_context = self.profile.get_memory_context()
        print(f"\n  [Memory injected into context:]")
        print(f"  {memory_context[:300]}...")
        return memory_context

    def chat(self, user_message: str) -> str:
        """Process a user message and generate response."""
        self.session_messages.append({"role": "user", "content": user_message})

        memory_context = self.profile.get_memory_context()

        if USE_LLM:
            messages = [
                {"role": "system", "content": f"""You are a helpful AI assistant with memory.
Use the following memories to personalize your response:

{memory_context}

Be concise. Reference past context when relevant."""},
            ]
            messages.extend(self.session_messages)
            response = client.chat.completions.create(
                model="gpt-4o-mini", messages=messages, max_tokens=200
            )
            reply = response.choices[0].message.content
        else:
            # Mock response using memory
            reply = self._mock_response(user_message, memory_context)

        self.session_messages.append({"role": "assistant", "content": reply})
        return reply

    def _mock_response(self, user_msg, memory_context):
        """Generate mock response that demonstrates memory usage."""
        prefs = self.profile.profile["preferences"]
        context = self.profile.profile["context"]

        if self.profile.profile["session_count"] > 1:
            # Later sessions reference memory
            if "continue" in user_msg.lower() or "last time" in user_msg.lower():
                history = self.profile.profile["history"]
                if history:
                    last = history[-1]
                    return f"Of course! Last time ({last['date']}) we discussed {last['topic']}. The outcome was: {last['outcome']}. Where would you like to pick up?"

            if context:
                ctx_str = ", ".join(f"{k}" for k in list(context.keys())[:3])
                return f"Based on what I remember about your context ({ctx_str}), here's my take on that..."

        # First session responses
        if "prefer" in user_msg.lower() or "like" in user_msg.lower():
            return "Got it! I'll remember that preference for future sessions."
        if "project" in user_msg.lower():
            return "Interesting project! I'll keep this context in mind. Tell me more about the requirements."
        return "I'll remember this for our future conversations. What else can I help with?"

    def end_session(self):
        """End session and extract memories."""
        print(f"\n  [Session ending... extracting memories]")
        extracted = self.extractor.extract(self.session_messages, self.profile)
        print(f"  [Extracted: {len(extracted.get('preferences', {}))} preferences, "
              f"{len(extracted.get('context', {}))} context items, "
              f"{len(extracted.get('pending', []))} pending items]")

        # Store session summary
        summary = " | ".join(m["content"][:40] for m in self.session_messages[:6])
        self.profile.add_history(
            topic="session_" + str(self.profile.profile["session_count"]),
            outcome=summary[:100]
        )


# =============================================================================
# DEMONSTRATION
# =============================================================================

def main():
    print("=" * 60)
    print("  CROSS-SESSION MEMORY DEMONSTRATION")
    print("=" * 60)

    profile = UserMemoryProfile("demo_user")

    # =========================================================================
    # SESSION 1: User introduces themselves and their project
    # =========================================================================
    print(f"\n{'━' * 60}")
    print("  SESSION 1: Initial Interaction")
    print(f"{'━' * 60}")

    agent = MemoryAgent(profile)
    agent.start_session()

    conversations_s1 = [
        "Hi! I prefer concise, technical responses. I'm a senior Python developer.",
        "I'm working on a RAG system for legal documents. Team of 5, deadline March 15.",
        "We chose Qdrant for vector search and BGE-large for embeddings.",
        "I need to figure out the chunking strategy still. Let's discuss that next time.",
    ]

    for msg in conversations_s1:
        print(f"\n  User: {msg}")
        reply = agent.chat(msg)
        print(f"  Agent: {reply}")

    agent.end_session()
    profile.print_profile()

    # =========================================================================
    # SESSION 2: User returns, agent should remember everything
    # =========================================================================
    print(f"\n{'━' * 60}")
    print("  SESSION 2: Returning User (next day)")
    print(f"{'━' * 60}")

    agent2 = MemoryAgent(profile)
    memory_ctx = agent2.start_session()

    conversations_s2 = [
        "Hey, I'm back. Can we continue where we left off?",
        "Right, the chunking. I'm thinking 512 tokens with overlap.",
        "Actually, let's go with 512 chunks and 64 token overlap. Decision made.",
        "Next I need to set up the evaluation pipeline. Add that to my todo.",
    ]

    for msg in conversations_s2:
        print(f"\n  User: {msg}")
        reply = agent2.chat(msg)
        print(f"  Agent: {reply}")

    agent2.end_session()
    profile.print_profile()

    # =========================================================================
    # SESSION 3: Further continuity
    # =========================================================================
    print(f"\n{'━' * 60}")
    print("  SESSION 3: Continued Project Work")
    print(f"{'━' * 60}")

    agent3 = MemoryAgent(profile)
    memory_ctx = agent3.start_session()

    conversations_s3 = [
        "What's on my pending list?",
        "Let's tackle the evaluation pipeline. I want to use RAGAS framework.",
        "Actually, I changed my mind about response style - give me detailed answers from now on.",
    ]

    for msg in conversations_s3:
        print(f"\n  User: {msg}")
        reply = agent3.chat(msg)
        print(f"  Agent: {reply}")

    agent3.end_session()

    # =========================================================================
    # FINAL STATE
    # =========================================================================
    print(f"\n{'━' * 60}")
    print("  FINAL MEMORY STATE (After 3 Sessions)")
    print(f"{'━' * 60}")

    profile.print_profile()

    print(f"\n  Memory context that would be injected into Session 4:")
    print(f"  {'─' * 50}")
    print(f"  {profile.get_memory_context()}")

    print(f"\n\n  KEY DEMONSTRATION POINTS:")
    print(f"  1. Preferences persisted across sessions (language, style)")
    print(f"  2. Project context maintained (RAG, legal, Qdrant)")
    print(f"  3. Decisions tracked with dates")
    print(f"  4. Pending items carried forward")
    print(f"  5. Preferences can be UPDATED (concise → detailed)")
    print(f"  6. Agent can reference past sessions naturally")

    # Cleanup
    profile.cleanup()
    print(f"\n  [Demo files cleaned up]")


if __name__ == "__main__":
    main()
