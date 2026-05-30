"""
Document Intelligence Implementation
=====================================
Production-grade document processing pipeline with OCR, table extraction,
form parsing, layout analysis, and coordinate-level citations.
"""

import io
import re
import json
import hashlib
import logging
from enum import Enum
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# Core Data Models
# =============================================================================

class ElementType(Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    CHART = "chart"
    FORM_FIELD = "form_field"
    HEADER = "header"
    FOOTER = "footer"
    LIST = "list"
    HEADING = "heading"
    PAGE_NUMBER = "page_number"


@dataclass
class BoundingBox:
    """Coordinate-level bounding box (normalized 0-1 or absolute pixels)."""
    x1: float
    y1: float
    x2: float
    y2: float
    page: int
    unit: str = "normalized"  # "normalized" (0-1) or "pixel"

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def overlaps(self, other: "BoundingBox") -> bool:
        if self.page != other.page:
            return False
        return not (self.x2 < other.x1 or other.x2 < self.x1 or
                    self.y2 < other.y1 or other.y2 < self.y1)

    def iou(self, other: "BoundingBox") -> float:
        if not self.overlaps(other):
            return 0.0
        inter_x1 = max(self.x1, other.x1)
        inter_y1 = max(self.y1, other.y1)
        inter_x2 = min(self.x2, other.x2)
        inter_y2 = min(self.y2, other.y2)
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        union_area = self.area + other.area - inter_area
        return inter_area / union_area if union_area > 0 else 0.0

    def to_dict(self) -> dict:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2,
                "page": self.page, "unit": self.unit}


@dataclass
class TableCell:
    text: str
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False
    bbox: Optional[BoundingBox] = None
    confidence: float = 1.0


@dataclass
class Table:
    cells: list[TableCell]
    num_rows: int
    num_cols: int
    bbox: Optional[BoundingBox] = None
    caption: Optional[str] = None

    def to_markdown(self) -> str:
        grid = [["" for _ in range(self.num_cols)] for _ in range(self.num_rows)]
        for cell in self.cells:
            if cell.row < self.num_rows and cell.col < self.num_cols:
                grid[cell.row][cell.col] = cell.text

        lines = []
        for i, row in enumerate(grid):
            lines.append("| " + " | ".join(row) + " |")
            if i == 0:
                lines.append("|" + "|".join(["---"] * self.num_cols) + "|")
        return "\n".join(lines)

    def to_csv(self) -> str:
        grid = [["" for _ in range(self.num_cols)] for _ in range(self.num_rows)]
        for cell in self.cells:
            if cell.row < self.num_rows and cell.col < self.num_cols:
                grid[cell.row][cell.col] = cell.text.replace(",", ";")
        return "\n".join(",".join(row) for row in grid)

    def to_dict(self) -> list[dict]:
        """Convert to list of dicts using first row as headers."""
        if self.num_rows < 2:
            return []
        grid = [["" for _ in range(self.num_cols)] for _ in range(self.num_rows)]
        for cell in self.cells:
            if cell.row < self.num_rows and cell.col < self.num_cols:
                grid[cell.row][cell.col] = cell.text
        headers = grid[0]
        return [{headers[j]: grid[i][j] for j in range(self.num_cols)}
                for i in range(1, self.num_rows)]


@dataclass
class FormField:
    key: str
    value: str
    field_type: str = "text"  # text, checkbox, signature, date
    confidence: float = 1.0
    key_bbox: Optional[BoundingBox] = None
    value_bbox: Optional[BoundingBox] = None


@dataclass
class DocumentImage:
    image_data: bytes
    format: str  # png, jpeg
    bbox: BoundingBox
    caption: Optional[str] = None
    description: Optional[str] = None
    alt_text: Optional[str] = None


@dataclass
class DocumentElement:
    """A single element extracted from a document."""
    element_type: ElementType
    content: str  # Text content or description
    bbox: BoundingBox
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)
    # For tables
    table: Optional[Table] = None
    # For images
    image: Optional[DocumentImage] = None
    # For form fields
    form_field: Optional[FormField] = None
    # Hierarchy
    level: int = 0  # Heading level (1-6) or nesting depth
    parent_id: Optional[str] = None

    @property
    def element_id(self) -> str:
        content_hash = hashlib.md5(self.content[:100].encode()).hexdigest()[:8]
        return f"{self.element_type.value}_{self.bbox.page}_{content_hash}"


@dataclass
class DocumentPage:
    page_number: int
    width: float
    height: float
    elements: list[DocumentElement] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class ParsedDocument:
    """Complete parsed document with all extracted elements."""
    source_path: str
    num_pages: int
    pages: list[DocumentPage]
    metadata: dict = field(default_factory=dict)
    tables: list[Table] = field(default_factory=list)
    images: list[DocumentImage] = field(default_factory=list)
    form_fields: list[FormField] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.raw_text for page in self.pages)

    def get_elements_by_type(self, element_type: ElementType) -> list[DocumentElement]:
        elements = []
        for page in self.pages:
            elements.extend(e for e in page.elements if e.element_type == element_type)
        return elements


# =============================================================================
# PDF Parser
# =============================================================================

