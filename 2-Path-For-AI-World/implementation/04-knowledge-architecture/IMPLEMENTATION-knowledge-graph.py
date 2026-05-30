"""
Enterprise Knowledge Graph
============================
Knowledge graph implementation for entity extraction, relationship modeling,
entity resolution, graph storage, and graph-augmented retrieval.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import numpy as np

try:
    import networkx as nx
except ImportError:
    nx = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("knowledge_graph")


# ============================================================================
# Types and Configuration
# ============================================================================

class EntityType(Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    TEAM = "team"
    PRODUCT = "product"
    SERVICE = "service"
    TECHNOLOGY = "technology"
    PROCESS = "process"
    DOCUMENT = "document"
    EVENT = "event"
    LOCATION = "location"
    CONCEPT = "concept"


class RelationshipType(Enum):
    OWNS = "owns"
    BELONGS_TO = "belongs_to"
    DEPENDS_ON = "depends_on"
    USES = "uses"
    DOCUMENTS = "documents"
    CAUSED_BY = "caused_by"
    SUPERSEDES = "supersedes"
    IMPLEMENTS = "implements"
    RELATED_TO = "related_to"
    REPORTS_TO = "reports_to"
    PART_OF = "part_of"
    CREATED_BY = "created_by"
    MAINTAINS = "maintains"
    INTEGRATES_WITH = "integrates_with"
    DEPLOYED_ON = "deployed_on"


@dataclass
class Entity:
    """A node in the knowledge graph."""
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    canonical_name: str = ""
    entity_type: EntityType = EntityType.CONCEPT
    aliases: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    source_documents: list[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    embedding: Optional[np.ndarray] = None

    @property
    def all_names(self) -> list[str]:
        return [self.canonical_name] + self.aliases


@dataclass
class Relationship:
    """An edge in the knowledge graph."""
    relationship_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_entity_id: str = ""
    target_entity_id: str = ""
    relationship_type: RelationshipType = RelationshipType.RELATED_TO
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source_document: str = ""
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExtractionResult:
    """Result of entity/relationship extraction from a document."""
    document_id: str
    entities: list[Entity]
    relationships: list[Relationship]
    extraction_confidence: float = 0.0


@dataclass
class GraphQueryResult:
    """Result of a graph query."""
    entities: list[Entity]
    relationships: list[Relationship]
    paths: list[list[str]] = field(default_factory=list)
    context_text: str = ""
    confidence: float = 0.0


# ============================================================================
# Entity Extraction
# ============================================================================

class EntityExtractor:
    """
    Extracts entities from document text using pattern matching and NER.
    In production: use spaCy, Hugging Face NER, or LLM-based extraction.
    """

    def __init__(self):
        self.logger = logging.getLogger("entity_extractor")
        # Pattern-based entity detection (production: use ML models)
        self._patterns: dict[EntityType, list[re.Pattern]] = {
            EntityType.TECHNOLOGY: [
                re.compile(r'\b(Kubernetes|K8s|Docker|AWS|Azure|GCP|Python|Java|Go|Rust|'
                          r'PostgreSQL|MySQL|Redis|Kafka|Elasticsearch|MongoDB|'
                          r'React|Next\.js|FastAPI|Spring Boot|TensorFlow|PyTorch)\b', re.I),
            ],
            EntityType.PRODUCT: [
                re.compile(r'\b(Slack|Jira|Confluence|GitHub|GitLab|Datadog|PagerDuty|'
                          r'Snowflake|Databricks|Terraform|ArgoCD|Jenkins)\b', re.I),
            ],
            EntityType.PROCESS: [
                re.compile(r'\b(CI/CD|deployment|migration|backup|disaster recovery|'
                          r'incident response|code review|sprint planning|'
                          r'capacity planning|load testing|canary deployment)\b', re.I),
            ],
            EntityType.ORGANIZATION: [
                re.compile(r'\b(engineering team|platform team|SRE team|data team|'
                          r'security team|product team|design team|DevOps team)\b', re.I),
            ],
        }
        # Person detection (simplified; use NER in production)
        self._person_pattern = re.compile(
            r'\b([A-Z][a-z]+\s[A-Z][a-z]+)\b'  # Simple "First Last" pattern
        )
        # Email-based person detection
        self._email_pattern = re.compile(r'\b([a-z]+\.[a-z]+)@[a-z]+\.[a-z]+\b')

    def extract(self, text: str, document_id: str) -> list[Entity]:
        """Extract all entities from text."""
        entities: list[Entity] = []
        seen_names: set[str] = set()

        # Pattern-based extraction
        for entity_type, patterns in self._patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    name = match.group(0)
                    normalized = self._normalize_name(name)
                    if normalized not in seen_names:
                        seen_names.add(normalized)
                        entities.append(Entity(
                            canonical_name=normalized,
                            entity_type=entity_type,
                            aliases=[name] if name != normalized else [],
                            source_documents=[document_id],
                            confidence=0.85,
                        ))

        # Person extraction
        for match in self._person_pattern.finditer(text):
            name = match.group(1)
            if name not in seen_names and not self._is_false_positive_person(name):
                seen_names.add(name)
                entities.append(Entity(
                    canonical_name=name,
                    entity_type=EntityType.PERSON,
                    source_documents=[document_id],
                    confidence=0.7,  # Lower confidence for pattern-based person detection
                ))

        self.logger.info(f"Extracted {len(entities)} entities from document {document_id}")
        return entities

    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for consistent matching."""
        # K8s → Kubernetes, etc.
        aliases = {"k8s": "Kubernetes", "pg": "PostgreSQL", "es": "Elasticsearch"}
        return aliases.get(name.lower(), name)

    def _is_false_positive_person(self, name: str) -> bool:
        """Filter out common false positives for person names."""
        false_positives = {
            "Read Only", "Write Access", "Next Steps", "Best Practices",
            "Key Points", "New York", "San Francisco", "Los Angeles",
        }
        return name in false_positives


