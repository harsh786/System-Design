"""
Layout-Aware Chunking Implementation
=====================================
Intelligent document chunking that respects document structure:
tables, figures, sections, lists, and cross-page elements.
"""

import re
import hashlib
import logging
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

class ElementType(Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    FIGURE = "figure"
    LIST = "list"
    LIST_ITEM = "list_item"
    CAPTION = "caption"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_NUMBER = "page_number"
    FOOTNOTE = "footnote"
    CODE_BLOCK = "code_block"
    EQUATION = "equation"
    BLOCKQUOTE = "blockquote"


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float
    page: int


@dataclass
class DocumentElement:
    """A structural element from document parsing."""
    element_type: ElementType
    content: str
    page: int
    bbox: Optional[BoundingBox] = None
    level: int = 0  # For headings (1-6) or nesting depth
    metadata: dict = field(default_factory=dict)
    # Relationships
    parent_heading: Optional[str] = None
    related_elements: list[str] = field(default_factory=list)  # IDs of related elements

    @property
    def element_id(self) -> str:
        h = hashlib.md5(f"{self.element_type.value}_{self.page}_{self.content[:30]}".encode())
        return h.hexdigest()[:12]

    @property
    def token_estimate(self) -> int:
        return int(len(self.content.split()) * 1.3)


@dataclass
class LayoutChunk:
    """A chunk produced by layout-aware chunking."""
    chunk_id: str
    content: str
    elements: list[DocumentElement]
    # Location
    start_page: int
    end_page: int
    # Structure metadata
    section_hierarchy: list[str]  # ["Chapter 1", "Section 1.2", "Subsection 1.2.1"]
    primary_type: ElementType  # Dominant element type in this chunk
    # For retrieval enrichment
    heading_context: str = ""  # Concatenated parent headings
    # Quality
    token_count: int = 0
    is_complete: bool = True  # False if chunk was split mid-element
    # Coordinates for citation
    bboxes: list[BoundingBox] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "section_hierarchy": self.section_hierarchy,
            "primary_type": self.primary_type.value,
            "heading_context": self.heading_context,
            "token_count": self.token_count,
            "is_complete": self.is_complete
        }


# =============================================================================
# Page Structure Detector
# =============================================================================

class PageStructureDetector:
    """Detects page-level structure: headers, body, footer regions."""

    def __init__(self, header_threshold: float = 0.08,
                 footer_threshold: float = 0.92):
        self.header_threshold = header_threshold
        self.footer_threshold = footer_threshold

    def classify_regions(self, elements: list[DocumentElement]) -> dict[str, list[DocumentElement]]:
        """Classify elements into header, body, and footer regions."""
        regions = {"header": [], "body": [], "footer": []}

        for elem in elements:
            if not elem.bbox:
                regions["body"].append(elem)
                continue

            y_pos = elem.bbox.y1  # Normalized 0-1

            if y_pos < self.header_threshold:
                regions["header"].append(elem)
                elem.element_type = ElementType.HEADER
            elif y_pos > self.footer_threshold:
                regions["footer"].append(elem)
                elem.element_type = ElementType.FOOTER
            else:
                regions["body"].append(elem)

        return regions

    def detect_repeated_headers_footers(self, pages: list[list[DocumentElement]]) -> tuple[set, set]:
        """
        Detect repeated headers/footers across pages.
        These should be excluded from chunking.
        """
        if len(pages) < 3:
            return set(), set()

        # Collect header/footer content across pages
        header_contents = []
        footer_contents = []

        for page_elements in pages:
            regions = self.classify_regions(page_elements)
            header_contents.append(
                frozenset(e.content.strip() for e in regions["header"])
            )
            footer_contents.append(
                frozenset(e.content.strip() for e in regions["footer"])
            )

        # Find content that appears on most pages
        repeated_headers = set()
        repeated_footers = set()

        if header_contents:
            # Content appearing on >60% of pages is likely a running header
            all_header_texts = [t for fs in header_contents for t in fs]
            for text in set(all_header_texts):
                count = sum(1 for fs in header_contents if text in fs)
                if count > len(pages) * 0.6:
                    repeated_headers.add(text)

        if footer_contents:
            all_footer_texts = [t for fs in footer_contents for t in fs]
            for text in set(all_footer_texts):
                count = sum(1 for fs in footer_contents if text in fs)
                if count > len(pages) * 0.6:
                    repeated_footers.add(text)

        return repeated_headers, repeated_footers


