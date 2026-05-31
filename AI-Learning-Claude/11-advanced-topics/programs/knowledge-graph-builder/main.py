"""
Knowledge Graph Builder

Demonstrates building a knowledge graph from unstructured text using LLMs,
then querying it for multi-hop reasoning.

Key insight: Knowledge graphs capture STRUCTURE that vector search misses.
"How is person A connected to company B?" requires following relationship chains,
not finding similar text chunks.
"""

import json
import os
from pathlib import Path

import networkx as nx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()


# --- Entity and Relation Extraction ---

def extract_entities_and_relations(text: str) -> dict:
    """
    Use an LLM to extract entities and their relationships from text.
    
    This is the core of knowledge graph construction:
    1. Find the "nouns" (entities)
    2. Find the "verbs" connecting them (relations)
    """
    prompt = """Extract entities and relationships from the following text.

Return a JSON object with:
- "entities": list of {"name": string, "type": string} where type is one of: Person, Organization, Product, Technology, Location, Event, Concept
- "relations": list of {"source": string, "target": string, "relation": string}

Rules:
- Entity names should be normalized (e.g., "Sarah Chen" not "she")
- Relations should be concise verb phrases (e.g., "founded", "works_at", "acquired")
- Extract ALL meaningful relationships, including implicit ones

Text:
"""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a knowledge graph extraction expert. Return only valid JSON."},
            {"role": "user", "content": prompt + text}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)


# --- Graph Building ---

class KnowledgeGraph:
    """
    A knowledge graph built on top of NetworkX.
    
    Nodes = Entities (people, orgs, products, etc.)
    Edges = Relationships (founded, works_at, acquired, etc.)
    """
    
    def __init__(self):
        self.graph = nx.DiGraph()  # Directed graph (relations have direction)
    
    def add_entity(self, name: str, entity_type: str):
        """Add an entity node to the graph."""
        self.graph.add_node(name, type=entity_type)
    
    def add_relation(self, source: str, target: str, relation: str):
        """Add a relationship edge between two entities."""
        # Ensure nodes exist
        if source not in self.graph:
            self.graph.add_node(source, type="Unknown")
        if target not in self.graph:
            self.graph.add_node(target, type="Unknown")
        
        self.graph.add_edge(source, target, relation=relation)
    
    def build_from_extraction(self, extraction: dict):
        """Build graph from LLM extraction output."""
        for entity in extraction.get("entities", []):
            self.add_entity(entity["name"], entity["type"])
        
        for rel in extraction.get("relations", []):
            self.add_relation(rel["source"], rel["target"], rel["relation"])
    
    def find_path(self, source: str, target: str) -> list[dict]:
        """
        Find how two entities are connected (multi-hop reasoning).
        
        This is what vector search CANNOT do:
        "How is Sarah Chen connected to AWS?"
        Sarah Chen → founded → Nextera → runs_on → AWS
        """
        # Find source and target (case-insensitive)
        source_node = self._find_node(source)
        target_node = self._find_node(target)
        
        if not source_node or not target_node:
            return []
        
        try:
            # Find shortest path in undirected version (for reachability)
            undirected = self.graph.to_undirected()
            path = nx.shortest_path(undirected, source_node, target_node)
            
            # Build the relationship chain
            chain = []
            for i in range(len(path) - 1):
                # Check both directions for the edge
                if self.graph.has_edge(path[i], path[i+1]):
                    rel = self.graph[path[i]][path[i+1]]["relation"]
                    chain.append({"from": path[i], "relation": rel, "to": path[i+1]})
                elif self.graph.has_edge(path[i+1], path[i]):
                    rel = self.graph[path[i+1]][path[i]]["relation"]
                    chain.append({"from": path[i+1], "relation": rel, "to": path[i]})
                else:
                    chain.append({"from": path[i], "relation": "connected_to", "to": path[i+1]})
            
            return chain
        except nx.NetworkXNoPath:
            return []
    
    def get_neighbors(self, entity: str) -> list[dict]:
        """Get all direct relationships for an entity."""
        node = self._find_node(entity)
        if not node:
            return []
        
        relations = []
        
        # Outgoing edges
        for _, target, data in self.graph.out_edges(node, data=True):
            relations.append({
                "direction": "outgoing",
                "relation": data.get("relation", "related_to"),
                "entity": target,
                "entity_type": self.graph.nodes[target].get("type", "Unknown")
            })
        
        # Incoming edges
        for source, _, data in self.graph.in_edges(node, data=True):
            relations.append({
                "direction": "incoming",
                "relation": data.get("relation", "related_to"),
                "entity": source,
                "entity_type": self.graph.nodes[source].get("type", "Unknown")
            })
        
        return relations
    
    def _find_node(self, name: str) -> str | None:
        """Find a node by case-insensitive name match."""
        name_lower = name.lower()
        for node in self.graph.nodes():
            if node.lower() == name_lower or name_lower in node.lower():
                return node
        return None
    
    def visualize_text(self) -> str:
        """Text-based visualization of the graph."""
        lines = []
        lines.append(f"\n{'='*60}")
        lines.append(f"KNOWLEDGE GRAPH: {self.graph.number_of_nodes()} entities, {self.graph.number_of_edges()} relationships")
        lines.append(f"{'='*60}\n")
        
        # Group entities by type
        entities_by_type: dict[str, list[str]] = {}
        for node, data in self.graph.nodes(data=True):
            etype = data.get("type", "Unknown")
            entities_by_type.setdefault(etype, []).append(node)
        
        lines.append("ENTITIES:")
        for etype, entities in sorted(entities_by_type.items()):
            lines.append(f"  [{etype}]: {', '.join(sorted(entities))}")
        
        lines.append(f"\nRELATIONSHIPS:")
        for source, target, data in self.graph.edges(data=True):
            rel = data.get("relation", "related_to")
            lines.append(f"  {source} --[{rel}]--> {target}")
        
        return "\n".join(lines)
    
    def answer_question(self, question: str) -> str:
        """
        Use the knowledge graph to answer a question.
        
        Strategy:
        1. Extract entities from the question
        2. Find relevant subgraph
        3. Use LLM to synthesize answer from graph context
        """
        # Extract entities from question
        extraction = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract entity names mentioned in this question. Return JSON: {\"entities\": [\"name1\", \"name2\"]}"},
                {"role": "user", "content": question}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        
        entities = json.loads(extraction.choices[0].message.content).get("entities", [])
        
        # Gather graph context
        context_parts = []
        
        for entity in entities:
            neighbors = self.get_neighbors(entity)
            if neighbors:
                for n in neighbors:
                    if n["direction"] == "outgoing":
                        context_parts.append(f"{entity} --[{n['relation']}]--> {n['entity']}")
                    else:
                        context_parts.append(f"{n['entity']} --[{n['relation']}]--> {entity}")
        
        # If two entities, find path between them
        if len(entities) >= 2:
            path = self.find_path(entities[0], entities[1])
            if path:
                path_str = " → ".join([f"{p['from']} --[{p['relation']}]--> {p['to']}" for p in path])
                context_parts.append(f"\nPath from {entities[0]} to {entities[1]}: {path_str}")
        
        if not context_parts:
            return "Could not find relevant information in the knowledge graph."
        
        # Generate answer using graph context
        graph_context = "\n".join(context_parts)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Answer the question using ONLY the knowledge graph relationships provided. Explain the reasoning chain."},
                {"role": "user", "content": f"Knowledge Graph Context:\n{graph_context}\n\nQuestion: {question}"}
            ],
            temperature=0
        )
        
        return response.choices[0].message.content


