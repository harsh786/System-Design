# Multimodal AI - Architecture Diagrams

## 1. Document Intelligence Pipeline

```mermaid
flowchart TD
    INPUT[Input Document] --> DETECT{Format Detection}
    DETECT -->|PDF| PDF_CHECK{Has Text Layer?}
    DETECT -->|Image| OCR[OCR Engine]
    DETECT -->|DOCX/PPTX| NATIVE[Native Parser]
    
    PDF_CHECK -->|Yes - Digital| TEXT_EXTRACT[Direct Text Extraction]
    PDF_CHECK -->|No - Scanned| RENDER[Render to Images]
    RENDER --> OCR
    
    TEXT_EXTRACT --> LAYOUT[Layout Analysis]
    OCR --> LAYOUT
    NATIVE --> LAYOUT
    
    LAYOUT --> ELEMENTS{Element Classification}
    ELEMENTS --> HEADINGS[Headings & Sections]
    ELEMENTS --> PARAGRAPHS[Text Paragraphs]
    ELEMENTS --> TABLES_E[Tables]
    ELEMENTS --> IMAGES_E[Images]
    ELEMENTS --> FORMS[Form Fields]
    ELEMENTS --> CHARTS[Charts]
    
    TABLES_E --> TABLE_EXTRACT[Table Structure Recognition]
    IMAGES_E --> IMG_DESC[Image Description]
    FORMS --> FORM_EXTRACT[Key-Value Extraction]
    CHARTS --> CHART_DATA[Data Extraction]
    
    HEADINGS --> STRUCTURE[Document Structure Tree]
    PARAGRAPHS --> STRUCTURE
    TABLE_EXTRACT --> STRUCTURE
    IMG_DESC --> STRUCTURE
    FORM_EXTRACT --> STRUCTURE
    CHART_DATA --> STRUCTURE
    
    STRUCTURE --> METADATA[Metadata Enrichment]
    METADATA --> CITATIONS[Coordinate Citation Map]
    CITATIONS --> OUTPUT[Structured Output<br/>JSON + Markdown + Chunks]
```

## 2. Multimodal RAG Architecture

```mermaid
flowchart TD
    subgraph Ingestion["Document Ingestion"]
        DOC[Documents] --> PARSE[Document Parser]
        PARSE --> TEXT_C[Text Chunks]
        PARSE --> IMG_C[Images]
        PARSE --> TBL_C[Tables]
        PARSE --> CHT_C[Charts]
    end
    
    subgraph Embedding["Multimodal Embedding"]
        TEXT_C --> TEXT_EMB[Text Embedder<br/>text-embedding-3-large]
        IMG_C --> IMG_EMB[Image Embedder<br/>CLIP/SigLIP]
        TBL_C --> TBL_EMB[Table Embedder<br/>Linearized Text]
        CHT_C --> CHT_EMB[Chart Embedder<br/>Description-based]
    end
    
    subgraph Index["Multimodal Index"]
        TEXT_EMB --> TEXT_IDX[(Text Index)]
        IMG_EMB --> IMG_IDX[(Image Index)]
        TBL_EMB --> TBL_IDX[(Table Index)]
        CHT_EMB --> CHT_IDX[(Chart Index)]
    end
    
    subgraph Retrieval["Query & Retrieval"]
        QUERY[User Query] --> Q_EMB[Query Embedding]
        Q_EMB --> TEXT_SEARCH[Text Search]
        Q_EMB --> IMG_SEARCH[Image Search<br/>Cross-modal CLIP]
        Q_EMB --> TBL_SEARCH[Table Search]
        
        TEXT_IDX --> TEXT_SEARCH
        IMG_IDX --> IMG_SEARCH
        TBL_IDX --> TBL_SEARCH
        
        TEXT_SEARCH --> FUSION[Score Fusion<br/>RRF / Weighted]
        IMG_SEARCH --> FUSION
        TBL_SEARCH --> FUSION
    end
    
    subgraph Generation["Answer Generation"]
        FUSION --> ASSEMBLE[Context Assembly]
        ASSEMBLE --> VLM[Vision-Language Model<br/>GPT-4o / Claude]
        VLM --> ANSWER[Answer + Citations]
    end
```

## 3. PDF Parsing Flow

```mermaid
flowchart LR
    subgraph Input
        PDF[PDF File]
    end
    
    subgraph Detection
        PDF --> META[Read Metadata]
        PDF --> CHECK[Check Text Layer]
        CHECK -->|Text found| DIGITAL
        CHECK -->|No text| SCANNED
    end
    
    subgraph DIGITAL[Digital Path]
        D1[Extract Text Blocks] --> D2[Get Font Info]
        D2 --> D3[Get Positions/BBox]
        D3 --> D4[Extract Embedded Images]
        D4 --> D5[Detect Tables via Lines]
    end
    
    subgraph SCANNED[Scanned Path]
        S1[Render Page @ 300 DPI] --> S2[Preprocess<br/>Deskew, Denoise]
        S2 --> S3[OCR with Tesseract/Azure]
        S3 --> S4[Word-level BBoxes]
        S4 --> S5[Block Grouping]
    end
    
    subgraph PostProcess[Post-Processing]
        D5 --> PP1[Reading Order Sort]
        S5 --> PP1
        PP1 --> PP2[Classify Elements]
        PP2 --> PP3[Build Hierarchy]
        PP3 --> PP4[Cross-page Merge]
        PP4 --> PP5[Coordinate Map]
    end
    
    subgraph Output
        PP5 --> OUT1[Structured JSON]
        PP5 --> OUT2[Markdown]
        PP5 --> OUT3[Layout Chunks]
    end
```

