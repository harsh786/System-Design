"""
knowledge_base.py - Data Layer for NovaTech (fictional company)

Contains three data sources that the agent can query:
1. Documents (unstructured text) - for vector/semantic search
2. Structured data (SQL-like) - for precise lookups
3. Entity relationships (graph-like) - for relationship traversal
"""

# =============================================================================
# DOCUMENT STORE - Unstructured text passages about NovaTech
# Each document has an id, text, and metadata for source attribution
# =============================================================================

DOCUMENTS = [
    {
        "id": "doc_001",
        "text": "NovaTech's flagship product is the NovaCloud Platform, a comprehensive cloud infrastructure solution launched in 2021. It provides compute, storage, and networking services to enterprise customers. The platform handles over 50,000 requests per second at peak load.",
        "metadata": {"category": "products", "date": "2024-01"}
    },
    {
        "id": "doc_002",
        "text": "The Platform Engineering Team at NovaTech built and maintains the payment gateway service, which processes all financial transactions. The team consists of 12 engineers and was formed in 2022 under the leadership of Sarah Chen.",
        "metadata": {"category": "teams", "date": "2024-01"}
    },
    {
        "id": "doc_003",
        "text": "NovaTech reported annual revenue of $45 million in fiscal year 2023, representing a 35% year-over-year growth. The company's primary revenue streams are subscription fees (60%), professional services (25%), and marketplace commissions (15%).",
        "metadata": {"category": "financials", "date": "2024-01"}
    },
    {
        "id": "doc_004",
        "text": "The engineering department at NovaTech follows an agile methodology with two-week sprints. Code review is mandatory for all pull requests, requiring at least two approvals. The team uses a microservices architecture with Kubernetes orchestration.",
        "metadata": {"category": "engineering", "date": "2024-01"}
    },
    {
        "id": "doc_005",
        "text": "NovaTech's sales team exceeded their Q3 2023 target of $12 million by achieving $13.5 million in bookings. The sales team consists of 8 account executives and 4 solution architects focused on enterprise accounts with deal sizes above $100K.",
        "metadata": {"category": "sales", "date": "2024-01"}
    },
    {
        "id": "doc_006",
        "text": "The NovaTech Data Analytics product, called NovaInsight, provides real-time dashboards and ML-powered anomaly detection for customers. It was developed by the Data Science Team and launched in Q2 2023. NovaInsight has 200 active enterprise customers.",
        "metadata": {"category": "products", "date": "2024-01"}
    },
    {
        "id": "doc_007",
        "text": "NovaTech's hiring policy prioritizes diversity and inclusion. The company offers remote work flexibility, competitive equity packages, and a learning budget of $5,000 per employee per year. Current headcount is 156 employees across 4 offices.",
        "metadata": {"category": "hr_policy", "date": "2024-01"}
    },
    {
        "id": "doc_008",
        "text": "Security at NovaTech is managed by the InfoSec team led by Marcus Johnson. The company achieved SOC 2 Type II compliance in 2023 and undergoes quarterly penetration testing. All customer data is encrypted at rest and in transit using AES-256.",
        "metadata": {"category": "security", "date": "2024-01"}
    },
    {
        "id": "doc_009",
        "text": "NovaTech's customer support operates 24/7 with a target response time of under 15 minutes for critical issues. The support team uses a tiered escalation model: L1 (basic), L2 (technical), L3 (engineering). Customer satisfaction score (CSAT) averages 4.6/5.",
        "metadata": {"category": "support", "date": "2024-01"}
    },
    {
        "id": "doc_010",
        "text": "NovaTech plans to expand into the Asian market in 2024, with a Singapore office opening in Q2. The company has allocated $5 million for international expansion. Key partnerships with local cloud providers are being established.",
        "metadata": {"category": "strategy", "date": "2024-01"}
    },
]

# =============================================================================
# STRUCTURED DATA - Simulates SQL database tables
# =============================================================================

