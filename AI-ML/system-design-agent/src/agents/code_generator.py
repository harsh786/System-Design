"""
Code Generator Agent

Generates production-ready code from LLD specifications.
Supports multiple languages and frameworks.
"""

import os
import json
from typing import Dict, List, Any
import structlog

from src.config.settings import Settings
from src.retrieval.vector_store import VectorStoreManager

logger = structlog.get_logger()


class CodeGeneratorAgent:
    """
    Generates production-ready code from design documents.
    """

    def __init__(self, vector_store: VectorStoreManager, settings: Settings):
        self.vector_store = vector_store
        self.settings = settings
        self.llm = self._init_llm()

    def _init_llm(self):
        """Initialize LLM client based on settings."""
        if self.settings.llm_provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=self.settings.openai_model,
                temperature=0.1,
                api_key=self.settings.openai_api_key,
            )
        elif self.settings.llm_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=self.settings.anthropic_model,
                temperature=0.1,
                api_key=self.settings.anthropic_api_key,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.settings.llm_provider}")

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution method for code generator agent.

        Args:
            state: Current agent state containing LLD documents

        Returns:
            Updated state with generated_code
        """
        logger.info("code_generator_started")

        try:
            lld_documents = state.get("lld_documents", {})
            tech_stack = state.get("tech_stack", {})
            db_design = state.get("db_design_document", "")
            security_requirements = state.get("security_requirements", "")

            if not lld_documents:
                logger.warning("no_lld_documents")
                return {
                    "generated_code": {},
                    "current_agent": "code_generator",
                    "error": "No LLD documents found for code generation",
                }

            generated_code = {}

            # Generate code for each component
            for component_name, lld_content in lld_documents.items():
                logger.info("generating_code_for_component", component=component_name)

                component_code = await self._generate_component_code(
                    component_name=component_name,
                    lld_content=lld_content,
                    tech_stack=tech_stack,
                    db_design=db_design,
                    security_requirements=security_requirements,
                )

                generated_code.update(component_code)

            # Generate common/shared code
            shared_code = await self._generate_shared_code(
                tech_stack=tech_stack,
                db_design=db_design,
                security_requirements=security_requirements,
            )
            generated_code.update(shared_code)

            logger.info(
                "code_generation_complete", files_generated=len(generated_code)
            )

            return {
                "generated_code": generated_code,
                "current_agent": "code_generator",
            }

        except Exception as e:
            logger.error("code_generation_failed", error=str(e))
            return {
                "error": f"Code generation failed: {str(e)}",
                "current_agent": "code_generator",
            }

    async def _generate_component_code(
        self,
        component_name: str,
        lld_content: str,
        tech_stack: Dict,
        db_design: str,
        security_requirements: str,
    ) -> Dict[str, str]:
        """
        Generate code for a specific component.
        """
        # Determine primary language and framework
        languages = tech_stack.get("languages", [])
        frameworks = tech_stack.get("frameworks", [])

        if "Python" in languages:
            return await self._generate_python_code(
                component_name, lld_content, frameworks, db_design, security_requirements
            )
        elif "JavaScript/TypeScript" in languages:
            return await self._generate_typescript_code(
                component_name, lld_content, frameworks, db_design, security_requirements
            )
        elif "Go" in languages:
            return await self._generate_go_code(
                component_name, lld_content, db_design, security_requirements
            )
        else:
            logger.warning("unsupported_language", languages=languages)
            return {}

    async def _generate_python_code(
        self,
        component_name: str,
        lld_content: str,
        frameworks: List[str],
        db_design: str,
        security_requirements: str,
    ) -> Dict[str, str]:
        """
        Generate Python code (FastAPI, Flask, etc.)
        """
        framework = "FastAPI" if "FastAPI" in frameworks else "Flask"

        # Retrieve similar code examples from vector store
        examples = self.vector_store.search(
            query=f"Python {framework} service implementation example",
            k=3,
        )

        prompt = f"""
