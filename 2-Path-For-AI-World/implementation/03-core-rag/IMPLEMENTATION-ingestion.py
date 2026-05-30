"""
RAG Ingestion Pipeline — Production-Grade Document Processing

This module handles the complete ingestion lifecycle:
- Multi-format parsing (PDF, HTML, Markdown, plain text)
- Table extraction
- Metadata extraction and enrichment
- Document deduplication
- Boilerplate removal
- Document versioning
- Deletion propagation
- Batch processing with comprehensive error handling

Dependencies:
    pip install pypdf2 unstructured beautifulsoup4 hashlib tiktoken
    pip install python-dateutil pydantic tenacity
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Optional, Protocol

from pydantic import BaseModel, Field

# ─── Logging ───────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# ─── Domain Models ─────────────────────────────────────────────────────────────


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class DocumentSource(str, Enum):
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    DOCX = "docx"


class DocumentMetadata(BaseModel):
    """Rich metadata extracted from and attached to each document."""
    source_id: str = Field(description="Unique identifier for the source document")
    source_type: DocumentSource
    title: str = ""
    author: str = ""
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    content_hash: str = ""
    word_count: int = 0
    page_count: int = 0
    language: str = "en"
    tags: list[str] = Field(default_factory=list)
    access_control: list[str] = Field(default_factory=list, description="ACL groups that can access this doc")
    custom_metadata: dict[str, Any] = Field(default_factory=dict)


class IngestedDocument(BaseModel):
    """A fully processed document ready for chunking."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    tables: list[str] = Field(default_factory=list, description="Extracted tables as markdown")
    metadata: DocumentMetadata
    status: DocumentStatus = DocumentStatus.PENDING


class IngestionResult(BaseModel):
    """Result of processing a single document."""
    document_id: str
    source_path: str
    status: DocumentStatus
    error: Optional[str] = None
    processing_time_ms: float = 0
    is_duplicate: bool = False
    version: int = 1


class BatchIngestionResult(BaseModel):
    """Aggregated results for a batch ingestion run."""
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    duplicates_skipped: int = 0
    results: list[IngestionResult] = Field(default_factory=list)
    total_time_ms: float = 0


# ─── Parser Protocol ───────────────────────────────────────────────────────────


class DocumentParser(Protocol):
    """Protocol for document parsers."""
    def parse(self, file_path: Path) -> IngestedDocument: ...
    def supports(self, file_path: Path) -> bool: ...


# ─── PDF Parser ────────────────────────────────────────────────────────────────


class PDFParser:
    """
    PDF parsing with fallback strategy:
    1. Try PyPDF2 for simple text extraction
    2. Fall back to unstructured for complex layouts
    """

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def parse(self, file_path: Path) -> IngestedDocument:
        logger.info(f"Parsing PDF: {file_path}")
        try:
            content, page_count = self._parse_with_pypdf2(file_path)
            if self._is_low_quality(content, page_count):
                logger.info("PyPDF2 extraction low quality, falling back to unstructured")
                content, tables = self._parse_with_unstructured(file_path)
            else:
                tables = []
        except Exception as e:
            logger.warning(f"PyPDF2 failed: {e}, trying unstructured")
            content, tables = self._parse_with_unstructured(file_path)
            page_count = 0

        metadata = DocumentMetadata(
            source_id=str(file_path),
            source_type=DocumentSource.PDF,
            title=file_path.stem,
            page_count=page_count,
            word_count=len(content.split()),
            content_hash=self._compute_hash(content),
        )

        return IngestedDocument(content=content, tables=tables, metadata=metadata)

    def _parse_with_pypdf2(self, file_path: Path) -> tuple[str, int]:
        from PyPDF2 import PdfReader

        reader = PdfReader(str(file_path))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append(f"[Page {i + 1}]\n{text}")

        return "\n\n".join(pages), len(reader.pages)

    def _parse_with_unstructured(self, file_path: Path) -> tuple[str, list[str]]:
        from unstructured.partition.pdf import partition_pdf

        elements = partition_pdf(str(file_path), strategy="hi_res")
        text_parts = []
        tables = []

        for element in elements:
            if element.category == "Table":
                tables.append(str(element))
            else:
                text_parts.append(str(element))

        return "\n\n".join(text_parts), tables

    def _is_low_quality(self, content: str, page_count: int) -> bool:
        """Heuristic: if extracted text is too short relative to page count, quality is low."""
        if page_count == 0:
            return True
        avg_chars_per_page = len(content) / max(page_count, 1)
        return avg_chars_per_page < 100  # Less than 100 chars/page suggests extraction failure

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()


