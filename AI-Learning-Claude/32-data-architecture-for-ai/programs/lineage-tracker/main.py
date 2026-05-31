"""
Data Lineage Tracker Simulator for AI Pipelines
=================================================
Tracks data flow from source to serving, demonstrates
impact analysis, debugging traces, and GDPR compliance.

Run: python3 main.py
No dependencies required (standard library only).
"""

import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field


# =============================================================================
# LINEAGE GRAPH DATA MODEL
# =============================================================================

@dataclass
class LineageNode:
    """A node in the lineage graph (dataset, transformation, or model)."""
    id: str
    name: str
    node_type: str  # source, transform, feature, embedding, index, model, endpoint
    owner: str
    description: str
    metadata: Dict = field(default_factory=dict)
    contains_pii: bool = False
    entity_types: List[str] = field(default_factory=list)  # e.g., ["user_id", "doc_id"]


@dataclass
class LineageEdge:
    """A directed edge representing data flow."""
    source_id: str
    target_id: str
    transformation: str
    columns_mapped: Dict[str, str] = field(default_factory=dict)  # source_col -> target_col
    timestamp: datetime = field(default_factory=datetime.now)


# =============================================================================
# LINEAGE GRAPH
# =============================================================================

class LineageGraph:
    """Directed acyclic graph tracking data lineage."""
    
    def __init__(self):
        self.nodes: Dict[str, LineageNode] = {}
        self.edges: List[LineageEdge] = []
        self.adjacency: Dict[str, List[str]] = defaultdict(list)  # forward edges
        self.reverse_adj: Dict[str, List[str]] = defaultdict(list)  # backward edges
    
    def add_node(self, node: LineageNode) -> None:
        self.nodes[node.id] = node
    
    def add_edge(self, edge: LineageEdge) -> None:
        self.edges.append(edge)
        self.adjacency[edge.source_id].append(edge.target_id)
        self.reverse_adj[edge.target_id].append(edge.source_id)
    
    def get_downstream(self, node_id: str) -> List[str]:
        """Find all nodes downstream of a given node (impact analysis)."""
        visited = set()
        queue = deque([node_id])
        result = []
        
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            if current != node_id:
                result.append(current)
            for neighbor in self.adjacency.get(current, []):
                if neighbor not in visited:
                    queue.append(neighbor)
        return result
    
    def get_upstream(self, node_id: str) -> List[str]:
        """Find all nodes upstream of a given node (provenance)."""
        visited = set()
        queue = deque([node_id])
        result = []
        
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            if current != node_id:
                result.append(current)
            for neighbor in self.reverse_adj.get(current, []):
                if neighbor not in visited:
                    queue.append(neighbor)
        return result
    
    def find_nodes_with_entity(self, entity_type: str) -> List[str]:
        """Find all nodes that contain a specific entity type (GDPR query)."""
        return [nid for nid, node in self.nodes.items() 
                if entity_type in node.entity_types]
    
    def get_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """Find path between two nodes."""
        visited = set()
        queue = deque([(source_id, [source_id])])
        
        while queue:
            current, path = queue.popleft()
            if current == target_id:
                return path
            if current in visited:
                continue
            visited.add(current)
            for neighbor in self.adjacency.get(current, []):
                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))
        return None


# =============================================================================
# ASCII VISUALIZATION
# =============================================================================

def render_lineage_ascii(graph: LineageGraph, highlight_path: Optional[List[str]] = None) -> str:
    """Render lineage graph as ASCII art."""
    
    # Group nodes by type for layered display
    layers = {
        "source": [],
        "transform": [],
        "feature": [],
        "embedding": [],
        "index": [],
        "model": [],
        "endpoint": [],
    }
    
    for node_id, node in graph.nodes.items():
        if node.node_type in layers:
            layers[node.node_type].append(node)
    
    lines = []
    lines.append("  Lineage Graph (left=upstream, right=downstream):")
    lines.append("  " + "=" * 66)
    
    layer_order = ["source", "transform", "feature", "embedding", "index", "endpoint"]
    
    for layer_name in layer_order:
        nodes = layers.get(layer_name, [])
        if not nodes:
            continue
        
        lines.append(f"  [{layer_name.upper()}]")
        for node in nodes:
            marker = " *" if highlight_path and node.id in highlight_path else "  "
            pii_marker = " [PII]" if node.contains_pii else ""
            lines.append(f"  {marker} [{node.id}] {node.name}{pii_marker}")
            
            # Show downstream connections
            downstream = graph.adjacency.get(node.id, [])
            if downstream:
                for ds in downstream:
                    arrow = " -->>" if highlight_path and node.id in highlight_path and ds in highlight_path else " --->"
                    lines.append(f"      {arrow} {ds}")
        lines.append("  " + "-" * 40)
    
    return "\n".join(lines)


