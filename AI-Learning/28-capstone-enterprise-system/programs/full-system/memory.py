"""
Memory system.
Session memory (conversation history) and user preferences.
"""

import time
from typing import Optional


class MemorySystem:
    """Manages session memory and user preferences."""

    def __init__(self):
        self.sessions: dict[str, list[dict]] = {}  # session_id → messages
        self.user_preferences: dict[str, dict] = {}  # user_id → preferences
        print("[MEMORY] Memory system initialized")

    def store_message(self, session_id: str, role: str, content: str):
        """Store a message in session memory."""
        if session_id not in self.sessions:
            self.sessions[session_id] = []

        self.sessions[session_id].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })

        # Keep only last 20 messages per session
        if len(self.sessions[session_id]) > 20:
            self.sessions[session_id] = self.sessions[session_id][-20:]

        print(f"[MEMORY] Stored {role} message in session={session_id} (total: {len(self.sessions[session_id])})")

    def get_history(self, session_id: str, limit: int = 10) -> list[dict]:
        """Get conversation history for a session."""
        messages = self.sessions.get(session_id, [])
        return messages[-limit:]

    def store_preference(self, user_id: str, key: str, value: str):
        """Store a user preference."""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {}
        self.user_preferences[user_id][key] = value
        print(f"[MEMORY] Stored preference for user={user_id}: {key}={value}")

    def get_preferences(self, user_id: str) -> dict:
        """Get all preferences for a user."""
        return self.user_preferences.get(user_id, {})

    def extract_preferences(self, text: str) -> dict:
        """Extract preferences from user message (simple heuristic)."""
        prefs = {}
        text_lower = text.lower()
        if "detailed" in text_lower or "verbose" in text_lower:
            prefs["detail_level"] = "detailed"
        if "brief" in text_lower or "short" in text_lower or "concise" in text_lower:
            prefs["detail_level"] = "brief"
        if "my name is" in text_lower:
            # Extract name
            import re
            match = re.search(r"my name is (\w+)", text_lower)
            if match:
                prefs["name"] = match.group(1).capitalize()
        return prefs

    def get_context_for_query(self, session_id: str, user_id: str) -> str:
        """Build context string from memory for a query."""
        parts = []

        # Add conversation history
        history = self.get_history(session_id, limit=5)
        if history:
            parts.append("Recent conversation:")
            for msg in history:
                parts.append(f"  {msg['role']}: {msg['content'][:100]}")

        # Add user preferences
        prefs = self.get_preferences(user_id)
        if prefs:
            parts.append(f"User preferences: {prefs}")

        return "\n".join(parts) if parts else ""

    def forget_session(self, session_id: str):
        """Clear a session's memory."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            print(f"[MEMORY] Forgot session={session_id}")

    def get_stats(self) -> dict:
        return {
            "active_sessions": len(self.sessions),
            "users_with_preferences": len(self.user_preferences),
            "total_messages": sum(len(msgs) for msgs in self.sessions.values()),
        }


# Global instance
memory = MemorySystem()