# ─── HTML Parser ───────────────────────────────────────────────────────────────


class HTMLParser:
    """Parse HTML documents with boilerplate removal."""

    # Common boilerplate selectors to remove
    BOILERPLATE_SELECTORS = [
        "nav", "header", "footer", "aside",
        ".sidebar", ".navigation", ".menu", ".cookie-banner",
        ".advertisement", ".ad", "#comments", ".social-share",
        "script", "style", "noscript",
    ]

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in (".html", ".htm")

    def parse(self, file_path: Path) -> IngestedDocument:
        from bs4 import BeautifulSoup

        logger.info(f"Parsing HTML: {file_path}")
        raw_html = file_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw_html, "html.parser")

        # Extract metadata before removing elements
        title = self._extract_title(soup)
        author = self._extract_author(soup)

        # Remove boilerplate
        self._remove_boilerplate(soup)

        # Extract tables separately
        tables = self._extract_tables(soup)

        # Get clean text
        content = self._extract_clean_text(soup)

        metadata = DocumentMetadata(
            source_id=str(file_path),
            source_type=DocumentSource.HTML,
            title=title,
            author=author,
            word_count=len(content.split()),
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
        )

        return IngestedDocument(content=content, tables=tables, metadata=metadata)

    def _extract_title(self, soup) -> str:
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return ""

    def _extract_author(self, soup) -> str:
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author:
            return meta_author.get("content", "")
        return ""

    def _remove_boilerplate(self, soup) -> None:
        for selector in self.BOILERPLATE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

    def _extract_tables(self, soup) -> list[str]:
        tables = []
        for table in soup.find_all("table"):
            tables.append(self._table_to_markdown(table))
            table.decompose()  # Remove from main content
        return tables

    def _table_to_markdown(self, table) -> str:
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            rows.append("| " + " | ".join(cells) + " |")
        if len(rows) > 1:
            # Add header separator
            header_sep = "| " + " | ".join(["---"] * len(rows[0].split("|")[1:-1])) + " |"
            rows.insert(1, header_sep)
        return "\n".join(rows)

    def _extract_clean_text(self, soup) -> str:
        # Preserve structure with headings
        lines = []
        for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "code"]):
            tag = element.name
            text = element.get_text(strip=True)
            if not text:
                continue
            if tag.startswith("h"):
                level = int(tag[1])
                lines.append(f"{'#' * level} {text}")
            elif tag == "li":
                lines.append(f"- {text}")
            elif tag in ("pre", "code"):
                lines.append(f"```\n{text}\n```")
            else:
                lines.append(text)
        return "\n\n".join(lines)


# ─── Markdown Parser ──────────────────────────────────────────────────────────


class MarkdownParser:
    """Parse Markdown files with metadata extraction from frontmatter."""

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in (".md", ".markdown")

    def parse(self, file_path: Path) -> IngestedDocument:
        logger.info(f"Parsing Markdown: {file_path}")
        raw_content = file_path.read_text(encoding="utf-8", errors="replace")

        # Extract frontmatter if present
        frontmatter, content = self._split_frontmatter(raw_content)

        # Extract title from first heading if not in frontmatter
        title = frontmatter.get("title", "") or self._extract_first_heading(content)

        metadata = DocumentMetadata(
            source_id=str(file_path),
            source_type=DocumentSource.MARKDOWN,
            title=title,
            author=frontmatter.get("author", ""),
            tags=frontmatter.get("tags", []),
            word_count=len(content.split()),
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            custom_metadata=frontmatter,
        )

        return IngestedDocument(content=content, metadata=metadata)

    def _split_frontmatter(self, content: str) -> tuple[dict, str]:
        """Extract YAML frontmatter from markdown."""
        if not content.startswith("---"):
            return {}, content
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content
        try:
            import yaml
            frontmatter = yaml.safe_load(parts[1]) or {}
            return frontmatter, parts[2].strip()
        except Exception:
            return {}, content

    def _extract_first_heading(self, content: str) -> str:
        for line in content.split("\n"):
            if line.startswith("# "):
                return line[2:].strip()
        return ""