# =============================================================================
# BUILD EXAMPLE LINEAGE GRAPH
# =============================================================================

def build_ai_pipeline_lineage() -> LineageGraph:
    """Build a realistic lineage graph for an AI/RAG pipeline."""
    
    graph = LineageGraph()
    
    # Sources
    graph.add_node(LineageNode(
        id="postgres_users", name="PostgreSQL: users table",
        node_type="source", owner="identity-team",
        description="User profiles and preferences",
        contains_pii=True, entity_types=["user_id", "email"],
    ))
    graph.add_node(LineageNode(
        id="postgres_docs", name="PostgreSQL: documents table",
        node_type="source", owner="content-team",
        description="Document metadata and content",
        entity_types=["doc_id"],
    ))
    graph.add_node(LineageNode(
        id="kafka_clicks", name="Kafka: user_clicks topic",
        node_type="source", owner="engagement-team",
        description="Real-time click events",
        contains_pii=True, entity_types=["user_id", "doc_id"],
    ))
    graph.add_node(LineageNode(
        id="s3_files", name="S3: document_files bucket",
        node_type="source", owner="content-team",
        description="Raw document files (PDF, DOCX)",
        entity_types=["doc_id"],
    ))
    
    # Transformations
    graph.add_node(LineageNode(
        id="clean_users", name="dbt: clean_users",
        node_type="transform", owner="data-team",
        description="Deduplicate and validate user records",
        contains_pii=True, entity_types=["user_id"],
    ))
    graph.add_node(LineageNode(
        id="clean_docs", name="dbt: clean_documents",
        node_type="transform", owner="data-team",
        description="Validate and enrich document metadata",
        entity_types=["doc_id"],
    ))
    graph.add_node(LineageNode(
        id="chunk_docs", name="Python: document_chunker",
        node_type="transform", owner="ai-team",
        description="Split documents into chunks (500 tokens, 50 overlap)",
        metadata={"chunk_size": 500, "overlap": 50},
        entity_types=["doc_id", "chunk_id"],
    ))
    graph.add_node(LineageNode(
        id="agg_clicks", name="Flink: click_aggregator",
        node_type="transform", owner="engagement-team",
        description="Aggregate clicks into session features",
        contains_pii=True, entity_types=["user_id"],
    ))
    
    # Features
    graph.add_node(LineageNode(
        id="user_features", name="Feature Store: user_activity_features",
        node_type="feature", owner="engagement-team",
        description="User activity features (clicks, sessions, preferences)",
        contains_pii=True, entity_types=["user_id"],
    ))
    graph.add_node(LineageNode(
        id="doc_features", name="Feature Store: document_features",
        node_type="feature", owner="content-team",
        description="Document quality, freshness, popularity features",
        entity_types=["doc_id"],
    ))
    
    # Embeddings
    graph.add_node(LineageNode(
        id="doc_embeddings", name="Embeddings: document_chunks",
        node_type="embedding", owner="ai-team",
        description="Document chunk embeddings (text-embedding-3-small)",
        metadata={"model": "text-embedding-3-small", "dimensions": 1536},
        entity_types=["doc_id", "chunk_id"],
    ))
    
    # Index
    graph.add_node(LineageNode(
        id="vector_index", name="Pinecone: search_index",
        node_type="index", owner="ai-team",
        description="HNSW index for document search",
        metadata={"ef": 200, "M": 16, "vectors": "5M"},
        entity_types=["doc_id", "chunk_id"],
    ))
    
    # Endpoint
    graph.add_node(LineageNode(
        id="search_api", name="API: /v2/search",
        node_type="endpoint", owner="ai-team",
        description="RAG search endpoint serving user queries",
        contains_pii=True, entity_types=["user_id", "doc_id"],
    ))
    
    # Edges (data flow)
    edges = [
        ("postgres_users", "clean_users", "deduplicate, validate email format"),
        ("postgres_docs", "clean_docs", "validate metadata, enrich categories"),
        ("s3_files", "chunk_docs", "extract text, split into chunks"),
        ("kafka_clicks", "agg_clicks", "aggregate by user, 5-min windows"),
        ("clean_users", "user_features", "compute activity features"),
        ("agg_clicks", "user_features", "merge real-time click features"),
        ("clean_docs", "doc_features", "compute document quality features"),
        ("chunk_docs", "doc_embeddings", "embed with text-embedding-3-small"),
        ("doc_embeddings", "vector_index", "HNSW index build"),
        ("vector_index", "search_api", "ANN search serving"),
        ("user_features", "search_api", "user context for personalization"),
        ("doc_features", "search_api", "document re-ranking signals"),
    ]
    
    for src, tgt, transform in edges:
        graph.add_edge(LineageEdge(source_id=src, target_id=tgt, transformation=transform))
    
    return graph