# =============================================================================
# Section Hierarchy Extractor
# =============================================================================

class SectionHierarchyExtractor:
    """Extracts section hierarchy from headings."""

    def __init__(self):
        self.hierarchy_stack: list[tuple[int, str]] = []  # (level, title)

    def reset(self):
        self.hierarchy_stack = []

    def process_heading(self, heading: DocumentElement) -> list[str]:
        """Process a heading and return current hierarchy."""
        level = heading.level or self._infer_level(heading)
        title = heading.content.strip()

        # Pop headings at same or lower level
        while self.hierarchy_stack and self.hierarchy_stack[-1][0] >= level:
            self.hierarchy_stack.pop()

        self.hierarchy_stack.append((level, title))

        return [h[1] for h in self.hierarchy_stack]

    def get_current_hierarchy(self) -> list[str]:
        return [h[1] for h in self.hierarchy_stack]

    def _infer_level(self, heading: DocumentElement) -> int:
        """Infer heading level from metadata if not explicitly set."""
        # Check font size
        font_size = heading.metadata.get("font_size", 12)
        if font_size >= 24:
            return 1
        elif font_size >= 18:
            return 2
        elif font_size >= 14:
            return 3
        else:
            return 4


# =============================================================================
# Element Grouping Strategies
# =============================================================================

class TableAwareGrouper:
    """Ensures tables are never split across chunks."""

    def group(self, elements: list[DocumentElement],
              max_tokens: int) -> list[list[DocumentElement]]:
        """Group elements keeping tables intact."""
        groups = []
        current_group = []
        current_tokens = 0

        for elem in elements:
            elem_tokens = elem.token_estimate

            if elem.element_type == ElementType.TABLE:
                # Tables get their own group (or are added whole to current)
                if current_tokens + elem_tokens > max_tokens and current_group:
                    groups.append(current_group)
                    current_group = []
                    current_tokens = 0

                # If table alone exceeds limit, it still gets its own chunk
                if elem_tokens > max_tokens:
                    if current_group:
                        groups.append(current_group)
                        current_group = []
                        current_tokens = 0
                    groups.append([elem])
                else:
                    current_group.append(elem)
                    current_tokens += elem_tokens
            else:
                if current_tokens + elem_tokens > max_tokens and current_group:
                    groups.append(current_group)
                    current_group = []
                    current_tokens = 0
                current_group.append(elem)
                current_tokens += elem_tokens

        if current_group:
            groups.append(current_group)

        return groups


class FigureAwareGrouper:
    """Associates figures with their captions and keeps them together."""

    def associate_captions(self, elements: list[DocumentElement]) -> list[DocumentElement]:
        """Find and associate captions with their figures."""
        result = []
        skip_next = False

        for i, elem in enumerate(elements):
            if skip_next:
                skip_next = False
                continue

            if elem.element_type == ElementType.FIGURE:
                # Look for caption immediately before or after
                caption = None

                # Check next element
                if i + 1 < len(elements):
                    next_elem = elements[i + 1]
                    if (next_elem.element_type == ElementType.CAPTION or
                        self._looks_like_caption(next_elem.content)):
                        caption = next_elem
                        skip_next = True

                # Check previous element
                if not caption and i > 0:
                    prev_elem = elements[i - 1]
                    if self._looks_like_caption(prev_elem.content):
                        caption = prev_elem
                        # Already added prev, update its relationship
                        if result and result[-1] == prev_elem:
                            result.pop()

                if caption:
                    elem.related_elements.append(caption.element_id)
                    elem.metadata["caption"] = caption.content
                    # Merge content
                    elem.content = f"{elem.content}\nCaption: {caption.content}"

            result.append(elem)

        return result

    def _looks_like_caption(self, text: str) -> bool:
        """Check if text looks like a figure/table caption."""
        caption_patterns = [
            r'^Figure\s+\d+',
            r'^Fig\.\s+\d+',
            r'^Table\s+\d+',
            r'^Chart\s+\d+',
            r'^Exhibit\s+\d+',
        ]
        return any(re.match(p, text, re.IGNORECASE) for p in caption_patterns)