# ─── Plain Text Parser ─────────────────────────────────────────────────────────


class PlainTextParser:
    """Fallback parser for plain text files."""

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in (".txt", ".text", ".log", "")

    def parse(self, file_path: Path) -> IngestedDocument:
        logger.info(f"Parsing plain text: {file_path}")
        content = file_path.read_text(encoding="utf-8", errors="replace")

        metadata = DocumentMetadata(
            source_id=str(file_path),
            source_type=DocumentSource.PLAIN_TEXT,
            title=file_path.stem,
            word_count=len(content.split()),
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
        )

        return IngestedDocument(content=content, metadata=metadata)


# ─── Deduplication Service ─────────────────────────────────────────────────────


class DeduplicationService:
    """
    Content-based deduplication using SHA-256 hashes.
    Tracks document versions when content changes.
    """

    def __init__(self):
        # In production, this would be backed by a database
        self._hash_store: dict[str, dict[str, Any]] = {}  # source_id -> {hash, version, doc_id}

    def check_and_register(self, document: IngestedDocument) -> tuple[bool, int]:
        """
        Check if document is a duplicate.
        Returns (is_duplicate, version_number).
        """
        source_id = document.metadata.source_id
        content_hash = document.metadata.content_hash

        if source_id in self._hash_store:
            existing = self._hash_store[source_id]
            if existing["hash"] == content_hash:
                # Exact duplicate — skip
                return True, existing["version"]
            else:
                # Content changed — new version
                new_version = existing["version"] + 1
                self._hash_store[source_id] = {
                    "hash": content_hash,
                    "version": new_version,
                    "doc_id": document.id,
                }
                return False, new_version
        else:
            # New document
            self._hash_store[source_id] = {
                "hash": content_hash,
                "version": 1,
                "doc_id": document.id,
            }
            return False, 1

    def get_previous_doc_id(self, source_id: str) -> Optional[str]:
        """Get the doc_id of the previous version for deletion propagation."""
        if source_id in self._hash_store:
            return self._hash_store[source_id].get("doc_id")
        return None


# ─── Boilerplate Removal ──────────────────────────────────────────────────────


class BoilerplateRemover:
    """Remove common boilerplate patterns from extracted text."""

    PATTERNS_TO_REMOVE = [
        # Page headers/footers
        r"Page \d+ of \d+",
        r"^\d+$",  # Standalone page numbers
        r"CONFIDENTIAL",
        r"DRAFT",
        # Common PDF artifacts
        r"^\s*[-_=]{3,}\s*$",  # Horizontal rules used as separators
    ]

    def clean(self, content: str) -> str:
        import re

        lines = content.split("\n")
        cleaned_lines = []

        for line in lines:
            # Skip empty lines at boundaries (preserve internal ones)
            stripped = line.strip()

            # Skip lines matching boilerplate patterns
            is_boilerplate = False
            for pattern in self.PATTERNS_TO_REMOVE:
                if re.match(pattern, stripped, re.IGNORECASE):
                    is_boilerplate = True
                    break

            if not is_boilerplate:
                cleaned_lines.append(line)

        # Collapse multiple blank lines into maximum 2
        result = "\n".join(cleaned_lines)
        result = re.sub(r"\n{4,}", "\n\n\n", result)

        return result.strip()


# ─── Document Store Protocol ──────────────────────────────────────────────────


class DocumentStore(Protocol):
    """Protocol for document persistence."""
    def save(self, document: IngestedDocument) -> None: ...
    def delete(self, document_id: str) -> None: ...
    def get_by_source(self, source_id: str) -> Optional[IngestedDocument]: ...


