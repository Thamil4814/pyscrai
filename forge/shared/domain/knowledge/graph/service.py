"""Graph Analysis Service for PyScrAI Forge.

Analyzes relationships and builds/updates the knowledge graph.
"""

import asyncio
from typing import Dict, List, Any
from forge.shared.core.event_bus import EventBus, EventPayload
from forge.shared.core import events


class GraphAnalysisService:
    """Analyzes relationships and maintains the knowledge graph."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        # In-memory graph structure (replace with DuckDB later)
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []
    
    async def start(self):
        """Start the service by subscribing to relationship events."""
        await self.event_bus.subscribe(
            events.TOPIC_RELATIONSHIP_FOUND, 
            self.handle_relationship_found
        )
    
    async def handle_relationship_found(self, payload: EventPayload):
        """Process discovered relationships and update the graph."""
        doc_id = payload.get("doc_id", "unknown")
        relationships = payload.get("relationships", [])

        # Simulate graph analysis (replace with real logic later)
        await asyncio.sleep(0.2)

        # Add nodes and edges to the graph
        for rel in relationships:
            source = rel.get("source")
            target = rel.get("target")

            # Add nodes if they don't exist
            if source and source not in self._nodes:
                self._nodes[source] = {
                    "id": source,
                    "type": rel.get("source_type") or "Unknown",
                    "label": source,
                }

            if target and target not in self._nodes:
                self._nodes[target] = {
                    "id": target,
                    "type": rel.get("target_type") or "Unknown",
                    "label": target,
                }

            # Add edge
            edge = {
                "source": source,
                "target": target,
                "type": rel.get("relation_type"),
                "confidence": rel.get("confidence", 1.0),
                "doc_id": doc_id,
            }
            self._edges.append(edge)

        # --- Ensure all referenced entities are present in nodes ---
        referenced_ids = set()
        for edge in self._edges:
            if edge["source"]:
                referenced_ids.add(edge["source"])
            if edge["target"]:
                referenced_ids.add(edge["target"])
        for entity_id in referenced_ids:
            if entity_id not in self._nodes:
                self._nodes[entity_id] = {
                    "id": entity_id,
                    "type": "Unknown",
                    "label": entity_id,
                }

        # Emit graph update event
        graph_stats = {
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "nodes": list(self._nodes.values()),
            "edges": self._edges,
        }

        await self.event_bus.publish(
            events.TOPIC_GRAPH_UPDATED,
            events.create_graph_updated_event(
                doc_id=doc_id,
                graph_stats=graph_stats,
            )
        )