class ListGrouper:
    """Detects and groups list items together."""

    def group_lists(self, elements: list[DocumentElement]) -> list[DocumentElement]:
        """Group consecutive list items into a single list element."""
        result = []
        list_buffer = []

        for elem in elements:
            if elem.element_type == ElementType.LIST_ITEM or self._is_list_item(elem):
                list_buffer.append(elem)
            else:
                if list_buffer:
                    merged = self._merge_list_items(list_buffer)
                    result.append(merged)
                    list_buffer = []
                result.append(elem)

        if list_buffer:
            result.append(self._merge_list_items(list_buffer))

        return result

    def _is_list_item(self, elem: DocumentElement) -> bool:
        """Detect list items by content pattern."""
        if elem.element_type != ElementType.PARAGRAPH:
            return False
        return bool(re.match(r'^\s*[•\-\*\u2022]\s', elem.content) or
                   re.match(r'^\s*\d+[\.\)]\s', elem.content) or
                   re.match(r'^\s*[a-z][\.\)]\s', elem.content))

    def _merge_list_items(self, items: list[DocumentElement]) -> DocumentElement:
        """Merge list items into a single list element."""
        content = "\n".join(item.content for item in items)
        return DocumentElement(
            element_type=ElementType.LIST,
            content=content,
            page=items[0].page,
            bbox=items[0].bbox,
            level=items[0].level,
            metadata={"item_count": len(items)},
            parent_heading=items[0].parent_heading
        )


# =============================================================================
# Cross-Page Element Handler
# =============================================================================

class CrossPageHandler:
    """Handles elements that span multiple pages."""

    def merge_cross_page_elements(self, pages: list[list[DocumentElement]]) -> list[DocumentElement]:
        """
        Detect and merge elements that continue across page boundaries.
        E.g., a paragraph split across pages, or a table spanning pages.
        """
        merged = []
        pending_merge: Optional[DocumentElement] = None

        for page_idx, page_elements in enumerate(pages):
            for elem_idx, elem in enumerate(page_elements):
                if pending_merge:
                    if self._is_continuation(pending_merge, elem):
                        # Merge with pending
                        pending_merge.content += " " + elem.content
                        pending_merge.metadata["end_page"] = elem.page
                        if elem_idx == len(page_elements) - 1:
                            # Still might continue on next page
                            continue
                        else:
                            merged.append(pending_merge)
                            pending_merge = None
                            continue
                    else:
                        merged.append(pending_merge)
                        pending_merge = None

                # Check if element continues to next page
                if (elem_idx == len(page_elements) - 1 and
                    page_idx < len(pages) - 1 and
                    self._might_continue(elem)):
                    pending_merge = elem
                    pending_merge.metadata["start_page"] = elem.page
                else:
                    merged.append(elem)

        if pending_merge:
            merged.append(pending_merge)

        return merged

    def _is_continuation(self, prev: DocumentElement, curr: DocumentElement) -> bool:
        """Check if curr is a continuation of prev across a page boundary."""
        # Same type (paragraph continues as paragraph)
        if prev.element_type != curr.element_type:
            # Exception: table continuation
            if prev.element_type == ElementType.TABLE and curr.element_type == ElementType.TABLE:
                return True
            return False

        # Text continuation heuristics
        if prev.element_type == ElementType.PARAGRAPH:
            # Ends without sentence-ending punctuation
            if not prev.content.rstrip().endswith(('.', '!', '?', ':')):
                return True
            # Current starts with lowercase
            if curr.content and curr.content[0].islower():
                return True

        return False

    def _might_continue(self, elem: DocumentElement) -> bool:
        """Check if an element at end of page might continue."""
        if elem.element_type == ElementType.PARAGRAPH:
            text = elem.content.rstrip()
            # Doesn't end with sentence-ending punctuation
            if text and not text[-1] in '.!?':
                return True
        if elem.element_type == ElementType.TABLE:
            # Tables at bottom of page often continue
            if elem.bbox and elem.bbox.y2 > 0.9:
                return True
        return False


# =============================================================================
# Metadata Enrichment
# =============================================================================