# ============================================================================
# Relationship Extraction
# ============================================================================

class RelationshipExtractor:
    """
    Extracts relationships between entities from text.
    In production: use LLM-based extraction with structured output.
    """

    def __init__(self):
        self.logger = logging.getLogger("relationship_extractor")
        # Relationship indicator patterns
        self._patterns: dict[RelationshipType, list[re.Pattern]] = {
            RelationshipType.USES: [
                re.compile(r'(\w+)\s+(?:uses?|utilizes?|leverages?|employs?)\s+(\w+)', re.I),
            ],
            RelationshipType.DEPENDS_ON: [
                re.compile(r'(\w+)\s+(?:depends?\s+on|requires?|needs?)\s+(\w+)', re.I),
            ],
            RelationshipType.OWNS: [
                re.compile(r'(\w+)\s+(?:owns?|manages?|maintains?|is\s+responsible\s+for)\s+(\w+)', re.I),
            ],
            RelationshipType.DEPLOYED_ON: [
                re.compile(r'(\w+)\s+(?:runs?\s+on|deployed\s+(?:on|to)|hosted\s+on)\s+(\w+)', re.I),
            ],
            RelationshipType.INTEGRATES_WITH: [
                re.compile(r'(\w+)\s+(?:integrates?\s+with|connects?\s+to|communicates?\s+with)\s+(\w+)', re.I),
            ],
            RelationshipType.PART_OF: [
                re.compile(r'(\w+)\s+(?:is\s+part\s+of|belongs?\s+to|is\s+a\s+component\s+of)\s+(\w+)', re.I),
            ],
        }

    def extract(
        self, text: str, entities: list[Entity], document_id: str
    ) -> list[Relationship]:
        """Extract relationships between known entities in text."""
        relationships: list[Relationship] = []
        entity_name_to_id = self._build_name_index(entities)

        # Pattern-based extraction
        for rel_type, patterns in self._patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    source_name = match.group(1)
                    target_name = match.group(2)

                    source_id = self._resolve_entity(source_name, entity_name_to_id)
                    target_id = self._resolve_entity(target_name, entity_name_to_id)

                    if source_id and target_id and source_id != target_id:
                        relationships.append(Relationship(
                            source_entity_id=source_id,
                            target_entity_id=target_id,
                            relationship_type=rel_type,
                            source_document=document_id,
                            confidence=0.75,
                        ))

        # Co-occurrence based relationships (entities in same sentence likely related)
        sentences = re.split(r'[.!?]\s+', text)
        for sentence in sentences:
            entities_in_sentence = []
            for entity in entities:
                for name in entity.all_names:
                    if name.lower() in sentence.lower():
                        entities_in_sentence.append(entity)
                        break

            # Create RELATED_TO edges for co-occurring entities
            for i, e1 in enumerate(entities_in_sentence):
                for e2 in entities_in_sentence[i + 1:]:
                    if e1.entity_id != e2.entity_id:
                        relationships.append(Relationship(
                            source_entity_id=e1.entity_id,
                            target_entity_id=e2.entity_id,
                            relationship_type=RelationshipType.RELATED_TO,
                            source_document=document_id,
                            confidence=0.5,  # Lower confidence for co-occurrence
                        ))

        self.logger.info(f"Extracted {len(relationships)} relationships from document {document_id}")
        return relationships

    def _build_name_index(self, entities: list[Entity]) -> dict[str, str]:
        """Build lowercase name → entity_id mapping."""
        index: dict[str, str] = {}
        for entity in entities:
            for name in entity.all_names:
                index[name.lower()] = entity.entity_id
        return index

    def _resolve_entity(self, name: str, index: dict[str, str]) -> Optional[str]:
        """Try to resolve a name to a known entity ID."""
        return index.get(name.lower())


