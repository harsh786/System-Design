# LLM Fundamentals — Architecture Diagrams

## 1. Transformer Architecture (Simplified)

```mermaid
graph TB
    subgraph Input
        A[Raw Text] --> B[Tokenizer]
        B --> C[Token Embeddings]
        C --> D[+ Positional Encoding]
    end

    subgraph "Transformer Block ×N"
        D --> E[Multi-Head Self-Attention]
        E --> F[Add & Layer Norm]
        F --> G[Feed-Forward Network]
        G --> H[Add & Layer Norm]
    end

    subgraph "Multi-Head Attention Detail"
        I[Input] --> J[Q = W_q × Input]
        I --> K[K = W_k × Input]
        I --> L[V = W_v × Input]
        J --> M["Attention = softmax(QK^T / √d) × V"]
        K --> M
        L --> M
        M --> N[Concat Heads → Linear]
    end

    subgraph Output
        H --> O[Linear Layer]
        O --> P[Softmax]
        P --> Q[Next Token Probabilities]
        Q --> R[Sampling: temp, top-p, top-k]
        R --> S[Generated Token]
    end

    S -.->|"Feed back as input (autoregressive)"| D
```

## 2. Token Flow Through the System

```mermaid
flowchart LR
    subgraph "Client"
        A[User Message] --> B[API Request]
    end

    subgraph "API Layer"
        B --> C[Tokenizer]
        C --> D{Token Count Check}
        D -->|Over limit| E[Error: Context too long]
        D -->|Within limit| F[Combine: System + History + User]
    end

    subgraph "Model Inference"
        F --> G[Embedding Lookup]
        G --> H[Transformer Layers]
        H --> I[Logit Output]
        I --> J[Sampling Strategy]
        J --> K{Stop Condition?}
        K -->|No| L[Append Token]
        L --> H
        K -->|Yes: max_tokens / EOS / stop sequence| M[Complete Response]
    end

    subgraph "Response"
        M --> N[Detokenize]
        N --> O[Stream chunks via SSE]
        O --> P[Client receives text]
    end

    subgraph "Billing"
        C --> Q[Count Input Tokens]
        M --> R[Count Output Tokens]
        Q --> S[Cost = input×rate + output×rate]
        R --> S
    end
```

## 3. Tool Calling Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant App as Application
    participant LLM as LLM API
    participant T1 as Tool: search_docs
    participant T2 as Tool: get_weather

    U->>App: "What's the weather in Paris and find our travel policy?"
    App->>LLM: messages + tool definitions
    
    Note over LLM: Model decides to call 2 tools in parallel

    LLM-->>App: tool_calls: [search_docs("travel policy"), get_weather("Paris")]
    
    par Execute tools concurrently
        App->>T1: search_docs(query="travel policy")
        T1-->>App: {results: [...]}
    and
        App->>T2: get_weather(location="Paris")
        T2-->>App: {temp: 18°C, condition: "sunny"}
    end

    App->>LLM: messages + tool_results (both)
    
    Note over LLM: Model synthesizes tool results into natural language

    LLM-->>App: "The weather in Paris is 18°C and sunny. Regarding our travel policy..."
    App-->>U: Display response
```

## 4. Model Routing Decision Tree

```mermaid
flowchart TD
    A[Incoming Request] --> B{Classify Complexity}
    
    B -->|Simple: FAQ, lookup| C{Latency Requirement}
    C -->|< 500ms| D[GPT-4o-mini / Haiku]
    C -->|Flexible| E[GPT-4o-mini / Haiku]
    
    B -->|Medium: analysis, code| F{Quality Requirement}
    F -->|Standard| G[GPT-4o-mini]
    F -->|High| H[GPT-4o / Sonnet]
    
    B -->|Complex: reasoning, math| I{Cost Sensitivity}
    I -->|Cost OK| J[o1 / Claude Extended Thinking]
    I -->|Cost Sensitive| K[GPT-4o with CoT prompt]
    
    B -->|Multimodal: image/audio| L{Input Type}
    L -->|Image| M[GPT-4o / Gemini 1.5 Pro]
    L -->|Audio| N[Whisper → GPT-4o / Gemini native]
    L -->|Video| O[Gemini 1.5 Pro]
    
    B -->|Data Sensitive| P{Compliance Requirement}
    P -->|HIPAA/PCI| Q[Self-hosted LLaMA / Mistral]
    P -->|Standard| R[Any cloud provider]
    
    subgraph "Fallback Logic"
        D --> S{Response Quality OK?}
        G --> S
        S -->|No: low confidence| T[Escalate to larger model]
        T --> H
    end

    style D fill:#90EE90
    style E fill:#90EE90
    style G fill:#87CEEB
    style H fill:#87CEEB
    style J fill:#FFB6C1
    style K fill:#FFB6C1
```

## 5. Structured Output Validation Flow

```mermaid
flowchart TD
    A[User Input] --> B[Construct Prompt + JSON Schema]
    B --> C{API Mode}
    
    C -->|Structured Output Mode| D[Constrained Decoding]
    D --> E[Valid JSON Guaranteed]
    E --> F[Pydantic Validation]
    F -->|Valid| G[Return parsed object]
    F -->|Invalid semantics| H[Retry with error feedback]
    
    C -->|JSON Mode| I[Model generates JSON]
    I --> J{Valid JSON?}
    J -->|No| K[Parse error → Retry]
    J -->|Yes| L[Schema Validation]
    L -->|Matches schema| G
    L -->|Missing/wrong fields| H
    
    C -->|Plain text fallback| M[Model generates text]
    M --> N[Regex/heuristic extraction]
    N --> O{Extracted successfully?}
    O -->|Yes| L
    O -->|No| P[Return error to user]
    
    H --> Q{Retry count < max?}
    Q -->|Yes| R[Add error to messages]
    R --> C
    Q -->|No| P
    
    subgraph "Error Feedback Loop"
        R --> S["'Your output had errors: {error}. Fix it.'"]
    end

    style G fill:#90EE90
    style P fill:#FFB6C1
```

## 6. Context Window Budget Allocation

```mermaid
pie title "Context Window Budget (128K tokens)"
    "System Prompt" : 2000
    "Tool Definitions" : 1500
    "RAG Context" : 8000
    "Conversation History" : 4000
    "User Message" : 2000
    "Reserved for Output" : 4096
    "Safety Buffer" : 1000
    "Available/Unused" : 105404
```

```mermaid
flowchart TD
    A[Total Context Window: 128K] --> B[Reserve Output: 4096 tokens]
    B --> C[Available Input Budget: ~124K tokens]
    
    C --> D[Priority 1: Required Sections]
    D --> D1[System Prompt: 2K max]
    D --> D2[Tool Definitions: 1.5K max]
    D --> D3[Current User Message: 2K max]
    
    C --> E[Priority 2: Important]
    E --> E1[RAG Context: 8K max]
    E --> E2[Recent History: 4K max]
    
    C --> F[Priority 3: Nice to Have]
    F --> F1[Full History: remainder]
    F --> F2[Additional Context: remainder]
    
    subgraph "Overflow Handling"
        G{Budget exceeded?}
        G -->|Yes| H[Drop Priority 3 sections]
        H --> I{Still exceeded?}
        I -->|Yes| J[Truncate Priority 2 sections]
        J --> K{Still exceeded?}
        K -->|Yes| L[Summarize conversation history]
        L --> M[Compress RAG chunks]
    end
    
    F --> G
```
