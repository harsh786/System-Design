"""
Document Chunker - Splits documents into chunks for embedding and retrieval.
"""

from dataclasses import dataclass

from src.ingestion.markdown_parser import ParsedDocument


@dataclass
class DocumentChunk:
    """A chunk of a document ready for embedding."""
    chunk_id: str
    content: str
    metadata: dict  # source_type, component, technology, etc.


class DocumentChunker:
    """
    Intelligent document chunking that preserves semantic boundaries.
    Uses different strategies based on document type.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_documents(
        self, documents: list[ParsedDocument]
    ) -> list[DocumentChunk]:
        """Chunk a list of documents using type-appropriate strategies."""
        all_chunks = []
        for doc in documents:
            chunks = self._chunk_document(doc)
            all_chunks.extend(chunks)
        return all_chunks

    def _chunk_document(self, doc: ParsedDocument) -> list[DocumentChunk]:
        """Chunk a single document based on its type."""
        if doc.doc_type in ("hld", "lld", "db_design"):
            return self._chunk_by_sections(doc)
        else:
            return self._chunk_by_size(doc)

    def _chunk_by_sections(self, doc: ParsedDocument) -> list[DocumentChunk]:
        """
        Chunk by markdown sections. Each top-level section becomes a chunk.
        If a section is too large, it's split further.
        """
        chunks = []
        chunk_idx = 0

        # Add a document-level summary chunk
        summary = f"# {doc.title}\n\nDocument type: {doc.doc_type}\n"
        summary += f"Technologies: {', '.join(doc.technologies)}\n"
        summary += f"Components: {', '.join(doc.components)}\n"

        chunks.append(DocumentChunk(
            chunk_id=f"{doc.file_path}::summary",
            content=summary,
            metadata={
                "source_type": doc.doc_type,
                "file_path": doc.file_path,
                "title": doc.title,
                "chunk_type": "summary",
                "technologies": ", ".join(doc.technologies),
                "components": ", ".join(doc.components),
            },
        ))

        # Chunk each section
        for section in doc.sections:
            section_content = f"## {section['heading']}\n{section['content']}"

            if len(section_content) <= self.chunk_size:
                chunks.append(DocumentChunk(
                    chunk_id=f"{doc.file_path}::section::{chunk_idx}",
                    content=section_content,
                    metadata={
                        "source_type": doc.doc_type,
                        "file_path": doc.file_path,
                        "title": doc.title,
                        "section": section["heading"],
                        "chunk_type": "section",
                        "technologies": ", ".join(doc.technologies),
                    },
                ))
                chunk_idx += 1
            else:
                # Split large sections
                sub_chunks = self._split_text(
                    section_content,
                    prefix=f"[From section: {section['heading']}]\n",
                )
                for sub_content in sub_chunks:
                    chunks.append(DocumentChunk(
                        chunk_id=f"{doc.file_path}::section::{chunk_idx}",
                        content=sub_content,
                        metadata={
                            "source_type": doc.doc_type,
                            "file_path": doc.file_path,
                            "title": doc.title,
                            "section": section["heading"],
                            "chunk_type": "section_part",
                            "technologies": ", ".join(doc.technologies),
                        },
                    ))
                    chunk_idx += 1

        return chunks

    def _chunk_by_size(self, doc: ParsedDocument) -> list[DocumentChunk]:
        """Simple size-based chunking with overlap."""
        chunks = []
        texts = self._split_text(doc.content)

        for idx, text in enumerate(texts):
            chunks.append(DocumentChunk(
                chunk_id=f"{doc.file_path}::chunk::{idx}",
                content=text,
                metadata={
                    "source_type": doc.doc_type,
                    "file_path": doc.file_path,
                    "title": doc.title,
                    "chunk_type": "text",
                    "technologies": ", ".join(doc.technologies),
                },
            ))

        return chunks

    def _split_text(
        self, text: str, prefix: str = ""
    ) -> list[str]:
        """Split text into chunks of approximately chunk_size with overlap."""
        if len(text) <= self.chunk_size:
            return [prefix + text]

        chunks = []
        # Try to split on paragraph boundaries
        paragraphs = text.split("\n\n")
        current_chunk = prefix
        
        for para in paragraphs:
            if len(current_chunk) + len(para) > self.chunk_size:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                # Start new chunk with overlap from end of previous
                overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                current_chunk = overlap_text + "\n\n" + para
            else:
                current_chunk += "\n\n" + para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [prefix + text]