# ============================================================================
# Entity Resolution and Deduplication
# ============================================================================

class EntityResolver:
    """
    Resolves entities across documents - determines when two mentions
    refer to the same real-world entity.
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self.logger = logging.getLogger("entity_resolver")
        # Canonical mappings (known aliases)
        self._known_aliases: dict[str, str] = {
            "k8s": "Kubernetes",
            "kubernetes": "Kubernetes",
            "pg": "PostgreSQL",
            "postgres": "PostgreSQL",
            "postgresql": "PostgreSQL",
            "es": "Elasticsearch",
            "elastic": "Elasticsearch",
            "aws": "Amazon Web Services",
            "amazon web services": "Amazon Web Services",
            "gcp": "Google Cloud Platform",
            "google cloud": "Google Cloud Platform",
        }

    def resolve(self, new_entities: list[Entity], existing_entities: list[Entity]) -> list[Entity]:
        """
        Resolve new entities against existing ones.
        Returns deduplicated list with merged properties.
        """
        resolved: list[Entity] = []
        merged_count = 0

        for new_entity in new_entities:
            match = self._find_match(new_entity, existing_entities + resolved)
            if match:
                # Merge into existing entity
                self._merge_entities(match, new_entity)
                merged_count += 1
            else:
                # Apply canonical name normalization
                new_entity.canonical_name = self._canonicalize(new_entity.canonical_name)
                resolved.append(new_entity)

        self.logger.info(
            f"Resolved {len(new_entities)} entities: "
            f"{merged_count} merged, {len(resolved)} new"
        )
        return resolved

    def _find_match(self, entity: Entity, candidates: list[Entity]) -> Optional[Entity]:
        """Find a matching entity in candidates."""
        for candidate in candidates:
            if self._is_same_entity(entity, candidate):
                return candidate
        return None

    def _is_same_entity(self, a: Entity, b: Entity) -> bool:
        """Determine if two entities refer to the same thing."""
        # Rule 1: Same type and exact name match (case-insensitive)
        if a.entity_type == b.entity_type:
            a_names = {n.lower() for n in a.all_names}
            b_names = {n.lower() for n in b.all_names}
            if a_names & b_names:
                return True

        # Rule 2: Same canonical form
        a_canonical = self._canonicalize(a.canonical_name).lower()
        b_canonical = self._canonicalize(b.canonical_name).lower()
        if a_canonical == b_canonical:
            return True

        # Rule 3: String similarity (Jaro-Winkler or Levenshtein)
        if a.entity_type == b.entity_type:
            similarity = self._string_similarity(a.canonical_name.lower(), b.canonical_name.lower())
            if similarity >= self.similarity_threshold:
                return True

        # Rule 4: Embedding similarity (if available)
        if a.embedding is not None and b.embedding is not None:
            cosine_sim = self._cosine_similarity(a.embedding, b.embedding)
            if cosine_sim >= self.similarity_threshold:
                return True

        return False

    def _merge_entities(self, target: Entity, source: Entity) -> None:
        """Merge source entity into target."""
        # Add aliases
        for name in source.all_names:
            if name not in target.all_names:
                target.aliases.append(name)

        # Merge source documents
        for doc_id in source.source_documents:
            if doc_id not in target.source_documents:
                target.source_documents.append(doc_id)

        # Merge properties
        target.properties.update(source.properties)

        # Update confidence (take max)
        target.confidence = max(target.confidence, source.confidence)
        target.updated_at = datetime.now(timezone.utc)

    def _canonicalize(self, name: str) -> str:
        """Apply known alias mappings."""
        return self._known_aliases.get(name.lower(), name)

    def _string_similarity(self, a: str, b: str) -> float:
        """Jaro-Winkler similarity approximation."""
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0

        # Simple Levenshtein-based similarity
        max_len = max(len(a), len(b))
        if max_len == 0:
            return 1.0

        # Count matching characters
        matches = sum(1 for ca, cb in zip(a, b) if ca == cb)
        prefix_len = 0
        for ca, cb in zip(a[:4], b[:4]):
            if ca == cb:
                prefix_len += 1
            else:
                break

        base_sim = matches / max_len
        # Jaro-Winkler boost for common prefix
        return base_sim + (prefix_len * 0.1 * (1 - base_sim))

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return float(dot / norm) if norm > 0 else 0.0


# ============================================================================
# Graph Storage
# ============================================================================

class KnowledgeGraphStore:
    """
    Graph storage layer using NetworkX for demo.
    Includes Neo4j Cypher patterns for production deployment.
    """

    def __init__(self):
        self.logger = logging.getLogger("graph_store")
        if nx is None:
            raise ImportError("networkx is required: pip install networkx")
        self._graph: nx.DiGraph = nx.DiGraph()
        self._entities: dict[str, Entity] = {}
        self._relationships: dict[str, Relationship] = {}

    # --- Write Operations ---

    def add_entity(self, entity: Entity) -> str:
        """Add an entity node to the graph."""
        self._entities[entity.entity_id] = entity
        self._graph.add_node(
            entity.entity_id,
            canonical_name=entity.canonical_name,
            entity_type=entity.entity_type.value,
            aliases=entity.aliases,
            properties=entity.properties,
            confidence=entity.confidence,
        )
        self.logger.debug(f"Added entity: {entity.canonical_name} ({entity.entity_type.value})")
        return entity.entity_id

    def add_relationship(self, relationship: Relationship) -> str:
        """Add a relationship edge to the graph."""
        if relationship.source_entity_id not in self._entities:
            self.logger.warning(f"Source entity {relationship.source_entity_id} not found")
            return ""
        if relationship.target_entity_id not in self._entities:
            self.logger.warning(f"Target entity {relationship.target_entity_id} not found")
            return ""

        self._relationships[relationship.relationship_id] = relationship
        self._graph.add_edge(
            relationship.source_entity_id,
            relationship.target_entity_id,
            relationship_id=relationship.relationship_id,
            relationship_type=relationship.relationship_type.value,
            confidence=relationship.confidence,
            properties=relationship.properties,
        )
        return relationship.relationship_id

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an entity and all its relationships."""
        if entity_id not in self._entities:
            return False
        self._graph.remove_node(entity_id)
        del self._entities[entity_id]
        # Remove dangling relationships
        to_remove = [
            rid for rid, r in self._relationships.items()
            if r.source_entity_id == entity_id or r.target_entity_id == entity_id
        ]
        for rid in to_remove:
            del self._relationships[rid]
        return True

    def remove_document_entities(self, document_id: str) -> int:
        """Remove all entities sourced only from a specific document."""
        removed = 0
        to_check = [
            e for e in self._entities.values()
            if document_id in e.source_documents
        ]
        for entity in to_check:
            entity.source_documents.remove(document_id)
            if not entity.source_documents:
                self.remove_entity(entity.entity_id)
                removed += 1
        return removed

    # --- Read Operations ---

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        return self._entities.get(entity_id)

    def find_entities_by_name(self, name: str) -> list[Entity]:
        """Find entities matching a name (case-insensitive)."""
        name_lower = name.lower()
        return [
            e for e in self._entities.values()
            if name_lower in [n.lower() for n in e.all_names]
        ]

    def find_entities_by_type(self, entity_type: EntityType) -> list[Entity]:
        """Find all entities of a given type."""
        return [e for e in self._entities.values() if e.entity_type == entity_type]

    def get_neighbors(self, entity_id: str, relationship_type: Optional[RelationshipType] = None,
                      direction: str = "both") -> list[tuple[Entity, Relationship]]:
        """Get neighboring entities with their connecting relationships."""
        results: list[tuple[Entity, Relationship]] = []

        if direction in ("out", "both"):
            for _, target, data in self._graph.out_edges(entity_id, data=True):
                if relationship_type and data.get("relationship_type") != relationship_type.value:
                    continue
                entity = self._entities.get(target)
                rel = self._relationships.get(data.get("relationship_id", ""))
                if entity and rel:
                    results.append((entity, rel))

        if direction in ("in", "both"):
            for source, _, data in self._graph.in_edges(entity_id, data=True):
                if relationship_type and data.get("relationship_type") != relationship_type.value:
                    continue
                entity = self._entities.get(source)
                rel = self._relationships.get(data.get("relationship_id", ""))
                if entity and rel:
                    results.append((entity, rel))

        return results

    def get_subgraph(self, entity_id: str, max_depth: int = 2) -> dict[str, Any]:
        """Get subgraph around an entity up to max_depth hops."""
        visited: set[str] = set()
        entities: list[Entity] = []
        relationships: list[Relationship] = []

        queue: list[tuple[str, int]] = [(entity_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)

            entity = self._entities.get(current_id)
            if entity:
                entities.append(entity)

            if depth < max_depth:
                neighbors = self.get_neighbors(current_id)
                for neighbor_entity, rel in neighbors:
                    relationships.append(rel)
                    if neighbor_entity.entity_id not in visited:
                        queue.append((neighbor_entity.entity_id, depth + 1))

        return {"entities": entities, "relationships": relationships}

    # --- Graph Analytics ---

    def get_most_connected(self, top_k: int = 10) -> list[tuple[Entity, int]]:
        """Get most connected entities by degree centrality."""
        degree_map = dict(self._graph.degree())
        sorted_nodes = sorted(degree_map.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [(self._entities[nid], deg) for nid, deg in sorted_nodes if nid in self._entities]

    def find_shortest_path(self, source_id: str, target_id: str) -> list[Entity]:
        """Find shortest path between two entities."""
        try:
            path_ids = nx.shortest_path(self._graph, source_id, target_id)
            return [self._entities[nid] for nid in path_ids if nid in self._entities]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def get_connected_components(self) -> list[list[str]]:
        """Get connected components (clusters of related entities)."""
        undirected = self._graph.to_undirected()
        return [list(comp) for comp in nx.connected_components(undirected)]

    @property
    def stats(self) -> dict[str, int]:
        return {
            "total_entities": len(self._entities),
            "total_relationships": len(self._relationships),
            "total_edges": self._graph.number_of_edges(),
            "connected_components": nx.number_weakly_connected_components(self._graph),
        }

    # --- Neo4j Cypher Patterns (for production) ---

    @staticmethod
    def neo4j_create_entity_cypher(entity: Entity) -> str:
        """Generate Cypher for creating an entity in Neo4j."""
        props = {
            "entity_id": entity.entity_id,
            "canonical_name": entity.canonical_name,
            "aliases": entity.aliases,
            "confidence": entity.confidence,
            "created_at": entity.created_at.isoformat(),
        }
        props.update(entity.properties)
        props_str = json.dumps(props)
        return (
            f"CREATE (e:{entity.entity_type.value} {props_str}) "
            f"RETURN e"
        )

    @staticmethod
    def neo4j_create_relationship_cypher(rel: Relationship) -> str:
        """Generate Cypher for creating a relationship in Neo4j."""
        return (
            f"MATCH (a {{entity_id: '{rel.source_entity_id}'}}), "
            f"(b {{entity_id: '{rel.target_entity_id}'}}) "
            f"CREATE (a)-[r:{rel.relationship_type.value} {{"
            f"confidence: {rel.confidence}, "
            f"source_document: '{rel.source_document}'"
            f"}}]->(b) RETURN r"
        )

    @staticmethod
    def neo4j_multi_hop_query(start_name: str, max_hops: int = 3) -> str:
        """Generate Cypher for multi-hop traversal."""
        return (
            f"MATCH path = (start {{canonical_name: '{start_name}'}})"
            f"-[*1..{max_hops}]-(connected) "
            f"RETURN path, nodes(path) as entities, relationships(path) as rels "
            f"ORDER BY length(path) LIMIT 50"
        )

    @staticmethod
    def neo4j_find_path_cypher(source_name: str, target_name: str) -> str:
        """Generate Cypher for finding paths between entities."""
        return (
            f"MATCH path = shortestPath("
            f"(a {{canonical_name: '{source_name}'}})-[*..5]-"
            f"(b {{canonical_name: '{target_name}'}}))"
            f"RETURN path, length(path) as hops"
        )


# ============================================================================
# Graph-Based Retrieval
# ============================================================================

class GraphRetriever:
    """
    Retrieves context from the knowledge graph to augment vector search.
    Supports entity-based, relationship-based, and multi-hop retrieval.
    """

    def __init__(self, graph_store: KnowledgeGraphStore):
        self.graph = graph_store
        self.logger = logging.getLogger("graph_retriever")

    def retrieve_by_entity(self, entity_name: str, max_depth: int = 2) -> GraphQueryResult:
        """Retrieve subgraph context for a named entity."""
        entities = self.graph.find_entities_by_name(entity_name)
        if not entities:
            self.logger.info(f"Entity not found: {entity_name}")
            return GraphQueryResult(entities=[], relationships=[], confidence=0.0)

        # Get subgraph for the first (best) match
        primary = entities[0]
        subgraph = self.graph.get_subgraph(primary.entity_id, max_depth=max_depth)

        # Generate context text from graph
        context = self._subgraph_to_context(primary, subgraph)

        return GraphQueryResult(
            entities=subgraph["entities"],
            relationships=subgraph["relationships"],
            context_text=context,
            confidence=primary.confidence,
        )

    def retrieve_by_relationship(
        self,
        entity_name: str,
        relationship_type: RelationshipType,
    ) -> GraphQueryResult:
        """Find entities related by a specific relationship type."""
        entities = self.graph.find_entities_by_name(entity_name)
        if not entities:
            return GraphQueryResult(entities=[], relationships=[], confidence=0.0)

        primary = entities[0]
        neighbors = self.graph.get_neighbors(
            primary.entity_id, relationship_type=relationship_type
        )

        related_entities = [e for e, _ in neighbors]
        relationships = [r for _, r in neighbors]

        context_parts = [f"{primary.canonical_name} {relationship_type.value}:"]
        for entity, rel in neighbors:
            context_parts.append(f"  - {entity.canonical_name} (confidence: {rel.confidence:.2f})")

        return GraphQueryResult(
            entities=[primary] + related_entities,
            relationships=relationships,
            context_text="\n".join(context_parts),
            confidence=primary.confidence,
        )

    def multi_hop_traversal(
        self,
        start_entity: str,
        target_entity: Optional[str] = None,
        max_hops: int = 3,
    ) -> GraphQueryResult:
        """
        Perform multi-hop graph traversal.
        If target_entity given, find paths between them.
        Otherwise, explore outward from start_entity.
        """
        start_entities = self.graph.find_entities_by_name(start_entity)
        if not start_entities:
            return GraphQueryResult(entities=[], relationships=[], confidence=0.0)

        start = start_entities[0]

        if target_entity:
            # Find path between two entities
            target_entities = self.graph.find_entities_by_name(target_entity)
            if not target_entities:
                return GraphQueryResult(entities=[], relationships=[], confidence=0.0)

            target = target_entities[0]
            path_entities = self.graph.find_shortest_path(start.entity_id, target.entity_id)

            if not path_entities:
                return GraphQueryResult(
                    entities=[start, target],
                    relationships=[],
                    context_text=f"No path found between {start_entity} and {target_entity}",
                    confidence=0.0,
                )

            # Build context from path
            path_names = [e.canonical_name for e in path_entities]
            context = f"Path: {' → '.join(path_names)}"

            return GraphQueryResult(
                entities=path_entities,
                relationships=[],
                paths=[path_names],
                context_text=context,
                confidence=0.8,
            )
        else:
            # Explore outward
            subgraph = self.graph.get_subgraph(start.entity_id, max_depth=max_hops)
            context = self._subgraph_to_context(start, subgraph)
            return GraphQueryResult(
                entities=subgraph["entities"],
                relationships=subgraph["relationships"],
                context_text=context,
                confidence=start.confidence,
            )

    def _subgraph_to_context(self, primary: Entity, subgraph: dict) -> str:
        """Convert a subgraph into readable context text."""
        lines = [f"Knowledge about: {primary.canonical_name} ({primary.entity_type.value})"]

        if primary.properties:
            lines.append(f"Properties: {json.dumps(primary.properties)}")

        # Group relationships by type
        rel_groups: dict[str, list[str]] = defaultdict(list)
        for rel in subgraph["relationships"]:
            source = self.graph.get_entity(rel.source_entity_id)
            target = self.graph.get_entity(rel.target_entity_id)
            if source and target:
                if source.entity_id == primary.entity_id:
                    rel_groups[rel.relationship_type.value].append(target.canonical_name)
                else:
                    rel_groups[f"(inverse) {rel.relationship_type.value}"].append(source.canonical_name)

        for rel_type, targets in rel_groups.items():
            lines.append(f"  {rel_type}: {', '.join(targets)}")

        return "\n".join(lines)


# ============================================================================
# Hybrid Retrieval (Graph + Vector)
# ============================================================================

class HybridGraphVectorRetriever:
    """
    Combines graph-based retrieval with vector similarity search.
    Graph provides structured context; vectors provide semantic similarity.
    """

    def __init__(
        self,
        graph_retriever: GraphRetriever,
        vector_search_fn=None,  # In production: vector DB search function
    ):
        self.graph_retriever = graph_retriever
        self.vector_search = vector_search_fn
        self.logger = logging.getLogger("hybrid_retriever")

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        graph_weight: float = 0.3,
        vector_weight: float = 0.7,
    ) -> dict[str, Any]:
        """
        Hybrid retrieval combining graph and vector results.

        Strategy:
        1. Extract entities from query
        2. Retrieve graph context for mentioned entities
        3. Perform vector similarity search
        4. Use graph context to re-rank and enrich vector results
        5. Combine scores with configurable weights
        """
        self.logger.info(f"Hybrid retrieval for: {query[:100]}")

        # Step 1: Extract entities from query
        query_entities = self._extract_query_entities(query)
        self.logger.info(f"Query entities: {query_entities}")

        # Step 2: Graph retrieval for each entity
        graph_contexts: list[GraphQueryResult] = []
        for entity_name in query_entities:
            result = self.graph_retriever.retrieve_by_entity(entity_name, max_depth=2)
            if result.entities:
                graph_contexts.append(result)

        # Step 3: Vector search (mock)
        vector_results = await self._vector_search(query, top_k)

        # Step 4: Combine and re-rank
        combined_context = self._merge_results(
            graph_contexts, vector_results, graph_weight, vector_weight
        )

        return {
            "query": query,
            "query_entities": query_entities,
            "graph_context": "\n\n".join(gc.context_text for gc in graph_contexts),
            "vector_results": vector_results,
            "combined_context": combined_context,
            "retrieval_strategy": "hybrid_graph_vector",
        }

    def _extract_query_entities(self, query: str) -> list[str]:
        """Extract potential entity names from query."""
        # Simple extraction; in production use NER
        extractor = EntityExtractor()
        entities = extractor.extract(query, "query")
        return [e.canonical_name for e in entities]

    async def _vector_search(self, query: str, top_k: int) -> list[dict]:
        """Perform vector similarity search (mock)."""
        if self.vector_search:
            return await self.vector_search(query, top_k)
        # Mock results
        return [
            {"chunk_id": f"chunk-{i}", "score": 0.9 - i * 0.05, "content": f"Result {i}"}
            for i in range(min(top_k, 5))
        ]

    def _merge_results(
        self,
        graph_contexts: list[GraphQueryResult],
        vector_results: list[dict],
        graph_weight: float,
        vector_weight: float,
    ) -> str:
        """Merge graph and vector results into final context."""
        parts = []

        # Add graph context (structured knowledge)
        if graph_contexts:
            parts.append("=== Structured Knowledge (from Knowledge Graph) ===")
            for gc in graph_contexts:
                parts.append(gc.context_text)

        # Add vector results (semantic matches)
        if vector_results:
            parts.append("\n=== Semantic Matches (from Vector Search) ===")
            for result in vector_results:
                parts.append(f"[Score: {result.get('score', 0):.3f}] {result.get('content', '')}")

        return "\n".join(parts)


# ============================================================================
# Full Knowledge Graph Pipeline
# ============================================================================

class KnowledgeGraphPipeline:
    """
    Orchestrates the full knowledge graph pipeline:
    Document → Entity Extraction → Relationship Extraction →
    Entity Resolution → Graph Storage → Indexing
    """

    def __init__(self):
        self.entity_extractor = EntityExtractor()
        self.relationship_extractor = RelationshipExtractor()
        self.entity_resolver = EntityResolver()
        self.graph_store = KnowledgeGraphStore()
        self.graph_retriever = GraphRetriever(self.graph_store)
        self.hybrid_retriever = HybridGraphVectorRetriever(self.graph_retriever)
        self.logger = logging.getLogger("kg_pipeline")

    def process_document(self, document_id: str, text: str) -> ExtractionResult:
        """Process a document through the full KG pipeline."""
        self.logger.info(f"Processing document for KG: {document_id}")

        # Extract entities
        new_entities = self.entity_extractor.extract(text, document_id)

        # Resolve against existing entities
        existing = list(self.graph_store._entities.values())
        resolved_entities = self.entity_resolver.resolve(new_entities, existing)

        # Add resolved entities to graph
        all_entities = list(self.graph_store._entities.values()) + resolved_entities
        for entity in resolved_entities:
            self.graph_store.add_entity(entity)

        # Extract relationships
        relationships = self.relationship_extractor.extract(text, all_entities, document_id)

        # Add relationships to graph
        for rel in relationships:
            self.graph_store.add_relationship(rel)

        result = ExtractionResult(
            document_id=document_id,
            entities=resolved_entities,
            relationships=relationships,
            extraction_confidence=np.mean([e.confidence for e in resolved_entities]) if resolved_entities else 0.0,
        )

        self.logger.info(
            f"KG update: +{len(resolved_entities)} entities, +{len(relationships)} relationships | "
            f"Graph total: {self.graph_store.stats}"
        )
        return result

    def remove_document(self, document_id: str) -> int:
        """Remove all graph entries sourced from a document."""
        return self.graph_store.remove_document_entities(document_id)

    async def query(self, query: str, top_k: int = 10) -> dict[str, Any]:
        """Query the knowledge graph with hybrid retrieval."""
        return await self.hybrid_retriever.retrieve(query, top_k)


# ============================================================================
# Demo
# ============================================================================

def main():
    """Demonstrate knowledge graph construction and retrieval."""
    pipeline = KnowledgeGraphPipeline()

    # Process sample documents
    documents = [
        ("doc-001", """
        The platform team manages Kubernetes clusters on AWS. 
        Our payment service uses PostgreSQL for transaction data and Redis for caching.
        The payment service depends on the authentication service for user verification.
        John Smith owns the payment service and reports to Sarah Chen.
        The platform team uses ArgoCD for deployments and Datadog for monitoring.
        """),
        ("doc-002", """
        The authentication service is deployed on Kubernetes and uses Redis for session storage.
        It integrates with Auth0 for SSO and communicates with the user service.
        The SRE team maintains the authentication service.
        Last week's incident was caused by a Redis connection pool exhaustion.
        Maria Garcia from the SRE team resolved the incident.
        """),
        ("doc-003", """
        Our data pipeline uses Kafka for event streaming and Snowflake as the data warehouse.
        The data team owns the pipeline infrastructure.
        Spark jobs run on Kubernetes for batch processing.
        The pipeline depends on PostgreSQL CDC for change data capture.
        David Lee manages the data team.
        """),
    ]

    print("=" * 60)
    print("KNOWLEDGE GRAPH CONSTRUCTION")
    print("=" * 60)

    for doc_id, text in documents:
        result = pipeline.process_document(doc_id, text)
        print(f"\n{doc_id}: {len(result.entities)} entities, {len(result.relationships)} relationships")

    # Print graph stats
    print(f"\nGraph Statistics: {pipeline.graph_store.stats}")

    # Show most connected entities
    print("\n" + "=" * 60)
    print("MOST CONNECTED ENTITIES")
    print("=" * 60)
    for entity, degree in pipeline.graph_store.get_most_connected(5):
        print(f"  {entity.canonical_name} ({entity.entity_type.value}): {degree} connections")

    # Demo retrieval
    print("\n" + "=" * 60)
    print("GRAPH RETRIEVAL DEMOS")
    print("=" * 60)

    # Entity retrieval
    print("\n--- Entity Retrieval: 'Kubernetes' ---")
    result = pipeline.graph_retriever.retrieve_by_entity("Kubernetes")
    print(result.context_text)

    # Relationship retrieval
    print("\n--- Relationship: 'payment service' DEPENDS_ON ---")
    result = pipeline.graph_retriever.retrieve_by_relationship(
        "payment service", RelationshipType.DEPENDS_ON
    )
    print(result.context_text if result.context_text else "No results")

    # Multi-hop
    print("\n--- Multi-hop: 'Redis' (2 hops) ---")
    result = pipeline.graph_retriever.multi_hop_traversal("Redis", max_hops=2)
    print(result.context_text)

    # Path finding
    print("\n--- Path: 'Kafka' → 'Kubernetes' ---")
    result = pipeline.graph_retriever.multi_hop_traversal("Kafka", "Kubernetes", max_hops=4)
    print(result.context_text)

    # Hybrid query
    print("\n" + "=" * 60)
    print("HYBRID RETRIEVAL")
    print("=" * 60)
    import asyncio
    hybrid_result = asyncio.run(
        pipeline.query("What services depend on Redis and who maintains them?")
    )
    print(f"Query entities: {hybrid_result['query_entities']}")
    print(f"Graph context:\n{hybrid_result['graph_context']}")


if __name__ == "__main__":
    main()
