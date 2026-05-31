"""
DB Design Generator Agent - Generates database design documents.
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage

from src.config.settings import Settings
from src.config.prompts import (
    DB_DESIGN_GENERATOR_SYSTEM_PROMPT,
    DB_DESIGN_GENERATOR_USER_PROMPT,
)
from src.retrieval.vector_store import VectorStoreManager


class DBDesignGeneratorAgent:
    """
    Generates comprehensive database design documents.

    This agent:
    1. Takes data entities from PRD + query patterns from LLD
    2. Retrieves existing DB design context
    3. Generates schema, indexes, partitioning, capacity planning
    4. Outputs DDL scripts
    """

    def __init__(self, vector_store: VectorStoreManager, settings: Settings):
        self.vector_store = vector_store
        self.settings = settings
        self.llm = settings.create_llm(max_tokens=8000)

    async def run(self, state) -> dict:
        """
        Generate the Database Design document.

        Args:
            state: DesignAgentState with entities, query patterns, and tech choices

        Returns:
            Dict with DB design document and DDL scripts
        """
        try:
            # Step 1: Retrieve existing DB design context
            project_name = state.get("project_name", "Unknown")
            db_technology = state.get("db_technology", "PostgreSQL")
            db_context = await self.vector_store.retrieve_for_db_design(
                query=(
                    f"database design schema for {project_name} "
                    f"{db_technology}"
                )
            )

            # Step 2: Collect existing schemas from workspace
            existing_schemas = self._collect_existing_schemas(state.get("existing_docs", []))

            # Step 3: Format query patterns
            query_patterns = state.get("query_patterns", [])
            query_patterns_str = "\n".join(
                f"- {pattern}" for pattern in query_patterns
            ) if query_patterns else "No specific query patterns extracted yet."

            # Step 4: Format scale requirements
            nfr = state.get("nfr") or {}
            scale_requirements = json.dumps(nfr, indent=2) if nfr else "Not specified"

            # Step 5: Format data entities
            data_entities_list = state.get("data_entities", [])
            data_entities = json.dumps(
                data_entities_list, indent=2
            ) if data_entities_list else "See requirements JSON"

            # Step 6: Build prompt
            user_prompt = DB_DESIGN_GENERATOR_USER_PROMPT.format(
                data_entities=data_entities,
                query_patterns=query_patterns_str,
                scale_requirements=scale_requirements,
                existing_schemas=existing_schemas or db_context,
                db_technology=db_technology or "PostgreSQL",
            )

            messages = [
                SystemMessage(content=DB_DESIGN_GENERATOR_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]

            # Add review feedback if this is a revision
            if state.get("review_iteration", 0) > 0 and state.get("review_issues"):
                db_issues = [
                    issue for issue in state.get("review_issues", [])
                    if issue.get("document") == "DB_DESIGN"
                ]
                if db_issues:
                    feedback = "## Review Feedback for DB Design:\n"
                    for issue in db_issues:
                        feedback += (
                            f"- [{issue['severity']}] {issue['description']}\n"
                            f"  Recommendation: {issue.get('recommendation', 'N/A')}\n"
                        )
                    messages.append(HumanMessage(content=feedback))

            response = await self.llm.ainvoke(messages)
            db_design_document = response.content

            # Step 7: Extract DDL scripts
            ddl_scripts = self._extract_ddl(db_design_document)

            return {
                "db_design_document": db_design_document,
                "ddl_scripts": ddl_scripts,
                "current_agent": "db_design_generator",
            }

        except Exception as e:
            return {
                "error": f"DB Design Generator failed: {str(e)}",
                "db_design_document": "",
                "current_agent": "db_design_generator",
            }

    def _collect_existing_schemas(self, existing_docs: list) -> str:
        """Extract existing schema information from workspace documents."""
        schema_parts = []
        for doc in existing_docs:
            if not hasattr(doc, "doc_type"):
                continue
            if doc.doc_type == "db_design":
                schema_parts.append(
                    f"--- Existing Schema: {doc.title} ---\n{doc.content[:2000]}"
                )
            elif hasattr(doc, "content"):
                # Look for CREATE TABLE or schema sections
                content = doc.content
                if "CREATE TABLE" in content.upper() or "schema" in content.lower():
                    schema_parts.append(
                        f"--- Schema from: {doc.title} ---\n{content[:1000]}"
                    )

        return "\n\n".join(schema_parts) if schema_parts else ""

    def _extract_ddl(self, db_design_document: str) -> str:
        """Extract DDL scripts from the generated DB design document."""
        ddl_parts = []
        in_sql_block = False
        current_block = []

        for line in db_design_document.split("\n"):
            if line.strip().startswith("```sql"):
                in_sql_block = True
                current_block = []
            elif line.strip() == "```" and in_sql_block:
                in_sql_block = False
                if current_block:
                    ddl_parts.append("\n".join(current_block))
            elif in_sql_block:
                current_block.append(line)

        return "\n\n".join(ddl_parts) if ddl_parts else ""