# =============================================================================
# DEBUGGING SCENARIOS
# =============================================================================

def demo_debugging(graph: LineageGraph):
    """Demonstrate debugging a model regression using lineage."""
    
    print("\n" + "=" * 70)
    print("DEMO: Debugging Model Regression via Lineage")
    print("=" * 70)
    
    print("""
  Incident: Search quality (MRR) dropped from 0.72 to 0.65 on Tuesday
  
  Step 1: Check model → No model deployment since Monday ✓
  Step 2: Trace upstream from search_api using lineage...
""")
    
    upstream = graph.get_upstream("search_api")
    print(f"  Upstream dependencies of search_api:")
    for node_id in upstream:
        node = graph.nodes[node_id]
        print(f"    [{node.node_type}] {node.name}")
    
    print(f"""
  Step 3: Check each upstream for changes on Tuesday...
  
  Finding: document_chunker config changed!
    Before: chunk_size=500, overlap=50
    After:  chunk_size=1000, overlap=0   ← SOMEONE CHANGED THIS
    
  Step 4: Trace impact downstream from chunk_docs:
""")
    
    downstream = graph.get_downstream("chunk_docs")
    print(f"  Impact of chunk_docs change:")
    for node_id in downstream:
        node = graph.nodes[node_id]
        print(f"    AFFECTED: [{node.node_type}] {node.name}")
    
    print(f"""
  Step 5: Root cause identified!
    - Chunking change → different embeddings → different search results
    - 30% of documents re-chunked with new config
    - Mixed chunk sizes in index degraded search quality
    
  Resolution: Revert chunking config, re-embed affected documents
  Time to debug: 2 hours (vs estimated 2 weeks without lineage)
""")


def demo_impact_analysis(graph: LineageGraph):
    """Demonstrate impact analysis before making changes."""
    
    print("\n" + "=" * 70)
    print("DEMO: Impact Analysis — 'What breaks if I change this?'")
    print("=" * 70)
    
    change_target = "postgres_docs"
    print(f"\n  Proposed change: Rename column 'title' to 'document_title' in {change_target}")
    print(f"\n  Running impact analysis...")
    
    downstream = graph.get_downstream(change_target)
    
    print(f"\n  Systems affected by changes to '{change_target}':")
    print(f"  {'─' * 50}")
    
    for node_id in downstream:
        node = graph.nodes[node_id]
        severity = "CRITICAL" if node.node_type in ("endpoint", "index") else "WARNING"
        print(f"    [{severity}] {node.name} (owner: {node.owner})")
    
    print(f"""
  Impact Summary:
  ├── {len(downstream)} downstream systems affected
  ├── Teams to notify: {', '.join(set(graph.nodes[n].owner for n in downstream))}
  ├── Production endpoints affected: {sum(1 for n in downstream if graph.nodes[n].node_type == 'endpoint')}
  └── Recommendation: Create data contract, notify consumers 90 days before change
""")