class InMemoryDocumentStore:
    """In-memory store for development/testing."""

    def __init__(self):
        self._store: dict[str, IngestedDocument] = {}
        self._source_index: dict[str, str] = {}  # source_id -> doc_id

    def save(self, document: IngestedDocument) -> None:
        self._store[document.id] = document
        self._source_index[document.metadata.source_id] = document.id

    def delete(self, document_id: str) -> None:
        if document_id in self._store:
            doc = self._store.pop(document_id)
            self._source_index.pop(doc.metadata.source_id, None)
            logger.info(f"Deleted document {document_id}")

    def get_by_source(self, source_id: str) -> Optional[IngestedDocument]:
        doc_id = self._source_index.get(source_id)
        if doc_id:
            return self._store.get(doc_id)
        return None

    @property
    def count(self) -> int:
        return len(self._store)


# ─── Ingestion Pipeline ───────────────────────────────────────────────────────


class IngestionPipeline:
    """
    Complete document ingestion pipeline with:
    - Multi-format parsing
    - Deduplication
    - Boilerplate removal
    - Version management
    - Deletion propagation
    - Error handling and observability
    """

    def __init__(
        self,
        document_store: DocumentStore | None = None,
        dedup_service: DeduplicationService | None = None,
        boilerplate_remover: BoilerplateRemover | None = None,
    ):
        self.document_store = document_store or InMemoryDocumentStore()
        self.dedup_service = dedup_service or DeduplicationService()
        self.boilerplate_remover = boilerplate_remover or BoilerplateRemover()

        # Register parsers in priority order
        self.parsers: list[DocumentParser] = [
            PDFParser(),
            HTMLParser(),
            MarkdownParser(),
            PlainTextParser(),
        ]

    def get_parser(self, file_path: Path) -> Optional[DocumentParser]:
        """Find appropriate parser for file type."""
        for parser in self.parsers:
            if parser.supports(file_path):
                return parser
        return None

    def ingest_file(
        self,
        file_path: Path,
        access_control: list[str] | None = None,
        custom_metadata: dict[str, Any] | None = None,
    ) -> IngestionResult:
        """
        Ingest a single file through the complete pipeline.

        Steps:
        1. Parse document (format-specific)
        2. Remove boilerplate
        3. Check deduplication
        4. Handle versioning
        5. Propagate deletions (old versions)
        6. Store document
        """
        start_time = time.perf_counter()
        source_path = str(file_path)

        try:
            # Step 1: Find parser
            parser = self.get_parser(file_path)
            if parser is None:
                return IngestionResult(
                    document_id="",
                    source_path=source_path,
                    status=DocumentStatus.FAILED,
                    error=f"No parser available for file type: {file_path.suffix}",
                )

            # Step 2: Parse document
            document = parser.parse(file_path)

            # Step 3: Clean content
            document.content = self.boilerplate_remover.clean(document.content)

            # Step 4: Apply access control
            if access_control:
                document.metadata.access_control = access_control

            # Step 5: Apply custom metadata
            if custom_metadata:
                document.metadata.custom_metadata.update(custom_metadata)

            # Step 6: Check deduplication
            is_duplicate, version = self.dedup_service.check_and_register(document)
            if is_duplicate:
                elapsed = (time.perf_counter() - start_time) * 1000
                logger.info(f"Skipping duplicate: {source_path}")
                return IngestionResult(
                    document_id=document.id,
                    source_path=source_path,
                    status=DocumentStatus.INDEXED,
                    is_duplicate=True,
                    version=version,
                    processing_time_ms=elapsed,
                )

            # Step 7: Handle versioning — delete old version
            if version > 1:
                old_doc_id = self.dedup_service.get_previous_doc_id(document.metadata.source_id)
                if old_doc_id:
                    self.document_store.delete(old_doc_id)
                    logger.info(f"Deleted previous version (v{version - 1}) of {source_path}")

            document.metadata.version = version
            document.status = DocumentStatus.INDEXED

            # Step 8: Store document
            self.document_store.save(document)

            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"Ingested {source_path} (v{version}) — "
                f"{document.metadata.word_count} words, {elapsed:.1f}ms"
            )

            return IngestionResult(
                document_id=document.id,
                source_path=source_path,
                status=DocumentStatus.INDEXED,
                version=version,
                processing_time_ms=elapsed,
            )

        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error(f"Failed to ingest {source_path}: {e}", exc_info=True)
            return IngestionResult(
                document_id="",
                source_path=source_path,
                status=DocumentStatus.FAILED,
                error=str(e),
                processing_time_ms=elapsed,
            )

    def ingest_batch(
        self,
        file_paths: list[Path],
        access_control: list[str] | None = None,
        custom_metadata: dict[str, Any] | None = None,
        continue_on_error: bool = True,
    ) -> BatchIngestionResult:
        """
        Ingest multiple files with aggregated results.

        Args:
            file_paths: List of files to ingest
            access_control: ACL groups applied to all documents
            custom_metadata: Metadata applied to all documents
            continue_on_error: If False, stop on first failure
        """
        batch_start = time.perf_counter()
        batch_result = BatchIngestionResult(total=len(file_paths))

        for i, file_path in enumerate(file_paths):
            logger.info(f"Processing [{i + 1}/{len(file_paths)}]: {file_path}")

            result = self.ingest_file(file_path, access_control, custom_metadata)
            batch_result.results.append(result)

            if result.status == DocumentStatus.INDEXED:
                if result.is_duplicate:
                    batch_result.duplicates_skipped += 1
                else:
                    batch_result.succeeded += 1
            elif result.status == DocumentStatus.FAILED:
                batch_result.failed += 1
                if not continue_on_error:
                    logger.error("Stopping batch due to failure (continue_on_error=False)")
                    break

        batch_result.total_time_ms = (time.perf_counter() - batch_start) * 1000
        logger.info(
            f"Batch complete: {batch_result.succeeded} succeeded, "
            f"{batch_result.failed} failed, {batch_result.duplicates_skipped} duplicates "
            f"in {batch_result.total_time_ms:.1f}ms"
        )
        return batch_result

    def ingest_directory(
        self,
        directory: Path,
        recursive: bool = True,
        extensions: list[str] | None = None,
        access_control: list[str] | None = None,
    ) -> BatchIngestionResult:
        """Ingest all supported files from a directory."""
        if extensions is None:
            extensions = [".pdf", ".html", ".htm", ".md", ".markdown", ".txt"]

        pattern = "**/*" if recursive else "*"
        file_paths = [
            f for f in directory.glob(pattern)
            if f.is_file() and f.suffix.lower() in extensions
        ]

        logger.info(f"Found {len(file_paths)} files in {directory}")
        return self.ingest_batch(file_paths, access_control=access_control)

    def delete_document(self, source_id: str) -> bool:
        """
        Delete a document and propagate deletion to downstream stores.
        In production, this would also delete chunks from vector store.
        """
        existing = self.document_store.get_by_source(source_id)
        if existing:
            self.document_store.delete(existing.id)
            logger.info(f"Deleted document with source_id={source_id}")
            # TODO: In production, also delete from vector store, search index, etc.
            return True
        return False


# ─── Usage Example ─────────────────────────────────────────────────────────────


def main():
    """Example usage of the ingestion pipeline."""

    pipeline = IngestionPipeline()

    # Single file ingestion
    # result = pipeline.ingest_file(
    #     Path("./documents/architecture-guide.pdf"),
    #     access_control=["engineering", "architects"],
    #     custom_metadata={"department": "engineering", "category": "architecture"},
    # )

    # Batch ingestion
    # batch_result = pipeline.ingest_directory(
    #     Path("./documents/"),
    #     recursive=True,
    #     extensions=[".pdf", ".md", ".html"],
    #     access_control=["all-employees"],
    # )

    # Demonstrate with a simple text example
    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("RAG (Retrieval-Augmented Generation) is a pattern that grounds LLM responses in factual data.")
        temp_path = Path(f.name)

    result = pipeline.ingest_file(temp_path)
    print(f"Ingestion result: {result.status.value}, doc_id={result.document_id}")

    # Re-ingest same file (should detect duplicate)
    result2 = pipeline.ingest_file(temp_path)
    print(f"Re-ingestion: duplicate={result2.is_duplicate}")

    # Clean up
    temp_path.unlink()


if __name__ == "__main__":
    main()