Generate production-ready Python code for the following component using {framework}.

## Component: {component_name}

## Low-Level Design
{lld_content}

## Database Design
{db_design[:1000]}  # Include relevant portion

## Security Requirements
{security_requirements[:500]}

## Reference Examples
{self._format_examples(examples)}

## Requirements
1. Follow PEP 8 style guide
2. Include type hints
3. Add comprehensive docstrings (Google style)
4. Implement proper error handling
5. Add structured logging with context
6. Include OpenTelemetry instrumentation
7. Implement authentication/authorization checks
8. Add input validation
9. Follow the Single Responsibility Principle
10. Include dependency injection where appropriate

Generate the following files:
1. Main service file (e.g., order_service.py)
2. Data models (Pydantic models)
3. Database models (SQLAlchemy/equivalent)
4. Repository layer
5. Business logic layer
6. API routes
7. Dependencies (auth, db)
8. Configuration

Output format:
```filename: path/to/file.py
<code content>
```

Start generating:
"""

        try:
            response = await self.llm.ainvoke(prompt)
            code_files = self._parse_code_blocks(response.content)
            return code_files

        except Exception as e:
            logger.error("python_code_generation_failed", error=str(e))
            return {}

    async def _generate_typescript_code(
        self,
        component_name: str,
        lld_content: str,
        frameworks: List[str],
        db_design: str,
        security_requirements: str,
    ) -> Dict[str, str]:
        """
        Generate TypeScript code (NestJS, Express, Next.js, etc.)
        """
        framework = "NestJS" if "NestJS" in frameworks else "Express"

        examples = self.vector_store.search(
            query=f"TypeScript {framework} service implementation",
            k=3,
        )

        prompt = f"""
Generate production-ready TypeScript code for the following component using {framework}.

## Component: {component_name}

## Low-Level Design
{lld_content}

## Database Design
{db_design[:1000]}

## Security Requirements
{security_requirements[:500]}

## Reference Examples
{self._format_examples(examples)}

## Requirements
1. Use TypeScript strict mode
2. Follow ESLint/Prettier conventions
3. Use interfaces for all types
4. Add JSDoc comments
5. Implement proper error handling (try-catch, error middleware)
6. Add logging with Winston or Pino
7. Include OpenTelemetry tracing
8. Implement JWT authentication
9. Add input validation (class-validator or Zod)
10. Use dependency injection

Generate the following files:
1. Controller/Route handler
2. Service layer
3. Repository/Data access layer
4. DTOs (Data Transfer Objects)
5. Entities (TypeORM/Prisma models)
6. Middleware (auth, logging, error handling)
7. Types/Interfaces

Output format:
```filename: path/to/file.ts
<code content>
```

Start generating:
"""

        try:
            response = await self.llm.ainvoke(prompt)
            code_files = self._parse_code_blocks(response.content)
            return code_files

        except Exception as e:
            logger.error("typescript_code_generation_failed", error=str(e))
            return {}

    async def _generate_go_code(
        self,
        component_name: str,
        lld_content: str,
        db_design: str,
        security_requirements: str,
    ) -> Dict[str, str]:
        """
        Generate Go code (Gin, Echo, standard library, etc.)
        """
        examples = self.vector_store.search(
            query="Go microservice implementation example",
            k=3,
        )

        prompt = f"""
Generate production-ready Go code for the following component.

## Component: {component_name}

## Low-Level Design
{lld_content}

## Database Design
{db_design[:1000]}

## Security Requirements
{security_requirements[:500]}

## Reference Examples
{self._format_examples(examples)}

## Requirements
1. Follow Go best practices and idioms
2. Use Go modules
3. Add godoc comments
4. Implement proper error handling
5. Use structured logging (zap or logrus)
6. Include OpenTelemetry instrumentation
7. Implement JWT authentication
8. Add input validation
9. Use interfaces for dependency injection
10. Follow clean architecture principles

