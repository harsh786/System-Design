"""
PRD Analyzer Agent - Extracts structured requirements from PRD documents.
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage

from src.config.settings import Settings
from src.config.prompts import PRD_ANALYZER_SYSTEM_PROMPT, PRD_ANALYZER_USER_PROMPT
from src.retrieval.vector_store import VectorStoreManager


class PRDAnalyzerAgent:
    """
    Analyzes PRD documents and extracts structured requirements.

    This agent:
    1. Retrieves existing system context from the vector store
    2. Sends the PRD + context to the LLM
    3. Extracts structured requirements (functional, NFR, data entities, etc.)
    4. Validates completeness of requirements
    """

    def __init__(self, vector_store: VectorStoreManager, settings: Settings):
        self.vector_store = vector_store
        self.settings = settings
        self.llm = settings.create_llm(max_tokens=4096)

    async def run(self, state) -> dict:
        """
        Execute the PRD analysis.

        Args:
            state: DesignAgentState with prd_content populated

        Returns:
            Dict with extracted requirements and validation status
        """
        try:
            # Step 1: Retrieve existing context
            prd_content = state.get("prd_content", "")
            existing_context = await self.vector_store.retrieve(
                query=prd_content[:500],  # Use first 500 chars as query
                top_k=10,
            )
            context_str = self.vector_store._format_results(existing_context)

            # Step 2: Build prompt
            user_prompt = PRD_ANALYZER_USER_PROMPT.format(
                existing_context=context_str,
                prd_content=prd_content,
            )

            # Step 3: Call LLM
            messages = [
                SystemMessage(content=PRD_ANALYZER_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
            response = await self.llm.ainvoke(messages)

            # Step 4: Parse response
            requirements = self._parse_requirements(response.content)

            # Step 5: Validate completeness
            is_valid, questions = self._validate_requirements(requirements)

            return {
                "requirements_json": json.dumps(requirements, indent=2),
                "project_name": requirements.get("project_name", "Unknown"),
                "data_entities": requirements.get("data_entities", []),
                "integrations": requirements.get("integrations", []),
                "nfr": requirements.get("non_functional_requirements", {}),
                "requirements_valid": is_valid,
                "clarification_questions": questions,
                "current_agent": "prd_analyzer",
            }

        except Exception as e:
            return {
                "error": f"PRD Analyzer failed: {str(e)}",
                "requirements_valid": False,
                "current_agent": "prd_analyzer",
            }

    def _parse_requirements(self, llm_response: str) -> dict:
        """Parse the LLM response to extract structured requirements."""
        # Try to extract JSON from the response
        try:
            # Look for JSON block in markdown code fence
            if "```json" in llm_response:
                json_str = llm_response.split("```json")[1].split("```")[0]
            elif "```" in llm_response:
                json_str = llm_response.split("```")[1].split("```")[0]
            else:
                json_str = llm_response

            return json.loads(json_str.strip())
        except (json.JSONDecodeError, IndexError):
            # Fallback: return raw text wrapped in a structure
            return {
                "project_name": "Unknown",
                "summary": llm_response[:500],
                "functional_requirements": [],
                "non_functional_requirements": {},
                "data_entities": [],
                "integrations": [],
                "user_flows": [],
                "constraints": [],
                "assumptions": [],
                "raw_analysis": llm_response,
            }

    def _validate_requirements(
        self, requirements: dict
    ) -> tuple[bool, list[str]]:
        """
        Validate that extracted requirements are sufficient for design.

        Returns:
            Tuple of (is_valid, list_of_clarification_questions)
        """
        questions = []

        # Check for minimum required fields
        if not requirements.get("functional_requirements"):
            questions.append(
                "No functional requirements could be extracted. "
                "Please provide a PRD with clear feature descriptions."
            )

        nfr = requirements.get("non_functional_requirements", {})
        if not nfr.get("expected_qps"):
            questions.append(
                "What is the expected QPS/TPS for read and write operations?"
            )
        if not nfr.get("latency"):
            questions.append(
                "What are the latency requirements (p50, p95, p99)?"
            )
        if not nfr.get("availability_target"):
            questions.append(
                "What is the availability target (e.g., 99.9%, 99.99%)?"
            )

        if not requirements.get("data_entities"):
            questions.append(
                "No data entities could be identified. "
                "Please describe the main data objects in the system."
            )

        # Valid if we have at least functional requirements and data entities
        is_valid = (
            bool(requirements.get("functional_requirements"))
            and bool(requirements.get("data_entities"))
        )

        return is_valid, questions