class PDFParser:
    """
    PDF parser that extracts text, tables, images, and layout.
    Handles both digital-native and scanned PDFs.
    """

    def __init__(self, ocr_engine: Optional["OCREngine"] = None,
                 extract_images: bool = True,
                 extract_tables: bool = True):
        self.ocr_engine = ocr_engine
        self.extract_images = extract_images
        self.extract_tables = extract_tables

    def parse(self, pdf_path: str) -> ParsedDocument:
        """Parse a PDF file into structured elements."""
        logger.info(f"Parsing PDF: {pdf_path}")

        # Detect if scanned or digital
        is_scanned = self._detect_scanned(pdf_path)
        logger.info(f"Document type: {'scanned' if is_scanned else 'digital'}")

        if is_scanned:
            return self._parse_scanned(pdf_path)
        else:
            return self._parse_digital(pdf_path)

    def _detect_scanned(self, pdf_path: str) -> bool:
        """
        Detect if PDF is scanned (image-based) or digital (text-layer).
        Heuristic: if text extraction yields very little text relative to page count,
        it's likely scanned.
        """
        # In production, use PyMuPDF/pdfplumber to check text layer
        # Here we simulate the detection logic
        try:
            text_length = self._extract_raw_text_length(pdf_path)
            page_count = self._get_page_count(pdf_path)
            # Less than 100 chars per page suggests scanned
            avg_chars_per_page = text_length / max(page_count, 1)
            return avg_chars_per_page < 100
        except Exception:
            return False

    def _extract_raw_text_length(self, pdf_path: str) -> int:
        """Extract text using PDF text layer (PyMuPDF/pdfplumber in production)."""
        # Simulated - in production use fitz (PyMuPDF)
        # import fitz
        # doc = fitz.open(pdf_path)
        # return sum(len(page.get_text()) for page in doc)
        return 5000  # Placeholder

    def _get_page_count(self, pdf_path: str) -> int:
        # import fitz; return fitz.open(pdf_path).page_count
        return 10  # Placeholder

    def _parse_digital(self, pdf_path: str) -> ParsedDocument:
        """Parse a digital PDF with text layer."""
        logger.info("Using digital PDF extraction pipeline")

        pages = []
        all_tables = []
        all_images = []

        # In production: use PyMuPDF or pdfplumber
        # import fitz
        # doc = fitz.open(pdf_path)
        # for page_num, page in enumerate(doc):
        #     blocks = page.get_text("dict")["blocks"]
        #     ...

        num_pages = self._get_page_count(pdf_path)

        for page_num in range(num_pages):
            page_elements = []

            # Extract text blocks with positions
            text_blocks = self._extract_text_blocks(pdf_path, page_num)
            for block in text_blocks:
                element = DocumentElement(
                    element_type=self._classify_text_element(block),
                    content=block["text"],
                    bbox=BoundingBox(
                        x1=block["x1"], y1=block["y1"],
                        x2=block["x2"], y2=block["y2"],
                        page=page_num
                    ),
                    confidence=block.get("confidence", 1.0),
                    level=block.get("level", 0)
                )
                page_elements.append(element)

            # Extract tables
            if self.extract_tables:
                tables = self._extract_tables_from_page(pdf_path, page_num)
                for table in tables:
                    all_tables.append(table)
                    element = DocumentElement(
                        element_type=ElementType.TABLE,
                        content=table.to_markdown(),
                        bbox=table.bbox or BoundingBox(0, 0, 1, 1, page_num),
                        table=table
                    )
                    page_elements.append(element)

            # Extract images
            if self.extract_images:
                images = self._extract_images_from_page(pdf_path, page_num)
                for img in images:
                    all_images.append(img)
                    element = DocumentElement(
                        element_type=ElementType.IMAGE,
                        content=img.description or "[Image]",
                        bbox=img.bbox,
                        image=img
                    )
                    page_elements.append(element)

            # Sort elements by reading order (top-to-bottom, left-to-right)
            page_elements.sort(key=lambda e: (e.bbox.y1, e.bbox.x1))

            raw_text = "\n".join(e.content for e in page_elements
                                if e.element_type in (ElementType.TEXT, ElementType.HEADING))

            pages.append(DocumentPage(
                page_number=page_num,
                width=612,  # Standard letter width in points
                height=792,
                elements=page_elements,
                raw_text=raw_text
            ))

        # Extract document metadata
        metadata = self._extract_metadata(pdf_path)

        return ParsedDocument(
            source_path=pdf_path,
            num_pages=num_pages,
            pages=pages,
            metadata=metadata,
            tables=all_tables,
            images=all_images
        )

    def _parse_scanned(self, pdf_path: str) -> ParsedDocument:
        """Parse a scanned PDF using OCR."""
        if not self.ocr_engine:
            raise ValueError("OCR engine required for scanned PDFs")

        logger.info("Using OCR pipeline for scanned PDF")
        pages = []
        num_pages = self._get_page_count(pdf_path)

        for page_num in range(num_pages):
            # Render page to image
            page_image = self._render_page_to_image(pdf_path, page_num)

            # OCR the page
            ocr_result = self.ocr_engine.process_image(page_image, page_num)

            pages.append(DocumentPage(
                page_number=page_num,
                width=ocr_result.get("width", 612),
                height=ocr_result.get("height", 792),
                elements=ocr_result.get("elements", []),
                raw_text=ocr_result.get("text", "")
            ))

        return ParsedDocument(
            source_path=pdf_path,
            num_pages=num_pages,
            pages=pages,
            metadata={"ocr_applied": True}
        )

    def _classify_text_element(self, block: dict) -> ElementType:
        """Classify a text block by its visual properties."""
        font_size = block.get("font_size", 12)
        is_bold = block.get("is_bold", False)
        y_pos = block.get("y1", 0.5)

        # Headers/footers by position
        if y_pos < 0.05:
            return ElementType.HEADER
        if y_pos > 0.95:
            return ElementType.FOOTER

        # Headings by font size
        if font_size > 16 or (font_size > 13 and is_bold):
            return ElementType.HEADING

        # List detection
        text = block.get("text", "")
        if re.match(r'^[\s]*[•\-\*\d+\.]\s', text):
            return ElementType.LIST

        return ElementType.TEXT

    def _extract_text_blocks(self, pdf_path: str, page_num: int) -> list[dict]:
        """Extract text blocks with position info from a page."""
        # In production: use PyMuPDF page.get_text("dict")
        # Returns blocks with bbox, font info, text content
        return [
            {"text": "Sample heading", "x1": 0.1, "y1": 0.05, "x2": 0.9, "y2": 0.08,
             "font_size": 18, "is_bold": True, "level": 1},
            {"text": "Sample paragraph text...", "x1": 0.1, "y1": 0.12, "x2": 0.9, "y2": 0.20,
             "font_size": 12, "is_bold": False, "level": 0},
        ]

    def _extract_tables_from_page(self, pdf_path: str, page_num: int) -> list[Table]:
        """Extract tables from a page using table detection."""
        # In production: use pdfplumber, camelot, or custom model
        return []

    def _extract_images_from_page(self, pdf_path: str, page_num: int) -> list[DocumentImage]:
        """Extract embedded images from a page."""
        # In production: use PyMuPDF page.get_images()
        return []

    def _extract_metadata(self, pdf_path: str) -> dict:
        """Extract PDF metadata (title, author, dates, etc.)."""
        # In production: use PyMuPDF doc.metadata
        return {
            "title": "",
            "author": "",
            "creation_date": "",
            "modification_date": "",
            "page_count": self._get_page_count(pdf_path)
        }

    def _render_page_to_image(self, pdf_path: str, page_num: int) -> bytes:
        """Render a PDF page to an image for OCR."""
        # In production: use PyMuPDF page.get_pixmap()
        # import fitz
        # doc = fitz.open(pdf_path)
        # page = doc[page_num]
        # pix = page.get_pixmap(dpi=300)
        # return pix.tobytes("png")
        return b""