def demo_gdpr_query(graph: LineageGraph):
    """Demonstrate GDPR data subject access request via lineage."""
    
    print("\n" + "=" * 70)
    print("DEMO: GDPR — 'Where is user X's data?'")
    print("=" * 70)
    
    print(f"\n  Data Subject Access Request: Where is user_12345's data stored?")
    print(f"\n  Querying lineage graph for all nodes containing 'user_id' entity...")
    
    user_nodes = graph.find_nodes_with_entity("user_id")
    
    print(f"\n  User data locations ({len(user_nodes)} systems):")
    print(f"  {'─' * 50}")
    
    pii_nodes = []
    for node_id in user_nodes:
        node = graph.nodes[node_id]
        pii_status = "CONTAINS PII" if node.contains_pii else "no PII"
        print(f"    [{node.node_type:>10}] {node.name}")
        print(f"               Owner: {node.owner} | {pii_status}")
        if node.contains_pii:
            pii_nodes.append(node)
    
    print(f"""
  GDPR Response:
  ├── Systems with user PII: {len(pii_nodes)}
  ├── Deletion required in: {', '.join(n.name for n in pii_nodes)}
  ├── Teams responsible: {', '.join(set(n.owner for n in pii_nodes))}
  └── Estimated deletion time: 72 hours (SLA)
  
  Deletion Order (respecting dependencies):
  1. search_api (serving cache) — immediate
  2. user_features (feature store) — within 1 hour
  3. agg_clicks (streaming state) — within 4 hours
  4. clean_users (warehouse) — within 24 hours
  5. postgres_users (source) — within 24 hours
  6. kafka_clicks (retain but redact) — within 72 hours
""")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("DATA LINEAGE TRACKER FOR AI PIPELINES")
    print("=" * 70)
    
    # Build lineage graph
    print("\n" + "-" * 70)
    print("STEP 1: Building Lineage Graph")
    print("-" * 70)
    
    graph = build_ai_pipeline_lineage()
    
    print(f"\n  Graph Statistics:")
    print(f"  ├── Nodes: {len(graph.nodes)}")
    print(f"  ├── Edges: {len(graph.edges)}")
    print(f"  ├── Sources: {sum(1 for n in graph.nodes.values() if n.node_type == 'source')}")
    print(f"  ├── Transformations: {sum(1 for n in graph.nodes.values() if n.node_type == 'transform')}")
    print(f"  ├── Features: {sum(1 for n in graph.nodes.values() if n.node_type == 'feature')}")
    print(f"  ├── Embeddings: {sum(1 for n in graph.nodes.values() if n.node_type == 'embedding')}")
    print(f"  └── Endpoints: {sum(1 for n in graph.nodes.values() if n.node_type == 'endpoint')}")
    
    # Visualize
    print("\n" + "-" * 70)
    print("STEP 2: Lineage Visualization")
    print("-" * 70)
    
    # Show path from source to endpoint
    path = graph.get_path("s3_files", "search_api")
    print(f"\n  Path: s3_files → search_api")
    ascii_viz = render_lineage_ascii(graph, highlight_path=path)
    print(ascii_viz)
    
    # Debugging demo
    demo_debugging(graph)
    
    # Impact analysis demo
    demo_impact_analysis(graph)
    
    # GDPR demo
    demo_gdpr_query(graph)
    
    # Summary
    print("\n" + "=" * 70)
    print("LINEAGE TRACKER SUMMARY")
    print("=" * 70)
    print(f"""
  Capabilities Demonstrated:
  ├── Forward lineage (downstream impact analysis)
  ├── Backward lineage (upstream provenance)
  ├── Path finding (source → destination trace)
  ├── Entity tracking (where does user data live?)
  ├── Debugging (model regression → root cause)
  └── Compliance (GDPR data subject requests)

  Staff Architect Takeaways:
  1. Lineage turns 2-week debugging into 2-hour debugging
  2. Impact analysis prevents breaking downstream AI systems
  3. GDPR compliance requires knowing ALL places user data exists
  4. Auto-instrument lineage at pipeline creation (not as afterthought)
  5. Column-level lineage enables precise PII tracking
  6. Lineage graph should be queryable via API (not just visual)
""")


if __name__ == "__main__":
    main()