class ChunkMetadataEnricher:
    """Enriches chunks with metadata from document structure."""

    def enrich(self, chunk: LayoutChunk, document_metadata: dict) -> LayoutChunk:
        """Add metadata to a chunk for better retrieval."""
        # Build heading context string
        if chunk.section_hierarchy:
            chunk.heading_context = " > ".join(chunk.section_hierarchy)

        # Add document-level metadata
        chunk.content = self._prepend_context(chunk)

        return chunk

    def _prepend_context(self, chunk: LayoutChunk) -> str:
        """Prepend structural context to chunk content for better embedding."""
        parts = []

        if chunk.heading_context:
            parts.append(f"Section: {chunk.heading_context}")

        if chunk.primary_type == ElementType.TABLE:
            parts.append("[Table content]")
        elif chunk.primary_type == ElementType.FIGURE:
            parts.append("[Figure]")

        parts.append(chunk.content)

        return "\n".join(parts)


# =============================================================================
# Chunk Quality Validator
# =============================================================================

class ChunkQualityValidator:
    """Validates chunk quality and flags issues."""

    def __init__(self, min_tokens: int = 20, max_tokens: int = 1000,
                 min_content_ratio: float = 0.3):
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.min_content_ratio = min_content_ratio

    def validate(self, chunk: LayoutChunk) -> tuple[bool, list[str]]:
        """
        Validate a chunk. Returns (is_valid, issues).
        """
        issues = []

        # Token count checks
        if chunk.token_count < self.min_tokens:
            issues.append(f"Too short ({chunk.token_count} tokens < {self.min_tokens})")

        if chunk.token_count > self.max_tokens:
            issues.append(f"Too long ({chunk.token_count} tokens > {self.max_tokens})")

        # Content quality checks
        content = chunk.content.strip()
        if not content:
            issues.append("Empty content")
            return False, issues

        # Check for meaningful content (not just whitespace/numbers)
        alpha_ratio = sum(c.isalpha() for c in content) / max(len(content), 1)
        if alpha_ratio < self.min_content_ratio:
            issues.append(f"Low text content ratio ({alpha_ratio:.0%})")

        # Check for incomplete sentences (split mid-sentence)
        if not chunk.is_complete:
            issues.append("Chunk appears incomplete (split mid-element)")

        # Check section hierarchy is reasonable
        if not chunk.section_hierarchy and chunk.primary_type == ElementType.PARAGRAPH:
            issues.append("No section context (orphaned paragraph)")

        is_valid = len(issues) == 0
        return is_valid, issues

    def validate_batch(self, chunks: list[LayoutChunk]) -> dict:
        """Validate a batch of chunks and return statistics."""
        stats = {
            "total": len(chunks),
            "valid": 0,
            "invalid": 0,
            "issues": {},
            "avg_tokens": 0,
            "token_distribution": {"<50": 0, "50-200": 0, "200-500": 0, "500-1000": 0, ">1000": 0}
        }

        total_tokens = 0
        for chunk in chunks:
            is_valid, issues = self.validate(chunk)
            if is_valid:
                stats["valid"] += 1
            else:
                stats["invalid"] += 1
                for issue in issues:
                    stats["issues"][issue] = stats["issues"].get(issue, 0) + 1

            total_tokens += chunk.token_count
            if chunk.token_count < 50:
                stats["token_distribution"]["<50"] += 1
            elif chunk.token_count < 200:
                stats["token_distribution"]["50-200"] += 1
            elif chunk.token_count < 500:
                stats["token_distribution"]["200-500"] += 1
            elif chunk.token_count < 1000:
                stats["token_distribution"]["500-1000"] += 1
            else:
                stats["token_distribution"][">1000"] += 1

        stats["avg_tokens"] = total_tokens / max(len(chunks), 1)
        return stats


# =============================================================================
# Layout-Aware Chunker (Main Class)
# =============================================================================

