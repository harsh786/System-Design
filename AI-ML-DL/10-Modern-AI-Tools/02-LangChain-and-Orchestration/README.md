# LangChain and LLM Orchestration

## Why LLM Orchestration Frameworks Exist

LLMs alone can't: access real-time data, execute actions, maintain state across turns, or chain complex reasoning. Orchestration frameworks solve this by providing abstractions for building LLM-powered applications.

```
┌─────────────────────────────────────────────────────────┐
│              LLM Application Architecture                 │
├─────────────────────────────────────────────────────────┤
│  User Interface (Chat, API, etc.)                        │
├─────────────────────────────────────────────────────────┤
│  Orchestration Layer (LangChain / LlamaIndex)            │
│  ├── Routing & Planning                                  │
│  ├── Memory Management                                   │
│  ├── Tool Execution                                      │
│  └── Output Parsing                                      │
├─────────────────────────────────────────────────────────┤
│  Foundation Models    │  Data Layer        │  Tools       │
│  (OpenAI, Anthropic,  │  (Vector DBs,      │  (APIs,      │
│   Local LLMs)         │   Documents)       │   Code exec) │
└─────────────────────────────────────────────────────────┘
```

## Installation

```bash
pip install langchain langchain-openai langchain-community langchain-core
pip install langgraph langsmith
pip install chromadb faiss-cpu  # vector stores
pip install llama-index  # alternative
```

---

## LangChain Core Concepts

### 1. Models

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_anthropic import ChatAnthropic
from langchain_community.llms import Ollama

# Chat Models
llm = ChatOpenAI(model="gpt-4o", temperature=0)
claude = ChatAnthropic(model="claude-3-5-sonnet-20241022")
local = Ollama(model="llama3")

# Embeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectors = embeddings.embed_documents(["hello world", "goodbye world"])

# Basic invocation
from langchain_core.messages import HumanMessage, SystemMessage
response = llm.invoke([
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="What is LangChain?"),
])
print(response.content)
```

### 2. Prompts

```python
from langchain_core.prompts import ChatPromptTemplate, FewShotPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

# Simple template
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a {role}. Respond in {language}."),
    ("human", "{input}"),
])
chain = prompt | llm
response = chain.invoke({"role": "translator", "language": "French", "input": "Hello!"})

# Structured output with Pydantic
class MovieReview(BaseModel):
    sentiment: str = Field(description="positive, negative, or neutral")
    score: float = Field(description="sentiment score 0-1")
    summary: str = Field(description="one-line summary")

structured_llm = llm.with_structured_output(MovieReview)
review = structured_llm.invoke("Review: The movie was absolutely fantastic!")
print(review.sentiment, review.score)

# Few-shot prompting
examples = [
    {"input": "happy", "output": "sad"},
    {"input": "tall", "output": "short"},
]
few_shot = FewShotPromptTemplate(
    examples=examples,
    example_prompt=ChatPromptTemplate.from_messages([
        ("human", "{input}"), ("ai", "{output}")
    ]),
    suffix="Human: {input}\nAI:",
    input_variables=["input"],
)
```

### 3. Chains (LCEL - LangChain Expression Language)

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel

# Simple chain with pipe operator
chain = prompt | llm | StrOutputParser()
result = chain.invoke({"input": "explain quantum computing"})

# Parallel chains
analysis_chain = RunnableParallel(
    summary=ChatPromptTemplate.from_template("Summarize: {text}") | llm | StrOutputParser(),
    sentiment=ChatPromptTemplate.from_template("Sentiment of: {text}") | llm | StrOutputParser(),
    keywords=ChatPromptTemplate.from_template("Extract keywords: {text}") | llm | StrOutputParser(),
)
result = analysis_chain.invoke({"text": "LangChain is a powerful framework..."})
# result = {"summary": "...", "sentiment": "...", "keywords": "..."}

# Sequential chain with context passing
chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# Streaming
for chunk in chain.stream({"input": "Tell me a story"}):
    print(chunk, end="", flush=True)

# Batch processing
results = chain.batch([{"input": "Q1"}, {"input": "Q2"}], config={"max_concurrency": 5})
```

### 4. Memory

```python
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

store = {}

def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

# Each session maintains its own history
response1 = chain_with_history.invoke(
    {"input": "My name is Alice"},
    config={"configurable": {"session_id": "user-123"}},
)
response2 = chain_with_history.invoke(
    {"input": "What's my name?"},  # Will remember "Alice"
    config={"configurable": {"session_id": "user-123"}},
)
```

### 5. Agents (Tool-Using LLMs)

```python
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor

@tool
def search_web(query: str) -> str:
    """Search the web for current information."""
    # Implementation here
    return f"Results for: {query}"

@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: 72°F, Sunny"

tools = [search_web, calculator, get_weather]

# Create agent
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant with access to tools."),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

result = executor.invoke({"input": "What's the weather in NYC and what's 25*47?"})
```

### 6. RAG (Retrieval-Augmented Generation)

