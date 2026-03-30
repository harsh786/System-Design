"""
LLD Generator Agent - Generates Low-Level Design documents for each component.
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage

from src.config.settings import Settings
from src.config.prompts import LLD_GENERATOR_SYSTEM_PROMPT, LLD_GENERATOR_USER_PROMPT
from src.retrieval.vector_store import VectorStoreManager


class LLDGeneratorAgent:
    """
    Generates detailed Low-Level Design documents for each component.

    This agent:
    1. Iterates through components identified in HLD
    2. Retrieves existing LLD context for each component
    3. Generates detailed LLD with class/sequence diagrams
    4. Extracts API contracts and query patterns for DB design
    """

    def __init__(self, vector_store: VectorStoreManager, settings: Settings):
        self.vector_store = vector_store
        self.settings = settings
        self.llm = settings.create_llm(max_tokens=6000)

    async def run(self, state) -> dict:
        """
        Generate LLD documents for all components.

        Args:
            state: DesignAgentState with HLD and components populated

        Returns:
            Dict with LLD documents, API contracts, and query patterns
        """
        try:
            lld_documents = {}
            all_api_contracts = {}
            all_query_patterns = []

            for component in state.get("components", []):
                comp_name = component.get("name", "unknown")
                comp_responsibility = component.get("responsibility", "")

                print(f"    📐 Generating LLD for: {comp_name}")

                # Generate LLD for this component
                lld_doc = await self._generate_component_lld(
                    state=state,
                    component_name=comp_name,
                    component_responsibility=comp_responsibility,
                )

                lld_documents[comp_name] = lld_doc

                # Extract API contracts
                api_contract = await self._extract_api_contracts(lld_doc, comp_name)
                if api_contract:
                    all_api_contracts[comp_name] = api_contract

                # Extract query patterns
                patterns = await self._extract_query_patterns(lld_doc)
                all_query_patterns.extend(patterns)

            return {
                "lld_documents": lld_documents,
                "api_contracts": all_api_contracts,
                "query_patterns": all_query_patterns,
                "current_agent": "lld_generator",
            }

        except Exception as e:
            return {
                "error": f"LLD Generator failed: {str(e)}",
                "lld_documents": {},
                "current_agent": "lld_generator",
            }

    async def _generate_component_lld(
        self,
        state,
        component_name: str,
        component_responsibility: str,
    ) -> str:
        """Generate LLD for a single component."""

        # Retrieve relevant existing LLD context
        lld_context = await self.vector_store.retrieve_for_lld(
            query=f"low level design for {component_name} {component_responsibility}"
        )

        # Filter requirements relevant to this component
        component_requirements = await self._get_component_requirements(
            state.get("requirements_json", ""), component_name
        )

        # Build prompt
        hld_doc = state.get("hld_document", "")
        user_prompt = LLD_GENERATOR_USER_PROMPT.format(
            hld_document=hld_doc[:3000],  # Truncate for context window
            component_name=component_name,
            component_responsibility=component_responsibility,
            existing_lld_context=lld_context,
            component_requirements=component_requirements,
        )

        messages = [
            SystemMessage(content=LLD_GENERATOR_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        # Add review feedback if this is a revision
        if state.get("review_iteration", 0) > 0 and state.get("review_issues"):
            lld_issues = [
                issue for issue in state.get("review_issues", [])
                if issue.get("document") == "LLD"
                and (
                    issue.get("component") == component_name
                    or not issue.get("component")
                )
            ]
            if lld_issues:
                feedback = f"## Review Feedback for {component_name}:\n"
                for issue in lld_issues:
                    feedback += (
                        f"- [{issue['severity']}] {issue['description']}\n"
                    )
                messages.append(HumanMessage(content=feedback))

        response = await self.llm.ainvoke(messages)
        return response.content

    async def _get_component_requirements(
        self, requirements_json: str, component_name: str
    ) -> str:
        """Filter requirements relevant to a specific component."""
        prompt = f"""
Given these system requirements:
{requirements_json[:3000]}

Which requirements are relevant to the "{component_name}" component?
List only the relevant functional requirements and their acceptance criteria.
Be concise.
"""
        messages = [HumanMessage(content=prompt)]
        response = await self.llm.ainvoke(messages)
        return response.content

    async def _extract_api_contracts(
        self, lld_document: str, component_name: str
    ) -> dict | None:
        """Extract API contracts from LLD document."""
        prompt = f"""
From this LLD document for {component_name}, extract the API endpoints as JSON:

{lld_document[:4000]}

Return JSON:
{{
  "endpoints": [
    {{
      "method": "GET|POST|PUT|DELETE",
      "path": "/api/v1/...",
      "description": "brief description",
      "request_body": "brief schema description or null",
      "response_body": "brief schema description"
    }}
  ]
}}

Return ONLY the JSON, no other text. If no APIs found, return {{"endpoints": []}}.
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
            result = json.loads(json_str.strip())
            return result if result.get("endpoints") else None
        except (json.JSONDecodeError, IndexError):
            return None

    async def _extract_query_patterns(self, lld_document: str) -> list[str]:
        """Extract database query patterns from LLD document."""
        prompt = f"""
From this LLD document, extract all database query patterns mentioned 
(e.g., "get user by ID", "list orders by user sorted by date", etc.)

{lld_document[:3000]}

Return a JSON array of query pattern strings:
["query pattern 1", "query pattern 2", ...]

Return ONLY the JSON array. If none found, return [].
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