## 4. Table Extraction Process

```mermaid
flowchart TD
    PAGE[Page Image/Region] --> DETECT[Table Detection]
    
    DETECT --> BORDERED{Table Type?}
    BORDERED -->|Bordered| RULE[Rule-Based Extraction]
    BORDERED -->|Borderless| ML[ML-Based Extraction]
    BORDERED -->|Complex| VISION[Vision LLM Extraction]
    
    subgraph RULE[Rule-Based Path]
        R1[Line Detection<br/>Hough Transform] --> R2[Find Intersections]
        R2 --> R3[Build Cell Grid]
        R3 --> R4[OCR per Cell]
    end
    
    subgraph ML[ML-Based Path]
        M1[Table Transformer<br/>Detection] --> M2[Structure Recognition<br/>Row/Col Detection]
        M2 --> M3[Cell Assignment]
        M3 --> M4[OCR per Cell]
    end
    
    subgraph VISION[Vision LLM Path]
        V1[Crop Table Region] --> V2[Send to GPT-4o]
        V2 --> V3[Parse JSON Response]
    end
    
    R4 --> VALIDATE[Validate Structure]
    M4 --> VALIDATE
    V3 --> VALIDATE
    
    VALIDATE --> MERGE{Merged Cells?}
    MERGE -->|Yes| RESOLVE[Resolve Spans]
    MERGE -->|No| FORMAT
    RESOLVE --> FORMAT[Format Output]
    
    FORMAT --> JSON_OUT[JSON]
    FORMAT --> MD_OUT[Markdown]
    FORMAT --> CSV_OUT[CSV]
    FORMAT --> HTML_OUT[HTML Table]
```

## 5. Layout-Aware Chunking

```mermaid
flowchart TD
    ELEMENTS[Document Elements] --> CLEAN[Remove Repeated<br/>Headers/Footers]
    
    CLEAN --> CROSS[Handle Cross-Page<br/>Elements]
    CROSS --> ASSOC[Associate Figures<br/>with Captions]
    ASSOC --> GROUP_LIST[Group List Items]
    
    GROUP_LIST --> HIERARCHY[Build Section<br/>Hierarchy]
    
    HIERARCHY --> CHUNK{Chunking Engine}
    
    CHUNK --> RULE1[Rule: Never split tables]
    CHUNK --> RULE2[Rule: Keep figures+captions]
    CHUNK --> RULE3[Rule: Respect section boundaries]
    CHUNK --> RULE4[Rule: Max token limit]
    CHUNK --> RULE5[Rule: Overlap for continuity]
    
    RULE1 --> VALIDATE[Quality Validation]
    RULE2 --> VALIDATE
    RULE3 --> VALIDATE
    RULE4 --> VALIDATE
    RULE5 --> VALIDATE
    
    VALIDATE --> FIX{Valid?}
    FIX -->|Yes| ENRICH[Metadata Enrichment]
    FIX -->|Too Short| MERGE_ADJ[Merge with Adjacent]
    FIX -->|Too Long| SPLIT_SAFE[Split at Paragraph]
    FIX -->|Empty| DISCARD[Discard]
    
    MERGE_ADJ --> ENRICH
    SPLIT_SAFE --> ENRICH
    
    ENRICH --> OUTPUT[Layout-Aware Chunks<br/>with Section Context,<br/>BBoxes, Element Types]
```

## 6. Audio Processing Pipeline

```mermaid
flowchart TD
    AUDIO[Audio Input] --> QUALITY[Quality Analysis]
    QUALITY --> GOOD{Quality OK?}
    GOOD -->|Poor| PREPROCESS[Noise Reduction<br/>Normalization]
    GOOD -->|Good| LANG_DETECT[Language Detection]
    PREPROCESS --> LANG_DETECT
    
    LANG_DETECT --> TRANSCRIBE[Speech-to-Text<br/>Whisper / Azure Speech]
    
    TRANSCRIBE --> WORDS[Word-Level Timestamps]
    TRANSCRIBE --> SEGMENTS[Sentence Segments]
    
    AUDIO --> DIARIZE[Speaker Diarization<br/>pyannote]
    DIARIZE --> SPEAKER_MAP[Speaker Timeline]
    
    SEGMENTS --> ASSIGN[Assign Speakers<br/>to Segments]
    SPEAKER_MAP --> ASSIGN
    
    ASSIGN --> FULL_TRANSCRIPT[Full Transcript<br/>with Speakers]
    
    FULL_TRANSCRIPT --> TOPIC_SEG[Topic Segmentation]
    FULL_TRANSCRIPT --> SUMMARIZE[Meeting Summarization<br/>LLM]
    FULL_TRANSCRIPT --> CHUNK_AUDIO[Audio Chunking]
    
    SUMMARIZE --> SUMMARY[Structured Summary]
    SUMMARY --> DECISIONS[Key Decisions]
    SUMMARY --> ACTIONS[Action Items]
    SUMMARY --> TOPICS[Topic List]
    
    CHUNK_AUDIO --> EMBED_AUDIO[Chunk Embedding]
    EMBED_AUDIO --> AUDIO_INDEX[(Audio Search Index)]
```

