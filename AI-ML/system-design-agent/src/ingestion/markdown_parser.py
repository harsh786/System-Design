"""
Markdown Parser - Reads and parses existing design documents from the workspace.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedDocument:
    """Represents a parsed design document."""
    title: str
    content: str
    file_path: str
    doc_type: str  # "hld" | "lld" | "db_design" | "architecture" | "other"
    sections: list[dict]  # [{heading, level, content}]
    technologies: list[str]  # Extracted tech mentions
    components: list[str]  # Extracted component names
    metadata: dict = field(default_factory=dict)


# Known technology keywords for extraction
TECH_KEYWORDS = {
    "kafka", "redis", "postgres", "postgresql", "mysql", "mongodb",
    "elasticsearch", "opensearch", "clickhouse", "pinot", "flink",
    "spark", "airflow", "kubernetes", "k8s", "docker", "aws",
    "gcp", "azure", "s3", "sqs", "sns", "kinesis", "dynamodb",
    "cassandra", "scylladb", "aerospike", "rabbitmq", "grpc",
    "graphql", "rest", "http", "websocket", "mqtt", "nginx",
    "envoy", "istio", "prometheus", "grafana", "datadog",
    "terraform", "pulumi", "cloudformation", "iceberg",
    "redshift", "athena", "bigquery", "snowflake", "dbt",
    "timescaledb", "victoriametrics", "influxdb", "mermaid",
    "java", "python", "go", "golang", "rust", "typescript",
    "node", "nodejs", "react", "nextjs", "fastapi", "spring",
}


class MarkdownParser:
    """
    Parses markdown design documents from the filesystem.
    Extracts structure, technologies, and components.
    """

    def parse_directory(
        self,
        directory: str,
        extensions: tuple[str, ...] = (".md", ".markdown"),
        recursive: bool = True,
    ) -> list[ParsedDocument]:
        """
        Parse all markdown files in a directory.

        Args:
            directory: Root directory to scan
            extensions: File extensions to include
            recursive: Whether to scan subdirectories

        Returns:
            List of parsed documents
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        pattern = "**/*" if recursive else "*"
        documents = []

        for file_path in dir_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                # Skip hidden dirs, venvs, node_modules, etc.
                path_str = str(file_path)
                if any(
                    skip in path_str
                    for skip in (
                        "/.venv/", "/venv/", "/node_modules/",
                        "/.git/", "/__pycache__/", "/.chromadb/",
                    )
                ):
                    continue
                try:
                    doc = self.parse_file(str(file_path))
                    documents.append(doc)
                except Exception as e:
                    print(f"Warning: Failed to parse {file_path}: {e}")

        return documents

    def parse_file(self, file_path: str) -> ParsedDocument:
        """
        Parse a single markdown file.

        Args:
            file_path: Path to the markdown file

        Returns:
            ParsedDocument with extracted information
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")

        # Extract title (first H1 or filename)
        title = self._extract_title(content, path)

        # Parse sections
        sections = self._parse_sections(content)

        # Detect document type
        doc_type = self._detect_doc_type(content, file_path)

        # Extract technology mentions
        technologies = self._extract_technologies(content)

        # Extract component names
        components = self._extract_components(content)

        # Build metadata
        metadata = {
            "file_name": path.name,
            "parent_dir": path.parent.name,
            "file_size": path.stat().st_size,
            "num_sections": len(sections),
            "has_diagrams": self._has_diagrams(content),
            "has_code_blocks": "```" in content,
        }

        return ParsedDocument(
            title=title,
            content=content,
            file_path=str(path.absolute()),
            doc_type=doc_type,
            sections=sections,
            technologies=technologies,
            components=components,
            metadata=metadata,
        )

    def _extract_title(self, content: str, path: Path) -> str:
        """Extract document title from first H1 heading or filename."""
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        # Fall back to filename
        return path.stem.replace("_", " ").replace("-", " ").title()

    def _parse_sections(self, content: str) -> list[dict]:
        """Parse markdown into sections based on headings."""
        sections = []
        lines = content.split("\n")
        current_section = None

        for line in lines:
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                if current_section:
                    sections.append(current_section)
                current_section = {
                    "heading": heading_match.group(2).strip(),
                    "level": len(heading_match.group(1)),
                    "content": "",
                }
            elif current_section:
                current_section["content"] += line + "\n"

        if current_section:
            sections.append(current_section)

        return sections

    def _detect_doc_type(self, content: str, file_path: str) -> str:
        """Detect the type of design document."""
        content_lower = content.lower()
        path_lower = file_path.lower()

        # Check path-based hints
        if "/hld/" in path_lower or "hld" in Path(file_path).stem.lower():
            return "hld"
        if "/lld/" in path_lower or "lld" in Path(file_path).stem.lower():
            return "lld"

        # Check content-based hints
        hld_signals = [
            "high-level design", "high level design",
            "system architecture", "component diagram",
            "technology choices", "scalability",
        ]
        lld_signals = [
            "low-level design", "low level design",
            "class diagram", "sequence diagram",
            "api contract", "error handling",
        ]
        db_signals = [
            "database design", "schema design",
            "er diagram", "entity relationship",
            "create table", "index strategy",
            "partitioning", "ddl",
        ]
        arch_signals = [
            "architecture", "deep dive",
            "internals", "how .* works",
        ]

        scores = {
            "hld": sum(1 for s in hld_signals if s in content_lower),
            "lld": sum(1 for s in lld_signals if s in content_lower),
            "db_design": sum(1 for s in db_signals if s in content_lower),
            "architecture": sum(
                1 for s in arch_signals
                if re.search(s, content_lower)
            ),
        }

        max_type = max(scores, key=scores.get)
        return max_type if scores[max_type] > 0 else "other"

    def _extract_technologies(self, content: str) -> list[str]:
        """Extract technology mentions from content."""
        content_lower = content.lower()
        found = []
        for tech in TECH_KEYWORDS:
            # Use word boundary matching
            if re.search(rf"\b{re.escape(tech)}\b", content_lower):
                found.append(tech)
        return sorted(set(found))

    def _extract_components(self, content: str) -> list[str]:
        """Extract component/service names from content."""
        components = set()

        # Pattern: "Service Name" or "Component Name"
        patterns = [
            r"(\w+[\s-]?service)\b",
            r"(\w+[\s-]?component)\b",
            r"(\w+[\s-]?module)\b",
            r"(\w+[\s-]?layer)\b",
            r"(\w+[\s-]?gateway)\b",
            r"(\w+[\s-]?controller)\b",
            r"(\w+[\s-]?handler)\b",
            r"(\w+[\s-]?worker)\b",
            r"(\w+[\s-]?processor)\b",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            components.update(m.strip() for m in matches)

        return sorted(components)

    def _has_diagrams(self, content: str) -> bool:
        """Check if content contains diagram definitions."""
        diagram_markers = [
            "```mermaid", "```plantuml", "```dot",
            "flowchart", "sequenceDiagram", "classDiagram",
            "erDiagram", "graph TD", "graph LR",
        ]
        return any(marker in content for marker in diagram_markers)
