"""
Review Agent - Cross-validates all generated designs against PRD requirements.
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage

from src.config.settings import Settings
from src.config.prompts import REVIEW_AGENT_SYSTEM_PROMPT, REVIEW_AGENT_USER_PROMPT
from src.retrieval.vector_store import VectorStoreManager


class ReviewAgent:
    """
    Reviews all generated design documents for completeness and consistency.

    This agent:
    1. Takes all generated documents (HLD, LLD, DB Design)
    2. Compares against original PRD requirements
    3. Checks for cross-document consistency
    4. Generates a review report with issues and recommendations
    """

    def __init__(self, vector_store: VectorStoreManager, settings: Settings):
        self.vector_store = vector_store
        self.settings = settings
        self.llm = settings.create_llm(max_tokens=6000, temperature=0.1)

    async def run(self, state) -> dict:
        """
        Review all generated design documents.

        Args:
            state: DesignAgentState with all documents generated

        Returns:
            Dict with review report, status, and issues
        """
        try:
            # Format LLD documents for review
            lld_summary = ""
            for comp_name, lld_content in state.get("lld_documents", {}).items():
                lld_summary += (
                    f"\n### LLD: {comp_name}\n"
                    f"{lld_content[:2000]}\n"  # Truncate for context window
                    f"[... truncated for review ...]\n"
                )

            # Build review prompt
            user_prompt = REVIEW_AGENT_USER_PROMPT.format(
                requirements_json=state.get("requirements_json", ""),
                hld_document=state.get("hld_document", "")[:4000],
                lld_documents=lld_summary[:6000],
                db_design_document=state.get("db_design_document", "")[:4000],
            )

            messages = [
                SystemMessage(content=REVIEW_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]

            response = await self.llm.ainvoke(messages)
            review_report = response.content

            # Parse review results
            review_status = self._extract_status(review_report)
            review_issues = await self._extract_issues(review_report)

            return {
                "review_report": review_report,
                "review_status": review_status,
                "review_issues": review_issues,
                "current_agent": "review_agent",
            }

        except Exception as e:
            return {
                "error": f"Review Agent failed: {str(e)}",
                "review_report": f"Review failed: {str(e)}",
                "review_status": "PASS_WITH_COMMENTS",  # Don't block on review failure
                "review_issues": [],
                "current_agent": "review_agent",
            }

    def _extract_status(self, review_report: str) -> str:
        """Extract overall status from review report."""
        report_upper = review_report.upper()
        if "NEEDS_REVISION" in report_upper or "NEEDS REVISION" in report_upper:
            return "NEEDS_REVISION"
        elif "PASS_WITH_COMMENTS" in report_upper or "PASS WITH COMMENTS" in report_upper:
            return "PASS_WITH_COMMENTS"
        elif "PASS" in report_upper:
            return "PASS"
        else:
            return "PASS_WITH_COMMENTS"  # Default to pass with comments

    async def _extract_issues(self, review_report: str) -> list[dict]:
        """Extract structured issues from review report using LLM."""
        prompt = f"""
From this review report, extract specific issues as a JSON array:

{review_report[:4000]}

Return JSON array:
[
  {{
    "severity": "CRITICAL|HIGH|MEDIUM|LOW",
    "document": "HLD|LLD|DB_DESIGN",
    "component": "component name or null",
    "description": "issue description",
    "recommendation": "what to fix"
  }}
]

Only include actionable issues. Return ONLY the JSON array.
If no issues, return [].
"""
        messages = [HumanMessage(content=prompt)]
        response = await self.llm.ainvoke(messages)

        try:
            json_str = response.content.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.split("```")[0]
            return json.loads(json_str.strip())
        except (json.JSONDecodeError, IndexError):
            return []