```python
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# Load documents
loader = PyPDFLoader("document.pdf")
docs = loader.load()

# Split into chunks
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
chunks = splitter.split_documents(docs)

# Create vector store
vectorstore = Chroma.from_documents(chunks, OpenAIEmbeddings())
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

# RAG chain
rag_prompt = ChatPromptTemplate.from_template("""
Answer based on the following context. If you can't find the answer, say so.

Context: {context}
Question: {question}
""")

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | rag_prompt
    | llm
    | StrOutputParser()
)

answer = rag_chain.invoke("What are the key findings?")
```

---

## LangGraph (Stateful Multi-Step Agents)

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    next_step: str

def researcher(state: AgentState) -> AgentState:
    """Research step - gather information."""
    response = llm.invoke(state["messages"] + [("system", "Research this topic thoroughly.")])
    return {"messages": [response], "next_step": "writer"}

def writer(state: AgentState) -> AgentState:
    """Writing step - create content from research."""
    response = llm.invoke(state["messages"] + [("system", "Write a clear summary.")])
    return {"messages": [response], "next_step": "reviewer"}

def reviewer(state: AgentState) -> AgentState:
    """Review step - check quality."""
    response = llm.invoke(state["messages"] + [("system", "Review and suggest improvements.")])
    return {"messages": [response], "next_step": "end"}

def router(state: AgentState) -> str:
    return state["next_step"] if state["next_step"] != "end" else END

# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("researcher", researcher)
workflow.add_node("writer", writer)
workflow.add_node("reviewer", reviewer)

workflow.set_entry_point("researcher")
workflow.add_conditional_edges("researcher", router)
workflow.add_conditional_edges("writer", router)
workflow.add_conditional_edges("reviewer", router)

app = workflow.compile()
result = app.invoke({"messages": [("human", "Write about quantum computing")], "next_step": ""})
```

---

## LlamaIndex (Data Framework for LLMs)

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

# Configure
Settings.llm = OpenAI(model="gpt-4o", temperature=0)
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

# Load and index (simplest RAG in 3 lines)
documents = SimpleDirectoryReader("./data").load_data()
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()

response = query_engine.query("What is the main topic?")
print(response)

# Advanced: different index types
from llama_index.core import SummaryIndex, KeywordTableIndex

summary_index = SummaryIndex.from_documents(documents)      # Summarization
keyword_index = KeywordTableIndex.from_documents(documents)  # Keyword-based retrieval

# Chat engine with memory
chat_engine = index.as_chat_engine(chat_mode="context", similarity_top_k=3)
response = chat_engine.chat("Tell me about the data")
response = chat_engine.chat("Can you elaborate on that?")  # Remembers context
```

---

## Framework Comparison

| Feature | LangChain | LlamaIndex | Semantic Kernel | DSPy |
|---------|-----------|------------|-----------------|------|
| **Focus** | General orchestration | Data/RAG | Enterprise/.NET | Prompt optimization |
| **Strengths** | Flexibility, ecosystem | RAG quality, indexing | Azure integration | Auto-tuning prompts |
| **Agents** | Excellent | Basic | Good | Via modules |
| **RAG** | Good | Excellent | Good | Good |
| **Learning curve** | Medium | Low | Medium | High |
| **Production ready** | Yes (with LangSmith) | Yes | Yes | Experimental |
| **Best for** | Complex LLM apps | Document Q&A | .NET/Azure shops | Research |

## When to Use What

- **Simple chatbot**: LangChain with memory
- **Document Q&A**: LlamaIndex (better default RAG)
- **Multi-step agents**: LangGraph
- **Enterprise/.NET**: Semantic Kernel
- **Optimize prompts automatically**: DSPy
- **Just need an API call**: Don't use a framework - use the SDK directly

---

## Production Patterns

```python
# Fallback chains
from langchain_core.runnables import RunnableWithFallbacks

primary = ChatOpenAI(model="gpt-4o")
fallback = ChatAnthropic(model="claude-3-5-sonnet-20241022")
robust_llm = primary.with_fallbacks([fallback])

# Retry with exponential backoff
from langchain_core.runnables import RunnableRetry
chain_with_retry = chain.with_retry(stop_after_attempt=3)

# Rate limiting
from langchain_core.rate_limiters import InMemoryRateLimiter
rate_limiter = InMemoryRateLimiter(requests_per_second=1)
llm = ChatOpenAI(rate_limiter=rate_limiter)

# Caching
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
set_llm_cache(SQLiteCache(database_path=".langchain.db"))

# Tracing with LangSmith
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-key"
# All chains automatically traced - no code changes needed
```

---

## Common Pitfalls

1. **Over-engineering**: Don't use LangChain for a simple API call - use the SDK directly
2. **Ignoring token limits**: Always track and manage context window usage
3. **No evaluation**: Use LangSmith or custom evals before production
4. **Stateless agents**: Use LangGraph for anything needing complex state management
5. **RAG without chunking strategy**: Default splitting is rarely optimal
6. **Not streaming**: Always stream for user-facing applications

## Best Practices

- Start with the simplest approach (direct API → chain → agent)
- Use structured output (Pydantic) for reliable parsing
- Implement fallbacks and retries for production
- Trace everything with LangSmith in production
- Evaluate with diverse test cases before deploying
- Version your prompts alongside your code