class LayoutAwareChunker:
    """
    Main chunking engine that respects document layout and structure.
    Never splits tables, keeps figures with captions, respects sections.
    """

    def __init__(self, config: Optional[dict] = None):
        config = config or {}

        self.max_chunk_tokens = config.get("max_chunk_tokens", 500)
        self.min_chunk_tokens = config.get("min_chunk_tokens", 50)
        self.overlap_tokens = config.get("overlap_tokens", 50)
        self.respect_sections = config.get("respect_sections", True)

        # Sub-components
        self.page_structure = PageStructureDetector()
        self.hierarchy_extractor = SectionHierarchyExtractor()
        self.table_grouper = TableAwareGrouper()
        self.figure_grouper = FigureAwareGrouper()
        self.list_grouper = ListGrouper()
        self.cross_page_handler = CrossPageHandler()
        self.metadata_enricher = ChunkMetadataEnricher()
        self.quality_validator = ChunkQualityValidator(
            min_tokens=self.min_chunk_tokens,
            max_tokens=self.max_chunk_tokens * 2  # Allow some overflow for tables
        )

    def chunk_document(self, pages: list[list[DocumentElement]],
                       document_metadata: Optional[dict] = None) -> list[LayoutChunk]:
        """
        Chunk a document respecting its layout structure.
        
        Args:
            pages: List of pages, each containing a list of elements
            document_metadata: Optional document-level metadata
        """
        document_metadata = document_metadata or {}
        logger.info(f"Chunking document with {len(pages)} pages")

        # Step 1: Remove repeated headers/footers
        repeated_headers, repeated_footers = self.page_structure.detect_repeated_headers_footers(pages)
        cleaned_pages = self._remove_repeated_elements(pages, repeated_headers, repeated_footers)

        # Step 2: Handle cross-page elements
        all_elements = self.cross_page_handler.merge_cross_page_elements(cleaned_pages)
        logger.info(f"After cross-page merge: {len(all_elements)} elements")

        # Step 3: Associate figures with captions
        all_elements = self.figure_grouper.associate_captions(all_elements)

        # Step 4: Group list items
        all_elements = self.list_grouper.group_lists(all_elements)

        # Step 5: Build section hierarchy and chunk
        chunks = self._chunk_with_structure(all_elements)
        logger.info(f"Initial chunking: {len(chunks)} chunks")

        # Step 6: Enrich metadata
        for chunk in chunks:
            self.metadata_enricher.enrich(chunk, document_metadata)

        # Step 7: Validate
        stats = self.quality_validator.validate_batch(chunks)
        logger.info(f"Chunk validation: {stats['valid']}/{stats['total']} valid, "
                    f"avg {stats['avg_tokens']:.0f} tokens")

        # Step 8: Fix invalid chunks
        chunks = self._fix_invalid_chunks(chunks)

        return chunks

    def _remove_repeated_elements(self, pages: list[list[DocumentElement]],
                                   headers: set, footers: set) -> list[list[DocumentElement]]:
        """Remove repeated headers/footers from pages."""
        cleaned = []
        for page_elements in pages:
            filtered = [
                e for e in page_elements
                if e.content.strip() not in headers and e.content.strip() not in footers
                and e.element_type not in (ElementType.PAGE_NUMBER,)
            ]
            cleaned.append(filtered)
        return cleaned

    def _chunk_with_structure(self, elements: list[DocumentElement]) -> list[LayoutChunk]:
        """Main chunking logic respecting document structure."""
        chunks = []
        self.hierarchy_extractor.reset()

        current_elements: list[DocumentElement] = []
        current_tokens = 0
        current_hierarchy: list[str] = []

        for elem in elements:
            # Update hierarchy on headings
            if elem.element_type == ElementType.HEADING:
                new_hierarchy = self.hierarchy_extractor.process_heading(elem)

                # Section break: start new chunk if we have content
                if self.respect_sections and current_elements:
                    chunk = self._build_chunk(current_elements, current_hierarchy)
                    chunks.append(chunk)
                    current_elements = []
                    current_tokens = 0

                current_hierarchy = new_hierarchy
                current_elements.append(elem)
                current_tokens += elem.token_estimate
                continue

            # Special elements that should not be split
            if elem.element_type in (ElementType.TABLE, ElementType.FIGURE):
                elem_tokens = elem.token_estimate

                # If current chunk + this element is too large, flush current first
                if current_tokens + elem_tokens > self.max_chunk_tokens and current_elements:
                    chunk = self._build_chunk(current_elements, current_hierarchy)
                    chunks.append(chunk)
                    current_elements = []
                    current_tokens = 0

                # Add the special element (may exceed max_tokens, that's OK)
                current_elements.append(elem)
                current_tokens += elem_tokens

                # If this element alone is large enough, make it its own chunk
                if current_tokens >= self.max_chunk_tokens:
                    chunk = self._build_chunk(current_elements, current_hierarchy)
                    chunks.append(chunk)
                    current_elements = []
                    current_tokens = 0

                continue

            # Regular elements (paragraphs, etc.)
            elem_tokens = elem.token_estimate

            if current_tokens + elem_tokens > self.max_chunk_tokens:
                if current_elements:
                    chunk = self._build_chunk(current_elements, current_hierarchy)
                    chunks.append(chunk)

                    # Overlap: keep last element if it's a paragraph
                    if (self.overlap_tokens > 0 and
                        current_elements[-1].element_type == ElementType.PARAGRAPH):
                        overlap_elem = current_elements[-1]
                        current_elements = [overlap_elem]
                        current_tokens = overlap_elem.token_estimate
                    else:
                        current_elements = []
                        current_tokens = 0

            current_elements.append(elem)
            current_tokens += elem_tokens

        # Final chunk
        if current_elements:
            chunk = self._build_chunk(current_elements, current_hierarchy)
            chunks.append(chunk)

        return chunks

    def _build_chunk(self, elements: list[DocumentElement],
                     hierarchy: list[str]) -> LayoutChunk:
        """Build a LayoutChunk from a group of elements."""
        content = "\n\n".join(elem.content for elem in elements)
        token_count = sum(elem.token_estimate for elem in elements)

        # Determine primary type
        type_counts = {}
        for elem in elements:
            type_counts[elem.element_type] = type_counts.get(elem.element_type, 0) + 1
        primary_type = max(type_counts, key=type_counts.get) if type_counts else ElementType.PARAGRAPH

        # Pages spanned
        pages = [elem.page for elem in elements]
        start_page = min(pages) if pages else 0
        end_page = max(pages) if pages else 0

        # Bounding boxes
        bboxes = [elem.bbox for elem in elements if elem.bbox]

        chunk_id = hashlib.md5(
            f"{start_page}_{content[:50]}_{len(elements)}".encode()
        ).hexdigest()[:12]

        return LayoutChunk(
            chunk_id=chunk_id,
            content=content,
            elements=elements,
            start_page=start_page,
            end_page=end_page,
            section_hierarchy=list(hierarchy),
            primary_type=primary_type,
            token_count=token_count,
            is_complete=True,
            bboxes=bboxes
        )

    def _fix_invalid_chunks(self, chunks: list[LayoutChunk]) -> list[LayoutChunk]:
        """Fix or remove invalid chunks."""
        fixed = []
        merge_buffer = None

        for chunk in chunks:
            is_valid, issues = self.quality_validator.validate(chunk)

            if is_valid:
                if merge_buffer:
                    # Merge buffer with this chunk
                    merged = self._merge_chunks(merge_buffer, chunk)
                    fixed.append(merged)
                    merge_buffer = None
                else:
                    fixed.append(chunk)
            else:
                if "Too short" in str(issues):
                    # Try to merge with adjacent chunk
                    if merge_buffer:
                        merge_buffer = self._merge_chunks(merge_buffer, chunk)
                    else:
                        merge_buffer = chunk
                elif "Empty content" in str(issues):
                    continue  # Skip empty chunks
                else:
                    fixed.append(chunk)  # Keep despite issues

        # Handle remaining buffer
        if merge_buffer:
            if fixed:
                fixed[-1] = self._merge_chunks(fixed[-1], merge_buffer)
            else:
                fixed.append(merge_buffer)

        return fixed

    def _merge_chunks(self, chunk1: LayoutChunk, chunk2: LayoutChunk) -> LayoutChunk:
        """Merge two chunks."""
        content = chunk1.content + "\n\n" + chunk2.content
        elements = chunk1.elements + chunk2.elements
        token_count = chunk1.token_count + chunk2.token_count

        return LayoutChunk(
            chunk_id=hashlib.md5(content[:50].encode()).hexdigest()[:12],
            content=content,
            elements=elements,
            start_page=min(chunk1.start_page, chunk2.start_page),
            end_page=max(chunk1.end_page, chunk2.end_page),
            section_hierarchy=chunk1.section_hierarchy or chunk2.section_hierarchy,
            primary_type=chunk1.primary_type,
            heading_context=chunk1.heading_context or chunk2.heading_context,
            token_count=token_count,
            is_complete=chunk1.is_complete and chunk2.is_complete,
            bboxes=chunk1.bboxes + chunk2.bboxes
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def chunk_document_elements(elements: list[dict],
                            max_tokens: int = 500,
                            overlap: int = 50) -> list[dict]:
    """
    Convenience function to chunk document elements.
    
    Args:
        elements: List of dicts with keys: type, content, page, bbox, level, metadata
        max_tokens: Maximum tokens per chunk
        overlap: Overlap tokens between chunks
    
    Returns:
        List of chunk dicts ready for embedding
    """
    # Convert to DocumentElement objects
    doc_elements = []
    for elem in elements:
        doc_elements.append(DocumentElement(
            element_type=ElementType(elem.get("type", "paragraph")),
            content=elem.get("content", ""),
            page=elem.get("page", 0),
            bbox=BoundingBox(**elem["bbox"]) if elem.get("bbox") else None,
            level=elem.get("level", 0),
            metadata=elem.get("metadata", {})
        ))

    # Group by page
    pages: dict[int, list[DocumentElement]] = {}
    for elem in doc_elements:
        pages.setdefault(elem.page, []).append(elem)
    page_list = [pages[k] for k in sorted(pages.keys())]

    # Chunk
    chunker = LayoutAwareChunker(config={
        "max_chunk_tokens": max_tokens,
        "overlap_tokens": overlap
    })
    chunks = chunker.chunk_document(page_list)

    # Convert to dicts
    return [chunk.to_dict() for chunk in chunks]


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    # Simulate a document with mixed elements
    sample_elements = [
        # Page 0
        DocumentElement(ElementType.HEADING, "1. Introduction", page=0, level=1),
        DocumentElement(ElementType.PARAGRAPH,
                       "This document describes the quarterly financial results for FY2024. "
                       "Revenue growth was strong across all segments.", page=0),
        DocumentElement(ElementType.PARAGRAPH,
                       "The company achieved record revenue of $5.2B, driven by cloud services "
                       "and AI products.", page=0),
        # Page 1
        DocumentElement(ElementType.HEADING, "2. Financial Results", page=1, level=1),
        DocumentElement(ElementType.HEADING, "2.1 Revenue Breakdown", page=1, level=2),
        DocumentElement(ElementType.TABLE,
                       "| Segment | Revenue | Growth |\n|---|---|---|\n| Cloud | $2.1B | 22% |\n| AI | $1.5B | 45% |\n| Other | $1.6B | 5% |",
                       page=1, metadata={"rows": 4, "cols": 3}),
        DocumentElement(ElementType.PARAGRAPH,
                       "Cloud revenue grew 22% year-over-year, driven by enterprise adoption.", page=1),
        # Page 2
        DocumentElement(ElementType.HEADING, "2.2 Profitability", page=2, level=2),
        DocumentElement(ElementType.PARAGRAPH,
                       "Operating margin improved to 38%, up from 35% in the prior year.", page=2),
        DocumentElement(ElementType.FIGURE,
                       "[Revenue growth chart showing upward trend from Q1 to Q4]", page=2,
                       metadata={"caption": "Figure 1: Quarterly Revenue Trend"}),
    ]

    # Group by page
    pages_dict: dict[int, list[DocumentElement]] = {}
    for elem in sample_elements:
        pages_dict.setdefault(elem.page, []).append(elem)
    page_list = [pages_dict[k] for k in sorted(pages_dict.keys())]

    # Chunk
    chunker = LayoutAwareChunker(config={
        "max_chunk_tokens": 200,
        "min_chunk_tokens": 30,
        "overlap_tokens": 20,
        "respect_sections": True
    })

    chunks = chunker.chunk_document(page_list, document_metadata={"title": "Q4 FY2024 Report"})

    print(f"Generated {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ---")
        print(f"  Section: {' > '.join(chunk.section_hierarchy)}")
        print(f"  Pages: {chunk.start_page}-{chunk.end_page}")
        print(f"  Type: {chunk.primary_type.value}")
        print(f"  Tokens: {chunk.token_count}")
        print(f"  Content: {chunk.content[:100]}...")