# =============================================================================
# OCR Engine
# =============================================================================

class OCREngine(ABC):
    """Abstract OCR engine interface."""

    @abstractmethod
    def process_image(self, image_data: bytes, page_num: int = 0) -> dict:
        """Process an image and return OCR results with layout."""
        pass


class TesseractOCR(OCREngine):
    """Tesseract-based OCR engine."""

    def __init__(self, language: str = "eng", dpi: int = 300,
                 psm: int = 3, oem: int = 3):
        """
        Args:
            language: Tesseract language code
            dpi: DPI for processing
            psm: Page segmentation mode (3=fully automatic)
            oem: OCR engine mode (3=default, LSTM)
        """
        self.language = language
        self.dpi = dpi
        self.psm = psm
        self.oem = oem

    def process_image(self, image_data: bytes, page_num: int = 0) -> dict:
        """
        Process image with Tesseract OCR.
        Returns structured output with text, bounding boxes, and confidence.
        """
        # In production:
        # import pytesseract
        # from PIL import Image
        # img = Image.open(io.BytesIO(image_data))
        # data = pytesseract.image_to_data(img, lang=self.language,
        #     config=f'--psm {self.psm} --oem {self.oem}',
        #     output_type=pytesseract.Output.DICT)

        # Process word-level results into blocks
        elements = self._group_words_into_elements([], page_num)
        full_text = " ".join(e.content for e in elements)

        return {
            "text": full_text,
            "elements": elements,
            "width": 2550,  # 8.5" * 300dpi
            "height": 3300,  # 11" * 300dpi
            "confidence": 0.92
        }

    def _group_words_into_elements(self, word_data: list, page_num: int) -> list[DocumentElement]:
        """Group OCR words into logical text blocks."""
        # In production: group by paragraph/block using Tesseract's hierarchy
        # (block_num, par_num, line_num, word_num)
        elements = []
        # ... grouping logic ...
        return elements