# --- Main ---

def main():
    print("\n" + "="*60)
    print("KNOWLEDGE GRAPH BUILDER")
    print("Extracts entities & relations, enables multi-hop reasoning")
    print("="*60)
    
    # Load sample text
    sample_path = Path(__file__).parent / "sample_text.txt"
    if not sample_path.exists():
        print("Error: sample_text.txt not found")
        return
    
    text = sample_path.read_text()
    print(f"\nLoaded text: {len(text)} characters")
    
    # Step 1: Extract entities and relations
    print("\n[Step 1] Extracting entities and relationships using LLM...")
    
    # Process in paragraphs for better extraction
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    kg = KnowledgeGraph()
    
    for i, paragraph in enumerate(paragraphs):
        print(f"  Processing paragraph {i+1}/{len(paragraphs)}...")
        extraction = extract_entities_and_relations(paragraph)
        kg.build_from_extraction(extraction)
    
    # Step 2: Visualize the graph
    print(kg.visualize_text())
    
    # Step 3: Interactive queries
    print("\n" + "="*60)
    print("QUERY THE KNOWLEDGE GRAPH")
    print("="*60)
    
    # Demo queries
    demo_queries = [
        ("neighbors", "Sarah Chen"),
        ("path", "Sarah Chen", "AWS"),
        ("question", "How is David Kim connected to Google?"),
        ("question", "What is the relationship between Sequoia Capital and CloudMesh?"),
    ]
    
    for query in demo_queries:
        if query[0] == "neighbors":
            entity = query[1]
            print(f"\n--- All relationships for '{entity}' ---")
            neighbors = kg.get_neighbors(entity)
            if neighbors:
                for n in neighbors:
                    arrow = "-->" if n["direction"] == "outgoing" else "<--"
                    print(f"  {arrow} [{n['relation']}] {n['entity']} ({n['entity_type']})")
            else:
                print(f"  Entity '{entity}' not found in graph")
        
        elif query[0] == "path":
            source, target = query[1], query[2]
            print(f"\n--- Path from '{source}' to '{target}' ---")
            path = kg.find_path(source, target)
            if path:
                for step in path:
                    print(f"  {step['from']} --[{step['relation']}]--> {step['to']}")
            else:
                print(f"  No path found")
        
        elif query[0] == "question":
            question = query[1]
            print(f"\n--- Question: {question} ---")
            answer = kg.answer_question(question)
            print(f"  Answer: {answer}")
    
    # Interactive mode
    print("\n" + "="*60)
    print("INTERACTIVE MODE (type 'quit' to exit)")
    print("Commands:")
    print("  neighbors <entity>  - Show all connections")
    print("  path <A> to <B>     - Find connection path")
    print("  <question>          - Ask a question")
    print("="*60)
    
    while True:
        user_input = input("\n> ").strip()
        if not user_input or user_input.lower() == "quit":
            break
        
        if user_input.startswith("neighbors "):
            entity = user_input[10:].strip()
            neighbors = kg.get_neighbors(entity)
            if neighbors:
                for n in neighbors:
                    arrow = "-->" if n["direction"] == "outgoing" else "<--"
                    print(f"  {arrow} [{n['relation']}] {n['entity']} ({n['entity_type']})")
            else:
                print(f"  Entity not found. Available: {list(kg.graph.nodes())[:10]}")
        
        elif " to " in user_input and user_input.startswith("path "):
            parts = user_input[5:].split(" to ")
            if len(parts) == 2:
                path = kg.find_path(parts[0].strip(), parts[1].strip())
                if path:
                    for step in path:
                        print(f"  {step['from']} --[{step['relation']}]--> {step['to']}")
                else:
                    print("  No path found")
        else:
            answer = kg.answer_question(user_input)
            print(f"  {answer}")


if __name__ == "__main__":
    main()