Generate the following files:
1. Main handler
2. Service layer
3. Repository layer
4. Models/Entities
5. DTOs
6. Middleware
7. Configuration

Output format:
```filename: path/to/file.go
<code content>
```

Start generating:
"""

        try:
            response = await self.llm.ainvoke(prompt)
            code_files = self._parse_code_blocks(response.content)
            return code_files

        except Exception as e:
            logger.error("go_code_generation_failed", error=str(e))
            return {}

    async def _generate_shared_code(
        self,
        tech_stack: Dict,
        db_design: str,
        security_requirements: str,
    ) -> Dict[str, str]:
        """
        Generate shared/common code (database connection, config, middleware, etc.)
        """
        languages = tech_stack.get("languages", [])
        shared_code = {}

        if "Python" in languages:
            shared_code.update(
                await self._generate_python_shared_code(tech_stack, db_design, security_requirements)
            )

        return shared_code

    async def _generate_python_shared_code(
        self, tech_stack: Dict, db_design: str, security_requirements: str
    ) -> Dict[str, str]:
        """
        Generate Python shared code (database, config, middleware, etc.)
        """
        prompt = f"""
Generate shared/common Python code for a microservice application.

## Technology Stack
{json.dumps(tech_stack, indent=2)}

## Database Design
{db_design[:1000]}

## Security Requirements
{security_requirements[:500]}

Generate the following shared modules:

1. **Database Connection** (database.py)
   - SQLAlchemy engine setup
   - Connection pooling
   - Session management
   - Health check

2. **Configuration** (config.py)
   - Pydantic Settings
   - Environment variable loading
   - Database URL, Redis URL, etc.

3. **Authentication** (auth.py)
   - JWT token creation/verification
   - Password hashing
   - OAuth2 password bearer

4. **Logging** (logging_config.py)
   - Structured logging with structlog
   - Context injection
   - Log formatting

5. **Middleware** (middleware.py)
   - Request ID injection
   - Logging middleware
   - Error handling middleware
   - CORS configuration

6. **Monitoring** (monitoring.py)
   - Prometheus metrics
   - OpenTelemetry setup
   - Health check endpoints

7. **Exceptions** (exceptions.py)
   - Custom exception classes
   - Exception handlers

Output format:
```filename: path/to/file.py
<code content>
```

Start generating:
"""

        try:
            response = await self.llm.ainvoke(prompt)
            code_files = self._parse_code_blocks(response.content)
            return code_files

        except Exception as e:
            logger.error("shared_code_generation_failed", error=str(e))
            return {}

    def _parse_code_blocks(self, content: str) -> Dict[str, str]:
        """
        Parse code blocks from LLM response.
        Expected format:
        ```filename: path/to/file.py
        <code>
        ```
        """
        code_files = {}
        lines = content.split("\n")
        current_file = None
        current_code = []

        for line in lines:
            # Check for filename marker
            if line.startswith("```filename:"):
                # Save previous file if exists
                if current_file and current_code:
                    code_files[current_file] = "\n".join(current_code)
                    current_code = []

                # Extract new filename
                current_file = line.split("```filename:")[1].strip()

            elif line.startswith("```") and current_file:
                # End of current code block
                if current_code:
                    code_files[current_file] = "\n".join(current_code)
                    current_code = []
                    current_file = None

            elif current_file:
                # Accumulate code lines
                current_code.append(line)

        # Handle last file
        if current_file and current_code:
            code_files[current_file] = "\n".join(current_code)

        return code_files

    def _format_examples(self, examples: List[Dict]) -> str:
        """Format code examples for prompt context."""
        formatted = []
        for i, example in enumerate(examples[:2], 1):  # Limit to 2 examples
            formatted.append(
                f"### Example {i}\n```\n{example.get('content', '')[:800]}\n```"
            )
        return "\n\n".join(formatted)