STRUCTURED_DATA = {
    "employees": [
        {"id": 1, "name": "Sarah Chen", "role": "VP Engineering", "team": "Platform Engineering", "reports_to": "CEO", "salary_band": "L7"},
        {"id": 2, "name": "Marcus Johnson", "role": "Director InfoSec", "team": "Security", "reports_to": "Sarah Chen", "salary_band": "L6"},
        {"id": 3, "name": "Alex Rivera", "role": "Head of Sales", "team": "Sales", "reports_to": "CEO", "salary_band": "L7"},
        {"id": 4, "name": "Priya Patel", "role": "Lead Data Scientist", "team": "Data Science", "reports_to": "Sarah Chen", "salary_band": "L6"},
        {"id": 5, "name": "James O'Brien", "role": "CTO", "team": "Executive", "reports_to": "CEO", "salary_band": "L8"},
        {"id": 6, "name": "Lisa Wang", "role": "Product Manager", "team": "Product", "reports_to": "James O'Brien", "salary_band": "L6"},
        {"id": 7, "name": "Tom Baker", "role": "Senior Engineer", "team": "Platform Engineering", "reports_to": "Sarah Chen", "salary_band": "L5"},
        {"id": 8, "name": "Nina Kowalski", "role": "Account Executive", "team": "Sales", "reports_to": "Alex Rivera", "salary_band": "L5"},
    ],
    "quarterly_financials": [
        {"quarter": "Q1 2023", "revenue": 9_500_000, "expenses": 7_200_000, "profit": 2_300_000, "headcount": 130},
        {"quarter": "Q2 2023", "revenue": 11_000_000, "expenses": 8_100_000, "profit": 2_900_000, "headcount": 142},
        {"quarter": "Q3 2023", "revenue": 13_500_000, "expenses": 9_000_000, "profit": 4_500_000, "headcount": 150},
        {"quarter": "Q4 2023", "revenue": 11_000_000, "expenses": 8_500_000, "profit": 2_500_000, "headcount": 156},
    ],
    "products": [
        {"name": "NovaCloud Platform", "team": "Platform Engineering", "launch_date": "2021-03", "customers": 500, "mrr": 2_800_000},
        {"name": "NovaInsight", "team": "Data Science", "launch_date": "2023-04", "customers": 200, "mrr": 900_000},
        {"name": "Payment Gateway", "team": "Platform Engineering", "launch_date": "2022-08", "customers": 350, "mrr": 1_200_000},
    ],
    "sales_targets": [
        {"quarter": "Q1 2023", "target": 9_000_000, "actual": 9_500_000, "team": "Sales"},
        {"quarter": "Q2 2023", "target": 10_500_000, "actual": 11_000_000, "team": "Sales"},
        {"quarter": "Q3 2023", "target": 12_000_000, "actual": 13_500_000, "team": "Sales"},
        {"quarter": "Q4 2023", "target": 12_500_000, "actual": 11_000_000, "team": "Sales"},
    ],
}

# =============================================================================
# ENTITY RELATIONSHIPS - Graph-like connections between entities
# Format: subject -> relationship -> object(s)
# =============================================================================

ENTITY_GRAPH = {
    "Platform Engineering": {
        "managed_by": ["Sarah Chen"],
        "products": ["NovaCloud Platform", "Payment Gateway"],
        "members": ["Sarah Chen", "Tom Baker"],
        "reports_to": ["CTO"],
    },
    "Data Science": {
        "managed_by": ["Priya Patel"],
        "products": ["NovaInsight"],
        "members": ["Priya Patel"],
        "reports_to": ["VP Engineering"],
    },
    "Sales": {
        "managed_by": ["Alex Rivera"],
        "products": [],
        "members": ["Alex Rivera", "Nina Kowalski"],
        "reports_to": ["CEO"],
    },
    "Security": {
        "managed_by": ["Marcus Johnson"],
        "products": [],
        "members": ["Marcus Johnson"],
        "reports_to": ["VP Engineering"],
    },
    "Sarah Chen": {
        "manages": ["Platform Engineering", "Data Science", "Security"],
        "role": ["VP Engineering"],
        "reports_to": ["CEO"],
    },
    "Alex Rivera": {
        "manages": ["Sales"],
        "role": ["Head of Sales"],
        "reports_to": ["CEO"],
    },
    "NovaCloud Platform": {
        "built_by": ["Platform Engineering"],
        "launched": ["2021-03"],
        "type": ["cloud infrastructure"],
    },
    "Payment Gateway": {
        "built_by": ["Platform Engineering"],
        "launched": ["2022-08"],
        "type": ["financial services"],
    },
    "NovaInsight": {
        "built_by": ["Data Science"],
        "launched": ["2023-04"],
        "type": ["analytics"],
    },
}


# =============================================================================
# SEARCH FUNCTIONS - Used by tools.py
# =============================================================================

def search_documents(query: str, top_k: int = 3) -> list:
    """
    Simple keyword/relevance search over documents.
    In production, this would be a vector similarity search.
    Here we simulate relevance scoring based on keyword overlap.
    """
    query_terms = set(query.lower().split())
    scored = []
    for doc in DOCUMENTS:
        text_terms = set(doc["text"].lower().split())
        # Jaccard-like overlap score
        overlap = len(query_terms & text_terms)
        score = overlap / max(len(query_terms), 1)
        if score > 0:
            scored.append({
                "id": doc["id"],
                "text": doc["text"],
                "score": round(min(score, 1.0), 3),
                "metadata": doc["metadata"],
            })
    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def query_structured(table: str, filters: dict = None) -> list:
    """
    Query structured data with optional filters.
    Simulates SQL: SELECT * FROM table WHERE filters
    """
    if table not in STRUCTURED_DATA:
        return []
    results = STRUCTURED_DATA[table]
    if filters:
        filtered = []
        for row in results:
            match = all(row.get(k) == v for k, v in filters.items())
            if match:
                filtered.append(row)
        return filtered
    return results


def lookup_graph(entity: str, relationship: str = None) -> list:
    """
    Traverse the entity graph.
    Returns relationships for a given entity, optionally filtered by type.
    """
    # Try exact match first, then partial match
    node = ENTITY_GRAPH.get(entity)
    if not node:
        # Partial match
        for key in ENTITY_GRAPH:
            if entity.lower() in key.lower() or key.lower() in entity.lower():
                node = ENTITY_GRAPH[key]
                entity = key
                break
    if not node:
        return []

    if relationship:
        values = node.get(relationship, [])
        return [{"entity": entity, "relationship": relationship, "targets": values}]
    else:
        # Return all relationships
        return [{"entity": entity, "relationship": rel, "targets": vals}
                for rel, vals in node.items()]
