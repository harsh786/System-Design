"""
HLD Generator Agent - Generates High-Level Design documents.
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage

from src.config.settings import Settings
from src.config.prompts import HLD_GENERATOR_SYSTEM_PROMPT, HLD_GENERATOR_USER_PROMPT
from src.retrieval.vector_store import VectorStoreManager


class HLDGeneratorAgent:
    """
    Generates comprehensive High-Level Design documents.

    This agent:
    1. Takes structured requirements from PRD Analyzer
    2. Retrieves existing HLD context from vector store
    3. Generates a complete HLD with architecture diagrams
    4. Extracts component list for LLD generation
    """

    def __init__(self, vector_store: VectorStoreManager, settings: Settings):
        self.vector_store = vector_store
        self.settings = settings
        self.llm = settings.create_llm(max_tokens=8000)

    async def run(self, state) -> dict:
        """
        Generate the High-Level Design document.

        Args:
            state: DesignAgentState with requirements populated

        Returns:
            Dict with HLD document and extracted components
        """
        try:
            # Step 1: Retrieve existing HLD context
            requirements_json = state.get("requirements_json", "")
            project_name = state.get("project_name", "Unknown")
            project_summary = requirements_json[:500]
            hld_context = await self.vector_store.retrieve_for_hld(
                query=f"architecture design for {project_name} {project_summary}"
            )

            # Step 2: Build technology context from existing docs
            tech_stack_context = self._build_tech_context(state.get("existing_docs", []))

            # Step 3: Build prompt
            user_prompt = HLD_GENERATOR_USER_PROMPT.format(
                requirements_json=requirements_json,
                existing_hld_context=hld_context,
                tech_stack_context=tech_stack_context,
            )

            # Step 4: Call LLM
            messages = [
                SystemMessage(content=HLD_GENERATOR_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]

            # If this is a revision, add review feedback
            if state.get("review_iteration", 0) > 0 and state.get("review_issues"):
                hld_issues = [
                    issue for issue in state.get("review_issues", [])
                    if issue.get("document") == "HLD"
                ]
                if hld_issues:
                    feedback = "## Review Feedback (Please address these issues):\n"
                    for issue in hld_issues:
                        feedback += (
                            f"- [{issue['severity']}] {issue['description']}\n"
                            f"  Recommendation: {issue.get('recommendation', 'N/A')}\n"
                        )
                    messages.append(HumanMessage(content=feedback))

            response = await self.llm.ainvoke(messages)
            hld_document = response.content

            # Step 5: Extract components from HLD
            components = await self._extract_components(hld_document)

            # Step 6: Extract technology choices
            tech_choices = await self._extract_tech_choices(hld_document)
            db_technology = tech_choices.get("database", "PostgreSQL")

            return {
                "hld_document": hld_document,
                "components": components,
                "tech_choices": tech_choices,
                "db_technology": db_technology,
                "current_agent": "hld_generator",
            }

        except Exception as e:
            return {
                "error": f"HLD Generator failed: {str(e)}",
                "hld_document": "",
                "current_agent": "hld_generator",
            }

    async def _extract_components(self, hld_document: str) -> list[dict]:
        """Extract component list from HLD document using LLM."""
        extraction_prompt = f"""
From the following HLD document, extract a list of system components 
that need detailed Low-Level Design.

HLD Document:
{hld_document[:4000]}

Return a JSON array of components:
[
  {{
    "name": "component-name",
    "responsibility": "brief description",
    "technology": "primary technology"
  }}
]

Only include components that need LLD (not external systems like databases or message brokers).
Return ONLY the JSON array, no other text.
"""
        messages = [HumanMessage(content=extraction_prompt)]
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
            # Fallback: return a default component
            return [
                {
                    "name": "main-service",
                    "responsibility": "Core business logic",
                    "technology": "Unknown",
                }
            ]

    async def _extract_tech_choices(self, hld_document: str) -> dict:
        """Extract technology choices from HLD document."""
        extraction_prompt = f"""
From the following HLD, extract the technology choices as a JSON object.

HLD (first 3000 chars):
{hld_document[:3000]}

Return JSON like:
{{
  "database": "PostgreSQL",
  "cache": "Redis",
  "message_queue": "Kafka",
  "api_framework": "FastAPI",
  "language": "Python"
}}

Return ONLY the JSON object, no other text.
"""
        messages = [HumanMessage(content=extraction_prompt)]
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
            return {}

    def _build_tech_context(self, existing_docs: list) -> str:
        """Build technology context from existing documents."""
        all_techs = set()
        for doc in existing_docs:
            if hasattr(doc, "technologies"):
                all_techs.update(doc.technologies)

        if all_techs:
            return (
                f"Technologies currently used in the organization: "
                f"{', '.join(sorted(all_techs))}"
            )
        return "No existing technology context available."
