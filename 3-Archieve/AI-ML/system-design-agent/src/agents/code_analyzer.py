"""
Code & Architecture Analyzer Agent

Analyzes existing codebase to extract:
- Architecture patterns
- Technology stack
- Code quality metrics
- Reusable components
- Integration points
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any
import structlog

from src.config.settings import Settings
from src.retrieval.vector_store import VectorStoreManager

logger = structlog.get_logger()


class CodeAnalyzerAgent:
    """
    Analyzes existing codebase and architecture to inform design decisions.
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
        Main execution method for code analyzer agent.

        Args:
            state: Current agent state containing repo_path

        Returns:
            Updated state with codebase_summary and current_architecture
        """
        logger.info("code_analyzer_started")

        try:
            repo_path = state.get("repo_path") or state.get("context_dir")
            if not repo_path:
                logger.warning("no_repo_path_provided")
                return {
                    "codebase_summary": {},
                    "current_architecture": {},
                    "tech_stack": {},
                    "reusable_components": [],
                }

            # Step 1: Scan directory structure
            directory_structure = self._scan_directory_structure(repo_path)

            # Step 2: Identify technology stack
            tech_stack = self._identify_tech_stack(repo_path, directory_structure)

            # Step 3: Analyze code files
            code_analysis = await self._analyze_code_files(repo_path, tech_stack)

            # Step 4: Extract architecture patterns
            architecture_summary = await self._extract_architecture_patterns(
                repo_path, code_analysis, tech_stack
            )

            # Step 5: Identify reusable components
            reusable_components = self._identify_reusable_components(
                code_analysis, architecture_summary
            )

            # Step 6: Generate comprehensive summary
            codebase_summary = {
                "languages": tech_stack.get("languages", []),
                "frameworks": tech_stack.get("frameworks", []),
                "dependencies": tech_stack.get("dependencies", {}),
                "file_count": len(code_analysis.get("files_analyzed", [])),
                "total_loc": code_analysis.get("total_lines_of_code", 0),
                "design_patterns": code_analysis.get("design_patterns", []),
                "code_quality_metrics": code_analysis.get("quality_metrics", {}),
            }

            logger.info(
                "code_analysis_complete",
                languages=len(tech_stack.get("languages", [])),
                files=len(code_analysis.get("files_analyzed", [])),
            )

            return {
                "codebase_summary": codebase_summary,
                "current_architecture": architecture_summary,
                "tech_stack": tech_stack,
                "reusable_components": reusable_components,
                "current_agent": "code_analyzer",
            }

        except Exception as e:
            logger.error("code_analyzer_failed", error=str(e))
            return {
                "error": f"Code analysis failed: {str(e)}",
                "current_agent": "code_analyzer",
            }

    def _scan_directory_structure(self, repo_path: str) -> Dict[str, Any]:
        """
        Scan directory structure to understand project layout.
        """
        structure = {
            "directories": [],
            "key_files": [],
            "total_files": 0,
        }

        ignore_dirs = {
            "node_modules",
            "__pycache__",
            ".git",
            "venv",
            "dist",
            "build",
            ".next",
            "target",
        }

        try:
            for root, dirs, files in os.walk(repo_path):
                # Filter out ignored directories
                dirs[:] = [d for d in dirs if d not in ignore_dirs]

                rel_root = os.path.relpath(root, repo_path)
                structure["directories"].append(rel_root)
                structure["total_files"] += len(files)

                # Identify key configuration files
                for file in files:
                    if file in [
                        "package.json",
                        "requirements.txt",
                        "Cargo.toml",
                        "go.mod",
                        "pom.xml",
                        "build.gradle",
                        "Dockerfile",
                        "docker-compose.yml",
                        "terraform.tf",
                    ]:
                        structure["key_files"].append(os.path.join(rel_root, file))

        except Exception as e:
            logger.warning("directory_scan_error", error=str(e))

        return structure

    def _identify_tech_stack(
        self, repo_path: str, directory_structure: Dict
    ) -> Dict[str, Any]:
        """
        Identify programming languages, frameworks, and dependencies.
        """
        tech_stack = {
            "languages": [],
            "frameworks": [],
            "dependencies": {},
            "infrastructure": [],
        }

        # Check for language-specific files
        key_files = directory_structure.get("key_files", [])

        # Python
        if any("requirements.txt" in f or "pyproject.toml" in f for f in key_files):
            tech_stack["languages"].append("Python")
            tech_stack["dependencies"]["python"] = self._parse_python_deps(repo_path)
            tech_stack["frameworks"].extend(
                self._identify_python_frameworks(tech_stack["dependencies"]["python"])
            )

        # JavaScript/TypeScript
        if any("package.json" in f for f in key_files):
            tech_stack["languages"].append("JavaScript/TypeScript")
            tech_stack["dependencies"]["javascript"] = self._parse_js_deps(repo_path)
            tech_stack["frameworks"].extend(
                self._identify_js_frameworks(tech_stack["dependencies"]["javascript"])
            )

        # Go
        if any("go.mod" in f for f in key_files):
            tech_stack["languages"].append("Go")

        # Rust
        if any("Cargo.toml" in f for f in key_files):
            tech_stack["languages"].append("Rust")

        # Java
        if any("pom.xml" in f or "build.gradle" in f for f in key_files):
            tech_stack["languages"].append("Java")

        # Infrastructure
        if any("Dockerfile" in f for f in key_files):
            tech_stack["infrastructure"].append("Docker")
        if any("docker-compose" in f for f in key_files):
            tech_stack["infrastructure"].append("Docker Compose")
        if any("terraform" in f.lower() for f in key_files):
            tech_stack["infrastructure"].append("Terraform")

        return tech_stack

    def _parse_python_deps(self, repo_path: str) -> List[str]:
        """Parse Python dependencies from requirements.txt or pyproject.toml."""
        deps = []
        
        # Check requirements.txt
        req_file = Path(repo_path) / "requirements.txt"
        if req_file.exists():
            try:
                content = req_file.read_text()
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Extract package name (before ==, >=, etc.)
                        pkg = line.split("==")[0].split(">=")[0].split("~=")[0].strip()
                        deps.append(pkg)
            except Exception as e:
                logger.warning("requirements_parse_error", error=str(e))

        return deps

    def _parse_js_deps(self, repo_path: str) -> Dict[str, str]:
        """Parse JavaScript dependencies from package.json."""
        deps = {}
        
        pkg_file = Path(repo_path) / "package.json"
        if pkg_file.exists():
            try:
                import json
                pkg_data = json.loads(pkg_file.read_text())
                deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
            except Exception as e:
                logger.warning("package_json_parse_error", error=str(e))

        return deps

    def _identify_python_frameworks(self, deps: List[str]) -> List[str]:
        """Identify Python frameworks from dependencies."""
        frameworks = []
        framework_map = {
            "fastapi": "FastAPI",
            "flask": "Flask",
            "django": "Django",
            "tornado": "Tornado",
            "aiohttp": "aiohttp",
            "sanic": "Sanic",
        }

        for dep in deps:
            dep_lower = dep.lower()
            for key, name in framework_map.items():
                if key in dep_lower:
                    frameworks.append(name)

        return frameworks

    def _identify_js_frameworks(self, deps: Dict[str, str]) -> List[str]:
        """Identify JavaScript/TypeScript frameworks from dependencies."""
        frameworks = []
        framework_map = {
            "react": "React",
            "next": "Next.js",
            "vue": "Vue.js",
            "nuxt": "Nuxt.js",
            "angular": "Angular",
            "express": "Express",
            "nestjs": "NestJS",
            "fastify": "Fastify",
        }

        for dep_name in deps.keys():
            dep_lower = dep_name.lower()
            for key, name in framework_map.items():
                if key in dep_lower:
                    frameworks.append(name)

        return frameworks

    async def _analyze_code_files(
        self, repo_path: str, tech_stack: Dict
    ) -> Dict[str, Any]:
        """
        Analyze actual code files to extract patterns and quality metrics.
        """
        analysis = {
            "files_analyzed": [],
            "total_lines_of_code": 0,
            "design_patterns": [],
            "quality_metrics": {
                "average_file_size": 0,
                "test_coverage_estimate": "unknown",
            },
        }

        # Sample files for analysis (don't analyze everything to save time/tokens)
        sample_files = self._get_sample_files(repo_path, tech_stack["languages"])

        for file_path in sample_files[:20]:  # Limit to 20 files
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    lines = len(content.split("\n"))
                    analysis["total_lines_of_code"] += lines
                    analysis["files_analyzed"].append(file_path)

                    # Basic pattern detection
                    patterns = self._detect_patterns(content)
                    analysis["design_patterns"].extend(patterns)

            except Exception as e:
                logger.debug("file_analysis_error", file=file_path, error=str(e))

        # Remove duplicates from design patterns
        analysis["design_patterns"] = list(set(analysis["design_patterns"]))

        if analysis["files_analyzed"]:
            analysis["quality_metrics"]["average_file_size"] = (
                analysis["total_lines_of_code"] / len(analysis["files_analyzed"])
            )

        return analysis

    def _get_sample_files(self, repo_path: str, languages: List[str]) -> List[str]:
        """
        Get a representative sample of code files.
        """
        extensions = []
        if "Python" in languages:
            extensions.extend([".py"])
        if "JavaScript/TypeScript" in languages:
            extensions.extend([".js", ".ts", ".jsx", ".tsx"])
        if "Go" in languages:
            extensions.extend([".go"])
        if "Rust" in languages:
            extensions.extend([".rs"])
        if "Java" in languages:
            extensions.extend([".java"])

        files = []
        ignore_dirs = {"node_modules", "__pycache__", ".git", "venv", "dist", "build"}

        for root, dirs, filenames in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for filename in filenames:
                if any(filename.endswith(ext) for ext in extensions):
                    files.append(os.path.join(root, filename))

        return files

    def _detect_patterns(self, code_content: str) -> List[str]:
        """
        Detect common design patterns in code.
        """
        patterns = []

        # Simple keyword-based detection
        pattern_keywords = {
            "Factory": ["Factory", "create_", "builder"],
            "Singleton": ["Singleton", "_instance", "get_instance"],
            "Repository": ["Repository", "repo"],
            "Service": ["Service", "service"],
            "Strategy": ["Strategy", "algorithm"],
            "Observer": ["Observer", "subscribe", "notify"],
            "Adapter": ["Adapter", "adapt"],
            "Decorator": ["@decorator", "wrapper"],
        }

        for pattern, keywords in pattern_keywords.items():
            if any(keyword in code_content for keyword in keywords):
                patterns.append(pattern)

        return patterns

    async def _extract_architecture_patterns(
        self, repo_path: str, code_analysis: Dict, tech_stack: Dict
    ) -> Dict[str, Any]:
        """
        Use LLM to extract high-level architecture patterns from code analysis.
        """
        # Retrieve relevant existing architecture docs from vector store
        existing_docs = self.vector_store.search(
            query="architecture pattern microservices API design",
            k=5,
        )

        context = f"""