class AzureDocumentIntelligence(OCREngine):
    """
    Azure AI Document Intelligence (formerly Form Recognizer).
    Provides high-quality OCR + layout + table + form extraction.
    """

    def __init__(self, endpoint: str, api_key: str, model: str = "prebuilt-layout"):
        """
        Args:
            endpoint: Azure endpoint URL
            api_key: API key
            model: Model to use (prebuilt-layout, prebuilt-invoice, prebuilt-receipt, etc.)
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model

    def process_image(self, image_data: bytes, page_num: int = 0) -> dict:
        """Process with Azure Document Intelligence."""
        # In production:
        # from azure.ai.documentintelligence import DocumentIntelligenceClient
        # from azure.core.credentials import AzureKeyCredential
        #
        # client = DocumentIntelligenceClient(self.endpoint, AzureKeyCredential(self.api_key))
        # poller = client.begin_analyze_document(self.model, image_data)
        # result = poller.result()

        return self._transform_azure_result({}, page_num)

    def process_document(self, document_path: str) -> ParsedDocument:
        """Process entire document with Azure Document Intelligence."""
        # In production: send entire PDF to Azure
        # Handles multi-page documents natively with tables spanning pages

        # from azure.ai.documentintelligence import DocumentIntelligenceClient
        # client = DocumentIntelligenceClient(self.endpoint, AzureKeyCredential(self.api_key))
        # with open(document_path, "rb") as f:
        #     poller = client.begin_analyze_document(self.model, f.read())
        # result = poller.result()
        # return self._build_parsed_document(result, document_path)

        return ParsedDocument(
            source_path=document_path, num_pages=0, pages=[], metadata={}
        )

    def _transform_azure_result(self, result: dict, page_num: int) -> dict:
        """Transform Azure result into our standard format."""
        elements = []
        # Azure returns:
        # - result.pages[].lines[].content, .polygon
        # - result.tables[].cells[].content, .row_index, .column_index
        # - result.key_value_pairs[].key, .value
        # - result.paragraphs[].content, .bounding_regions
        return {"text": "", "elements": elements, "width": 0, "height": 0}

    def _build_parsed_document(self, result: dict, path: str) -> ParsedDocument:
        """Build full ParsedDocument from Azure response."""
        pass


# =============================================================================
# Table Extractor
# =============================================================================

class TableExtractor:
    """
    Extracts tables from document pages using multiple strategies.
    Handles bordered, borderless, and complex tables.
    """

    def __init__(self, strategy: str = "hybrid"):
        """
        Args:
            strategy: "rule_based", "ml_based", "hybrid"
        """
        self.strategy = strategy

    def extract_tables(self, page_image: bytes, page_num: int) -> list[Table]:
        """Extract all tables from a page image."""
        if self.strategy == "rule_based":
            return self._rule_based_extraction(page_image, page_num)
        elif self.strategy == "ml_based":
            return self._ml_based_extraction(page_image, page_num)
        else:
            return self._hybrid_extraction(page_image, page_num)

    def _rule_based_extraction(self, page_image: bytes, page_num: int) -> list[Table]:
        """
        Rule-based table extraction using line detection.
        Works well for bordered tables.
        """
        # Steps:
        # 1. Detect horizontal and vertical lines (Hough transform or morphological operations)
        # 2. Find intersections to get cell boundaries
        # 3. Extract text within each cell using OCR
        # 4. Build table structure from grid

        # In production with OpenCV:
        # import cv2
        # import numpy as np
        # img = cv2.imdecode(np.frombuffer(page_image, np.uint8), cv2.IMREAD_GRAYSCALE)
        # # Detect lines
        # horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        # vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        # horizontal_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel)
        # vertical_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel)
        # # Find intersections and build grid...

        return []

    def _ml_based_extraction(self, page_image: bytes, page_num: int) -> list[Table]:
        """
        ML-based table detection and structure recognition.
        Uses models like TableNet, DETR, or Table Transformer.
        """
        # Steps:
        # 1. Table detection (locate tables in page)
        # 2. Table structure recognition (identify rows/cols)
        # 3. Cell content extraction (OCR per cell)

        # In production:
        # from transformers import TableTransformerForObjectDetection
        # model = TableTransformerForObjectDetection.from_pretrained(
        #     "microsoft/table-transformer-detection"
        # )
        # # Detect tables, then use structure recognition model
        # structure_model = TableTransformerForObjectDetection.from_pretrained(
        #     "microsoft/table-transformer-structure-recognition"
        # )

        return []

    def _hybrid_extraction(self, page_image: bytes, page_num: int) -> list[Table]:
        """
        Hybrid approach: ML detection + rule-based structure extraction.
        Falls back to vision LLM for complex cases.
        """
        # 1. Try ML detection first
        tables = self._ml_based_extraction(page_image, page_num)

        # 2. Validate with rule-based checks
        validated = []
        for table in tables:
            if self._validate_table(table):
                validated.append(table)
            else:
                # 3. Fall back to vision LLM for complex tables
                reparsed = self._vision_llm_extraction(page_image, table.bbox, page_num)
                if reparsed:
                    validated.append(reparsed)

        return validated

    def _validate_table(self, table: Table) -> bool:
        """Validate extracted table structure."""
        if table.num_rows < 2 or table.num_cols < 2:
            return False
        # Check that cells don't overlap
        # Check that all rows have consistent column count
        # Check that content makes sense
        return True

    def _vision_llm_extraction(self, page_image: bytes,
                                bbox: Optional[BoundingBox],
                                page_num: int) -> Optional[Table]:
        """Use vision LLM (GPT-4V) to extract table structure."""
        # Crop image to table region, send to GPT-4V with prompt:
        # "Extract this table into a structured format with rows and columns..."
        # Parse LLM response into Table object
        return None


# =============================================================================
# Form Field Extractor
# =============================================================================

class FormFieldExtractor:
    """Extracts key-value pairs from forms."""

    def __init__(self, use_template_matching: bool = True):
        self.use_template_matching = use_template_matching
        self.templates: dict[str, list[dict]] = {}  # Form type -> expected fields

    def register_template(self, form_type: str, fields: list[dict]):
        """Register a form template for template matching."""
        self.templates[form_type] = fields

    def extract_fields(self, page_elements: list[DocumentElement],
                       form_type: Optional[str] = None) -> list[FormField]:
        """Extract form fields from page elements."""
        if form_type and form_type in self.templates:
            return self._template_based_extraction(page_elements, form_type)
        return self._generic_extraction(page_elements)

    def _template_based_extraction(self, elements: list[DocumentElement],
                                    form_type: str) -> list[FormField]:
        """Extract fields using a known template."""
        template = self.templates[form_type]
        fields = []

        for field_def in template:
            key = field_def["key"]
            expected_region = field_def.get("region")  # Expected bbox area

            # Find the key label in elements
            key_element = self._find_element_by_text(elements, key)
            if not key_element:
                continue

            # Find the value (typically to the right or below the key)
            value_element = self._find_value_near_key(elements, key_element, field_def)

            if value_element:
                fields.append(FormField(
                    key=key,
                    value=value_element.content.strip(),
                    field_type=field_def.get("type", "text"),
                    confidence=min(key_element.confidence, value_element.confidence),
                    key_bbox=key_element.bbox,
                    value_bbox=value_element.bbox
                ))

        return fields

    def _generic_extraction(self, elements: list[DocumentElement]) -> list[FormField]:
        """
        Generic key-value extraction without template.
        Uses spatial relationships and text patterns.
        """
        fields = []
        used_indices = set()

        for i, element in enumerate(elements):
            if i in used_indices:
                continue

            # Pattern: "Key:" or "Key :" followed by value
            match = re.match(r'^(.+?)\s*:\s*(.+)$', element.content)
            if match:
                fields.append(FormField(
                    key=match.group(1).strip(),
                    value=match.group(2).strip(),
                    key_bbox=element.bbox,
                    value_bbox=element.bbox,
                    confidence=element.confidence
                ))
                used_indices.add(i)
                continue

            # Pattern: Key label followed by value element to the right
            if self._looks_like_label(element.content):
                value_elem = self._find_value_to_right(elements, element, i)
                if value_elem:
                    idx = elements.index(value_elem)
                    used_indices.add(i)
                    used_indices.add(idx)
                    fields.append(FormField(
                        key=element.content.rstrip(":").strip(),
                        value=value_elem.content.strip(),
                        key_bbox=element.bbox,
                        value_bbox=value_elem.bbox
                    ))

        return fields

    def _looks_like_label(self, text: str) -> bool:
        """Heuristic: does this text look like a form field label?"""
        text = text.strip()
        if text.endswith(":"):
            return True
        if len(text.split()) <= 4 and text[0].isupper():
            return True
        label_patterns = ["name", "date", "address", "phone", "email",
                         "number", "amount", "total", "id"]
        return any(p in text.lower() for p in label_patterns)

    def _find_element_by_text(self, elements: list[DocumentElement],
                               text: str) -> Optional[DocumentElement]:
        """Find element containing specific text."""
        text_lower = text.lower()
        for elem in elements:
            if text_lower in elem.content.lower():
                return elem
        return None

    def _find_value_near_key(self, elements: list[DocumentElement],
                              key_element: DocumentElement,
                              field_def: dict) -> Optional[DocumentElement]:
        """Find value element near a key element."""
        direction = field_def.get("value_direction", "right")  # right, below
        key_bbox = key_element.bbox

        candidates = []
        for elem in elements:
            if elem == key_element:
                continue
            if elem.bbox.page != key_bbox.page:
                continue

            if direction == "right":
                # Value is to the right, same vertical band
                if (elem.bbox.x1 > key_bbox.x2 and
                    abs(elem.bbox.center[1] - key_bbox.center[1]) < key_bbox.height):
                    distance = elem.bbox.x1 - key_bbox.x2
                    candidates.append((distance, elem))
            elif direction == "below":
                # Value is below, same horizontal band
                if (elem.bbox.y1 > key_bbox.y2 and
                    abs(elem.bbox.center[0] - key_bbox.center[0]) < key_bbox.width * 0.5):
                    distance = elem.bbox.y1 - key_bbox.y2
                    candidates.append((distance, elem))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
        return None

    def _find_value_to_right(self, elements: list[DocumentElement],
                              key_element: DocumentElement,
                              key_index: int) -> Optional[DocumentElement]:
        """Find value element to the right of a key."""
        return self._find_value_near_key(elements, key_element,
                                          {"value_direction": "right"})


# =============================================================================
# Layout Analyzer
# =============================================================================

class LayoutAnalyzer:
    """Analyzes document layout: headings, paragraphs, lists, page structure."""

    def __init__(self):
        self.heading_size_threshold = 14  # Font size above this = heading
        self.column_gap_threshold = 0.05  # Normalized gap for column detection

    def analyze(self, page: DocumentPage) -> DocumentPage:
        """Analyze and enrich page layout."""
        # Detect columns
        columns = self._detect_columns(page.elements)

        # Classify elements
        for element in page.elements:
            if element.element_type == ElementType.TEXT:
                element.element_type = self._reclassify_element(element, page)

        # Build hierarchy
        self._build_hierarchy(page.elements)

        # Determine reading order
        page.elements = self._determine_reading_order(page.elements, columns)

        return page

    def _detect_columns(self, elements: list[DocumentElement]) -> list[tuple[float, float]]:
        """Detect column layout from element positions."""
        if not elements:
            return [(0.0, 1.0)]

        # Find gaps in horizontal positions
        x_positions = sorted(set(
            x for e in elements
            for x in [e.bbox.x1, e.bbox.x2]
        ))

        # Look for consistent vertical gaps
        gaps = []
        for i in range(len(x_positions) - 1):
            gap = x_positions[i + 1] - x_positions[i]
            if gap > self.column_gap_threshold:
                gaps.append((x_positions[i], x_positions[i + 1]))

        if not gaps:
            return [(0.0, 1.0)]  # Single column

        # Build column boundaries
        columns = []
        start = 0.0
        for gap_start, gap_end in gaps:
            columns.append((start, gap_start))
            start = gap_end
        columns.append((start, 1.0))

        return columns

    def _reclassify_element(self, element: DocumentElement,
                             page: DocumentPage) -> ElementType:
        """Reclassify text elements based on context."""
        content = element.content.strip()

        # Page numbers
        if re.match(r'^\d+$', content) and element.bbox.y1 > 0.9:
            return ElementType.PAGE_NUMBER

        # Headers (top of page, repeated text)
        if element.bbox.y1 < 0.05:
            return ElementType.HEADER

        # Footers
        if element.bbox.y1 > 0.92:
            return ElementType.FOOTER

        # Lists
        if re.match(r'^[\s]*[•\-\*]\s', content) or re.match(r'^\d+[\.\)]\s', content):
            return ElementType.LIST

        return element.element_type

    def _build_hierarchy(self, elements: list[DocumentElement]):
        """Build parent-child relationships based on headings."""
        heading_stack: list[DocumentElement] = []

        for element in elements:
            if element.element_type == ElementType.HEADING:
                # Pop headings of same or lower level
                while heading_stack and heading_stack[-1].level >= element.level:
                    heading_stack.pop()
                if heading_stack:
                    element.parent_id = heading_stack[-1].element_id
                heading_stack.append(element)
            else:
                if heading_stack:
                    element.parent_id = heading_stack[-1].element_id

    def _determine_reading_order(self, elements: list[DocumentElement],
                                  columns: list[tuple[float, float]]) -> list[DocumentElement]:
        """Determine correct reading order considering columns."""
        if len(columns) <= 1:
            # Single column: top to bottom
            return sorted(elements, key=lambda e: (e.bbox.y1, e.bbox.x1))

        # Multi-column: read each column top to bottom, left to right
        column_elements: list[list[DocumentElement]] = [[] for _ in columns]

        for element in elements:
            center_x = element.bbox.center[0]
            for i, (col_start, col_end) in enumerate(columns):
                if col_start <= center_x <= col_end:
                    column_elements[i].append(element)
                    break
            else:
                # Element spans columns - add to first overlapping
                column_elements[0].append(element)

        # Sort within each column by y position
        ordered = []
        for col_elems in column_elements:
            col_elems.sort(key=lambda e: e.bbox.y1)
            ordered.extend(col_elems)

        return ordered


# =============================================================================
# Chart Understanding
# =============================================================================

class ChartExtractor:
    """Extracts data and descriptions from charts/graphs."""

    def __init__(self, vision_model_client=None):
        self.vision_model = vision_model_client

    def extract_chart_data(self, image_data: bytes,
                            chart_type_hint: Optional[str] = None) -> dict:
        """
        Extract structured data from a chart image.
        Returns data series, labels, and description.
        """
        # Step 1: Classify chart type
        chart_type = chart_type_hint or self._classify_chart(image_data)

        # Step 2: Extract data using vision LLM
        extraction_prompt = self._build_extraction_prompt(chart_type)
        raw_result = self._call_vision_model(image_data, extraction_prompt)

        # Step 3: Parse and validate
        parsed = self._parse_extraction_result(raw_result, chart_type)

        return {
            "chart_type": chart_type,
            "title": parsed.get("title", ""),
            "x_axis_label": parsed.get("x_axis", ""),
            "y_axis_label": parsed.get("y_axis", ""),
            "data_series": parsed.get("series", []),
            "description": parsed.get("description", ""),
            "raw_data": parsed.get("data", [])
        }

    def _classify_chart(self, image_data: bytes) -> str:
        """Classify chart type from image."""
        prompt = """Classify this chart into one of: bar, line, pie, scatter, 
        area, histogram, box_plot, heatmap, other. Return only the type name."""
        result = self._call_vision_model(image_data, prompt)
        return result.strip().lower() if result else "other"

    def _build_extraction_prompt(self, chart_type: str) -> str:
        """Build extraction prompt based on chart type."""
        prompts = {
            "bar": """Extract data from this bar chart. Return JSON with:
                - title: chart title
                - x_axis: x-axis label
                - y_axis: y-axis label
                - series: [{name: series_name, data: [{category: str, value: number}]}]""",
            "line": """Extract data from this line chart. Return JSON with:
                - title: chart title
                - x_axis: x-axis label  
                - y_axis: y-axis label
                - series: [{name: series_name, data: [{x: value, y: value}]}]""",
            "pie": """Extract data from this pie chart. Return JSON with:
                - title: chart title
                - series: [{category: str, value: number, percentage: number}]""",
        }
        return prompts.get(chart_type, "Extract all data from this chart as structured JSON.")

    def _call_vision_model(self, image_data: bytes, prompt: str) -> str:
        """Call vision LLM with image and prompt."""
        if not self.vision_model:
            return ""
        # In production:
        # response = self.vision_model.chat.completions.create(
        #     model="gpt-4o",
        #     messages=[{
        #         "role": "user",
        #         "content": [
        #             {"type": "text", "text": prompt},
        #             {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{...}"}}
        #         ]
        #     }]
        # )
        # return response.choices[0].message.content
        return ""

    def _parse_extraction_result(self, raw: str, chart_type: str) -> dict:
        """Parse LLM output into structured data."""
        try:
            # Try to parse as JSON
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return {"description": raw}


# =============================================================================
# Document Metadata Extractor
# =============================================================================

class MetadataExtractor:
    """Extracts document-level metadata."""

    def extract(self, parsed_doc: ParsedDocument) -> dict:
        """Extract comprehensive metadata from parsed document."""
        metadata = {
            "title": self._extract_title(parsed_doc),
            "authors": self._extract_authors(parsed_doc),
            "date": self._extract_date(parsed_doc),
            "language": self._detect_language(parsed_doc),
            "document_type": self._classify_document(parsed_doc),
            "page_count": parsed_doc.num_pages,
            "word_count": self._count_words(parsed_doc),
            "has_tables": len(parsed_doc.tables) > 0,
            "has_images": len(parsed_doc.images) > 0,
            "table_count": len(parsed_doc.tables),
            "image_count": len(parsed_doc.images),
            "sections": self._extract_sections(parsed_doc),
        }
        return metadata

    def _extract_title(self, doc: ParsedDocument) -> str:
        """Extract document title (usually largest text on first page)."""
        if not doc.pages:
            return ""
        first_page = doc.pages[0]
        headings = [e for e in first_page.elements if e.element_type == ElementType.HEADING]
        if headings:
            # Return the first/largest heading
            headings.sort(key=lambda e: e.level)
            return headings[0].content
        return ""

    def _extract_authors(self, doc: ParsedDocument) -> list[str]:
        """Extract author names from document."""
        # Look for "Author:", "By:", or common patterns on first page
        if not doc.pages:
            return []
        text = doc.pages[0].raw_text
        patterns = [
            r'(?:Author|By|Written by|Prepared by)[:\s]+(.+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return [a.strip() for a in match.group(1).split(",")]
        return []

    def _extract_date(self, doc: ParsedDocument) -> Optional[str]:
        """Extract document date."""
        if doc.metadata.get("creation_date"):
            return doc.metadata["creation_date"]
        # Search for date patterns in first page
        if doc.pages:
            date_pattern = r'\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b|\b\w+ \d{1,2},? \d{4}\b'
            match = re.search(date_pattern, doc.pages[0].raw_text)
            if match:
                return match.group()
        return None

    def _detect_language(self, doc: ParsedDocument) -> str:
        """Detect document language."""
        # In production: use langdetect or fasttext
        # from langdetect import detect
        # return detect(doc.full_text[:1000])
        return "en"

    def _classify_document(self, doc: ParsedDocument) -> str:
        """Classify document type."""
        text = doc.full_text[:2000].lower()
        if any(w in text for w in ["invoice", "bill to", "amount due"]):
            return "invoice"
        if any(w in text for w in ["resume", "curriculum vitae", "experience"]):
            return "resume"
        if any(w in text for w in ["contract", "agreement", "parties"]):
            return "contract"
        if len(doc.tables) > 5:
            return "report"
        return "general"

    def _count_words(self, doc: ParsedDocument) -> int:
        return len(doc.full_text.split())

    def _extract_sections(self, doc: ParsedDocument) -> list[dict]:
        """Extract section hierarchy."""
        sections = []
        for page in doc.pages:
            for elem in page.elements:
                if elem.element_type == ElementType.HEADING:
                    sections.append({
                        "title": elem.content,
                        "level": elem.level,
                        "page": elem.bbox.page
                    })
        return sections


# =============================================================================
# Coordinate-Level Citation Builder
# =============================================================================

@dataclass
class Citation:
    """A citation pointing to a specific location in a source document."""
    text: str
    document_id: str
    page: int
    bounding_box: BoundingBox
    element_type: ElementType
    confidence: float
    context: str = ""  # Surrounding text for context

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "document_id": self.document_id,
            "page": self.page,
            "bounding_box": self.bounding_box.to_dict(),
            "element_type": self.element_type.value,
            "confidence": self.confidence,
            "context": self.context
        }


class CitationBuilder:
    """Builds coordinate-level citations from document elements."""

    def __init__(self):
        self.element_index: dict[str, list[DocumentElement]] = {}

    def index_document(self, doc_id: str, parsed_doc: ParsedDocument):
        """Index a document's elements for citation lookup."""
        elements = []
        for page in parsed_doc.pages:
            elements.extend(page.elements)
        self.element_index[doc_id] = elements

    def find_citation(self, query_text: str, doc_id: str) -> Optional[Citation]:
        """Find the best citation for a piece of text in a document."""
        elements = self.element_index.get(doc_id, [])
        if not elements:
            return None

        best_match = None
        best_score = 0.0

        for element in elements:
            score = self._compute_match_score(query_text, element.content)
            if score > best_score:
                best_score = score
                best_match = element

        if best_match and best_score > 0.5:
            return Citation(
                text=query_text,
                document_id=doc_id,
                page=best_match.bbox.page,
                bounding_box=best_match.bbox,
                element_type=best_match.element_type,
                confidence=best_score,
                context=best_match.content[:200]
            )
        return None

    def build_citations_for_answer(self, answer: str, doc_id: str,
                                    source_elements: list[DocumentElement]) -> list[Citation]:
        """Build citations for all claims in an answer."""
        # Split answer into sentences/claims
        sentences = re.split(r'[.!?]+', answer)
        citations = []

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
            citation = self._find_best_source(sentence, doc_id, source_elements)
            if citation:
                citations.append(citation)

        return citations

    def _find_best_source(self, claim: str, doc_id: str,
                           elements: list[DocumentElement]) -> Optional[Citation]:
        """Find the best source element for a claim."""
        best_match = None
        best_score = 0.0

        for element in elements:
            score = self._compute_match_score(claim, element.content)
            if score > best_score:
                best_score = score
                best_match = element

        if best_match and best_score > 0.3:
            return Citation(
                text=claim,
                document_id=doc_id,
                page=best_match.bbox.page,
                bounding_box=best_match.bbox,
                element_type=best_match.element_type,
                confidence=best_score,
                context=best_match.content[:200]
            )
        return None

    def _compute_match_score(self, query: str, content: str) -> float:
        """Compute text similarity score (simple token overlap)."""
        if not query or not content:
            return 0.0
        query_tokens = set(query.lower().split())
        content_tokens = set(content.lower().split())
        if not query_tokens:
            return 0.0
        overlap = query_tokens & content_tokens
        return len(overlap) / len(query_tokens)