## 7. Multimodal Embedding and Retrieval

```mermaid
flowchart LR
    subgraph TextPath["Text Embedding Space"]
        T_IN[Text Chunk] --> T_ENC[Text Encoder<br/>Ada-002 / E5]
        T_ENC --> T_VEC[1536-dim Vector]
    end
    
    subgraph ImagePath["Image Embedding Space"]
        I_IN[Image] --> I_ENC[CLIP Image Encoder<br/>ViT-L/14]
        I_ENC --> I_VEC[768-dim Vector]
    end
    
    subgraph CrossModal["Cross-Modal Alignment"]
        Q[Text Query] --> Q_TEXT[Text Encoder]
        Q --> Q_CLIP[CLIP Text Encoder]
        Q_TEXT --> SEARCH_T[Search Text Index]
        Q_CLIP --> SEARCH_I[Search Image Index]
    end
    
    subgraph Fusion["Score Fusion"]
        SEARCH_T --> NORM_T[Normalize Scores]
        SEARCH_I --> NORM_I[Normalize Scores]
        NORM_T --> RRF[Reciprocal Rank Fusion]
        NORM_I --> RRF
        RRF --> TOP_K[Top-K Results<br/>Mixed Modalities]
    end
    
    T_VEC --> SEARCH_T
    I_VEC --> SEARCH_I
```

## 8. Coordinate-Level Citation Flow

```mermaid
flowchart TD
    subgraph Ingestion["Document Ingestion"]
        DOC[Document] --> PARSE[Parse with BBoxes]
        PARSE --> ELEMENTS[Elements with<br/>Page + Coordinates]
        ELEMENTS --> INDEX[Citation Index<br/>Element → BBox Map]
    end
    
    subgraph Query["Query Processing"]
        QUESTION[User Question] --> RAG[Multimodal RAG]
        RAG --> ANSWER[Generated Answer]
        RAG --> SOURCES[Source Chunks Used]
    end
    
    subgraph CitationBuild["Citation Construction"]
        ANSWER --> SPLIT[Split into Claims]
        SPLIT --> MATCH[Match Claims to<br/>Source Elements]
        SOURCES --> MATCH
        INDEX --> MATCH
        
        MATCH --> CITE[Build Citations]
        CITE --> COORD[Coordinate Citation<br/>Doc + Page + BBox]
    end
    
    subgraph Render["Citation Rendering"]
        COORD --> HIGHLIGHT[Highlight in PDF Viewer]
        COORD --> SNIPPET[Source Snippet Display]
        COORD --> VERIFY[Human Verification UI]
    end
    
    HIGHLIGHT --> USER[User sees exact source<br/>location highlighted]
```

## 9. End-to-End System Architecture

```mermaid
flowchart TD
    subgraph Sources["Document Sources"]
        S1[PDFs]
        S2[Images]
        S3[Audio/Video]
        S4[Office Docs]
    end
    
    subgraph Processing["Processing Layer"]
        S1 --> DOC_INT[Document Intelligence]
        S2 --> DOC_INT
        S3 --> AUDIO_P[Audio Processing]
        S4 --> DOC_INT
        
        DOC_INT --> LAYOUT[Layout-Aware Chunking]
        AUDIO_P --> AUDIO_CHUNK[Audio Chunking]
    end
    
    subgraph Indexing["Indexing Layer"]
        LAYOUT --> MM_EMB[Multimodal Embedding]
        AUDIO_CHUNK --> MM_EMB
        MM_EMB --> VECTOR_DB[(Vector Database<br/>Pinecone/Weaviate)]
        MM_EMB --> META_DB[(Metadata Store<br/>PostgreSQL)]
        MM_EMB --> BLOB[(Blob Storage<br/>Images/Audio)]
    end
    
    subgraph Query["Query Layer"]
        USER[User Query] --> RETRIEVAL[Multimodal Retrieval]
        VECTOR_DB --> RETRIEVAL
        META_DB --> RETRIEVAL
        RETRIEVAL --> CONTEXT[Context Assembly]
        BLOB --> CONTEXT
        CONTEXT --> VLM[Vision-Language Model]
        VLM --> RESPONSE[Answer + Citations]
    end
    
    subgraph Verification["Trust Layer"]
        RESPONSE --> CITE_BUILD[Citation Builder]
        META_DB --> CITE_BUILD
        CITE_BUILD --> HIGHLIGHT[Source Highlighting]
        HIGHLIGHT --> USER_VIEW[User Verification]
    end
```