Analyze the codebase and identify the architecture pattern.

## Technology Stack
{json.dumps(tech_stack, indent=2)}

## Code Analysis
- Files analyzed: {len(code_analysis.get('files_analyzed', []))}
- Total LOC: {code_analysis.get('total_lines_of_code', 0)}
- Design patterns found: {', '.join(code_analysis.get('design_patterns', []))}

## Existing Architecture Documentation
{self._format_docs(existing_docs)}

Based on this information, identify:
1. Overall architecture pattern (Monolithic, Microservices, Serverless, etc.)
2. Communication patterns (REST, gRPC, Event-driven, etc.)
3. Data storage patterns (RDBMS, NoSQL, Cache, etc.)
4. Key components and their responsibilities
5. Integration points with external systems

Provide response in JSON format:
{{
    "pattern": "...",
    "communication": [...],
    "data_stores": [...],
    "components": [
        {{"name": "...", "responsibility": "...", "technology": "..."}}
    ],
    "integrations": [...]
}}
"""

        try:
            response = await self.llm.ainvoke(context)
            content = response.content
            
            # Try to extract JSON from response
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            architecture = json.loads(json_str)
            return architecture

        except Exception as e:
            logger.error("architecture_extraction_failed", error=str(e))
            return {
                "pattern": "Unknown",
                "communication": [],
                "data_stores": [],
                "components": [],
                "integrations": [],
            }

    def _identify_reusable_components(
        self, code_analysis: Dict, architecture: Dict
    ) -> List[Dict[str, Any]]:
        """
        Identify reusable components that can be leveraged for new features.
        """
        reusable = []

        # Extract components from architecture
        for component in architecture.get("components", []):
            if any(
                keyword in component.get("name", "").lower()
                for keyword in ["common", "shared", "util", "helper", "lib"]
            ):
                reusable.append(
                    {
                        "name": component.get("name"),
                        "type": "component",
                        "responsibility": component.get("responsibility"),
                        "reusability": "high",
                    }
                )

        # Add design patterns as reusable concepts
        for pattern in code_analysis.get("design_patterns", []):
            reusable.append(
                {
                    "name": pattern,
                    "type": "pattern",
                    "responsibility": f"Implements {pattern} pattern",
                    "reusability": "pattern",
                }
            )

        return reusable

    def _format_docs(self, docs: List[Dict]) -> str:
        """Format retrieved documents for prompt context."""
        formatted = []
        for doc in docs:
            formatted.append(f"### {doc.get('source', 'Unknown')}\n{doc.get('content', '')[:500]}")
        return "\n\n".join(formatted)