# =============================================================================
# Multi-Format Document Router
# =============================================================================

class DocumentRouter:
    """Routes documents to appropriate parsers based on format."""

    def __init__(self):
        self.parsers: dict[str, any] = {}
        self.ocr_engine: Optional[OCREngine] = None
        self.pdf_parser: Optional[PDFParser] = None

    def configure(self, ocr_engine: Optional[OCREngine] = None):
        """Configure the router with engines."""
        self.ocr_engine = ocr_engine
        self.pdf_parser = PDFParser(ocr_engine=ocr_engine)

    def process(self, file_path: str) -> ParsedDocument:
        """Process any supported document format."""
        extension = Path(file_path).suffix.lower()

        router_map = {
            ".pdf": self._process_pdf,
            ".docx": self._process_docx,
            ".doc": self._process_doc,
            ".xlsx": self._process_xlsx,
            ".xls": self._process_xls,
            ".pptx": self._process_pptx,
            ".html": self._process_html,
            ".htm": self._process_html,
            ".png": self._process_image,
            ".jpg": self._process_image,
            ".jpeg": self._process_image,
            ".tiff": self._process_image,
            ".tif": self._process_image,
            ".txt": self._process_text,
            ".md": self._process_text,
            ".csv": self._process_csv,
        }

        handler = router_map.get(extension)
        if not handler:
            raise ValueError(f"Unsupported format: {extension}")

        logger.info(f"Processing {file_path} with {handler.__name__}")
        return handler(file_path)

    def _process_pdf(self, path: str) -> ParsedDocument:
        return self.pdf_parser.parse(path)

    def _process_docx(self, path: str) -> ParsedDocument:
        """Process DOCX using python-docx."""
        # In production:
        # from docx import Document
        # doc = Document(path)
        # Extract paragraphs, tables, images with style info
        return ParsedDocument(source_path=path, num_pages=1, pages=[])

    def _process_doc(self, path: str) -> ParsedDocument:
        """Process legacy DOC format (convert to DOCX first)."""
        # Use libreoffice for conversion: soffice --convert-to docx
        return ParsedDocument(source_path=path, num_pages=1, pages=[])

    def _process_xlsx(self, path: str) -> ParsedDocument:
        """Process Excel files."""
        # In production: use openpyxl
        # Each sheet becomes a page, each sheet is a table
        return ParsedDocument(source_path=path, num_pages=1, pages=[])

    def _process_xls(self, path: str) -> ParsedDocument:
        return self._process_xlsx(path)

    def _process_pptx(self, path: str) -> ParsedDocument:
        """Process PowerPoint files."""
        # In production: use python-pptx
        # Each slide becomes a page
        return ParsedDocument(source_path=path, num_pages=1, pages=[])

    def _process_html(self, path: str) -> ParsedDocument:
        """Process HTML files."""
        # In production: use BeautifulSoup
        return ParsedDocument(source_path=path, num_pages=1, pages=[])

    def _process_image(self, path: str) -> ParsedDocument:
        """Process standalone images with OCR."""
        if not self.ocr_engine:
            raise ValueError("OCR engine required for image processing")
        with open(path, "rb") as f:
            image_data = f.read()
        result = self.ocr_engine.process_image(image_data)
        page = DocumentPage(
            page_number=0,
            width=result.get("width", 0),
            height=result.get("height", 0),
            elements=result.get("elements", []),
            raw_text=result.get("text", "")
        )
        return ParsedDocument(source_path=path, num_pages=1, pages=[page])

    def _process_text(self, path: str) -> ParsedDocument:
        """Process plain text/markdown files."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        element = DocumentElement(
            element_type=ElementType.TEXT,
            content=content,
            bbox=BoundingBox(0, 0, 1, 1, 0)
        )
        page = DocumentPage(page_number=0, width=1, height=1,
                           elements=[element], raw_text=content)
        return ParsedDocument(source_path=path, num_pages=1, pages=[page])

    def _process_csv(self, path: str) -> ParsedDocument:
        """Process CSV as a table."""
        import csv
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            return ParsedDocument(source_path=path, num_pages=1, pages=[])

        cells = []
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                cells.append(TableCell(text=val, row=i, col=j, is_header=(i == 0)))

        table = Table(cells=cells, num_rows=len(rows), num_cols=len(rows[0]) if rows else 0)
        element = DocumentElement(
            element_type=ElementType.TABLE,
            content=table.to_markdown(),
            bbox=BoundingBox(0, 0, 1, 1, 0),
            table=table
        )
        page = DocumentPage(page_number=0, width=1, height=1, elements=[element],
                           raw_text=table.to_markdown())
        return ParsedDocument(source_path=path, num_pages=1, pages=[page], tables=[table])


# =============================================================================
# Invoice Processor (Specialized)
# =============================================================================

@dataclass
class InvoiceLineItem:
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None


@dataclass
class Invoice:
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    customer_name: Optional[str] = None
    customer_address: Optional[str] = None
    line_items: list[InvoiceLineItem] = field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    currency: str = "USD"
    confidence: float = 0.0


class InvoiceProcessor:
    """Specialized processor for invoice documents."""

    def __init__(self, form_extractor: FormFieldExtractor,
                 table_extractor: TableExtractor):
        self.form_extractor = form_extractor
        self.table_extractor = table_extractor

    def process(self, parsed_doc: ParsedDocument) -> Invoice:
        """Extract structured invoice data from parsed document."""
        invoice = Invoice()

        # Extract header fields
        all_elements = []
        for page in parsed_doc.pages:
            all_elements.extend(page.elements)

        fields = self.form_extractor.extract_fields(all_elements)
        field_map = {f.key.lower(): f.value for f in fields}

        # Map fields to invoice
        invoice.invoice_number = self._find_field(field_map,
            ["invoice number", "invoice no", "invoice #", "inv no"])
        invoice.invoice_date = self._find_field(field_map,
            ["invoice date", "date", "issue date"])
        invoice.due_date = self._find_field(field_map,
            ["due date", "payment due", "due by"])
        invoice.vendor_name = self._find_field(field_map,
            ["from", "vendor", "seller", "company"])
        invoice.customer_name = self._find_field(field_map,
            ["to", "bill to", "customer", "buyer"])

        # Extract line items from tables
        if parsed_doc.tables:
            invoice.line_items = self._extract_line_items(parsed_doc.tables[0])

        # Extract totals
        invoice.subtotal = self._parse_currency(
            self._find_field(field_map, ["subtotal", "sub total", "sub-total"]))
        invoice.tax = self._parse_currency(
            self._find_field(field_map, ["tax", "vat", "gst"]))
        invoice.total = self._parse_currency(
            self._find_field(field_map, ["total", "amount due", "total due", "grand total"]))

        # Validate
        invoice.confidence = self._calculate_confidence(invoice)

        return invoice

    def _find_field(self, field_map: dict, keys: list[str]) -> Optional[str]:
        for key in keys:
            if key in field_map:
                return field_map[key]
        return None

    def _extract_line_items(self, table: Table) -> list[InvoiceLineItem]:
        """Extract line items from an invoice table."""
        items = []
        rows = table.to_dict()
        for row in rows:
            item = InvoiceLineItem(
                description=row.get("description", row.get("item", "")),
                quantity=self._parse_number(row.get("quantity", row.get("qty"))),
                unit_price=self._parse_currency(row.get("unit price", row.get("price"))),
                total=self._parse_currency(row.get("total", row.get("amount")))
            )
            if item.description:
                items.append(item)
        return items

    def _parse_currency(self, value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        cleaned = re.sub(r'[^\d.]', '', value)
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _parse_number(self, value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _calculate_confidence(self, invoice: Invoice) -> float:
        """Calculate confidence score based on extracted fields."""
        score = 0.0
        total_fields = 8
        if invoice.invoice_number: score += 1
        if invoice.invoice_date: score += 1
        if invoice.vendor_name: score += 1
        if invoice.customer_name: score += 1
        if invoice.line_items: score += 1
        if invoice.total: score += 1
        if invoice.subtotal: score += 1
        if invoice.tax: score += 0.5
        # Validate math
        if invoice.subtotal and invoice.tax and invoice.total:
            expected = invoice.subtotal + invoice.tax
            if abs(expected - invoice.total) < 0.01:
                score += 0.5
        return score / total_fields


# =============================================================================
# Main Pipeline
# =============================================================================

class DocumentIntelligencePipeline:
    """End-to-end document intelligence pipeline."""

    def __init__(self, config: Optional[dict] = None):
        config = config or {}
        self.router = DocumentRouter()
        self.layout_analyzer = LayoutAnalyzer()
        self.metadata_extractor = MetadataExtractor()
        self.citation_builder = CitationBuilder()
        self.table_extractor = TableExtractor(strategy=config.get("table_strategy", "hybrid"))
        self.form_extractor = FormFieldExtractor()
        self.chart_extractor = ChartExtractor()

        # Configure OCR
        ocr_type = config.get("ocr", "tesseract")
        if ocr_type == "azure":
            self.ocr_engine = AzureDocumentIntelligence(
                endpoint=config.get("azure_endpoint", ""),
                api_key=config.get("azure_key", "")
            )
        else:
            self.ocr_engine = TesseractOCR()

        self.router.configure(ocr_engine=self.ocr_engine)

    def process(self, file_path: str) -> dict:
        """
        Process a document end-to-end.
        Returns structured output with all extracted information.
        """
        logger.info(f"Starting document intelligence pipeline for: {file_path}")

        # Step 1: Parse document
        parsed_doc = self.router.process(file_path)

        # Step 2: Analyze layout
        for page in parsed_doc.pages:
            self.layout_analyzer.analyze(page)

        # Step 3: Extract metadata
        metadata = self.metadata_extractor.extract(parsed_doc)
        parsed_doc.metadata.update(metadata)

        # Step 4: Index for citations
        doc_id = hashlib.md5(file_path.encode()).hexdigest()
        self.citation_builder.index_document(doc_id, parsed_doc)

        # Step 5: Build output
        output = {
            "document_id": doc_id,
            "source": file_path,
            "metadata": metadata,
            "pages": [
                {
                    "page_number": page.page_number,
                    "elements": [
                        {
                            "type": elem.element_type.value,
                            "content": elem.content[:500],
                            "bbox": elem.bbox.to_dict(),
                            "confidence": elem.confidence,
                        }
                        for elem in page.elements
                    ],
                    "text": page.raw_text
                }
                for page in parsed_doc.pages
            ],
            "tables": [t.to_dict() for t in parsed_doc.tables],
            "form_fields": [
                {"key": f.key, "value": f.value, "confidence": f.confidence}
                for f in parsed_doc.form_fields
            ],
            "full_text": parsed_doc.full_text
        }

        logger.info(f"Pipeline complete. {parsed_doc.num_pages} pages, "
                    f"{len(parsed_doc.tables)} tables, {len(parsed_doc.images)} images")

        return output


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    # Configure pipeline
    pipeline = DocumentIntelligencePipeline(config={
        "ocr": "tesseract",
        "table_strategy": "hybrid"
    })

    # Process a document
    # result = pipeline.process("sample_invoice.pdf")

    # Access structured data
    # print(f"Document type: {result['metadata']['document_type']}")
    # print(f"Tables found: {len(result['tables'])}")
    # print(f"Total pages: {result['metadata']['page_count']}")

    # Build citations
    # citation = pipeline.citation_builder.find_citation(
    #     "Revenue grew 15%", doc_id="abc123"
    # )
    # if citation:
    #     print(f"Found at page {citation.page}, bbox: {citation.bounding_box}")

    print("Document Intelligence Pipeline ready.")
