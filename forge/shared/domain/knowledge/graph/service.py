"""Graph Analysis Service for PyScrAI Forge.

Analyzes relationships and builds/updates the knowledge graph.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from forge.shared.core.event_bus import EventBus, EventPayload
from forge.shared.core import events

logger = logging.getLogger(__name__)


class GraphAnalysisService:
    """Analyzes relationships and maintains the knowledge graph."""
    
    def __init__(self, event_bus: EventBus, db_connection=None):
        self.event_bus = event_bus
        self.db_conn = db_connection
        # Fallback in-memory graph structure (used only if db_connection is None)
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []
    
    def update_db_connection(self, db_connection):
        """Update the database connection after initialization."""
        self.db_conn = db_connection
        logger.info("GraphAnalysisService: Database connection updated")
    
    async def start(self):
        """Start the service by subscribing to entity and relationship events."""
        # Subscribe to entity extraction events
        await self.event_bus.subscribe(
            events.TOPIC_ENTITY_EXTRACTED,
            self.handle_entity_extracted
        )
        # Subscribe to relationship events
        await self.event_bus.subscribe(
            events.TOPIC_RELATIONSHIP_FOUND, 
            self.handle_relationship_found
        )

    async def handle_entity_extracted(self, payload: EventPayload):
        """Process extracted entities and update the graph."""
        doc_id = payload.get("doc_id", "unknown")
        entities = payload.get("entities", [])

        logger.debug(f"GraphAnalysisService: Received ENTITY_EXTRACTED event for doc {doc_id}")
        logger.info(f"GraphAnalysisService: ✅ Activated - processing {len(entities)} entities")

        # Small delay for database persistence service to finish writing entities
        await asyncio.sleep(0.5)

        if self.db_conn:
            graph_data = self._query_graph_from_db(doc_id)
            nodes = graph_data["nodes"]
            edges = graph_data["edges"]
        else:
            # Fallback in-memory update
            for entity in entities:
                e_id = entity.get("text") # Assuming text as ID for in-memory simple version
                if e_id and e_id not in self._nodes:
                    self._nodes[e_id] = {
                        "id": e_id,
                        "type": entity.get("type", "Unknown"),
                        "label": e_id,
                        "attributes": entity.get("attributes", {})
                    }
            nodes = list(self._nodes.values())
            edges = self._edges

        # Emit graph update to trigger Profiler/Inference
        graph_stats = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

        await self.event_bus.publish(
            events.TOPIC_GRAPH_UPDATED,
            events.create_graph_updated_event(
                doc_id=doc_id,
                graph_stats=graph_stats,
            )
        )
        logger.info(f"GraphAnalysisService: Published GRAPH_UPDATED event (entities only update)")
    
    def _query_graph_from_db(self, doc_id: Optional[str] = None) -> Dict[str, Any]:
        """Query the database for graph data.
        
        Args:
            doc_id: Optional document ID to filter by
            
        Returns:
            Dictionary with nodes and edges from the database
        """
        if not self.db_conn:
            logger.warning("GraphAnalysisService: No database connection, using in-memory data")
            return {
                "nodes": list(self._nodes.values()),
                "edges": self._edges,
            }
        
        try:
            # Always get all entities, regardless of relationships
            entities_query = "SELECT id, type, label, attributes_json FROM entities"
            entity_results = self.db_conn.execute(entities_query).fetchall()
            
            nodes = []
            for row in entity_results:
                nodes.append({
                    "id": row[0],
                    "type": row[1] or "Unknown",
                    "label": row[2] or row[0],
                    "attributes": row[3] if len(row) > 3 else {},
                })
            
            # Query relationships (edges)
            if doc_id and doc_id != "unknown":
                relationships_query = """
                    SELECT source, target, type, confidence, doc_id
                    FROM relationships
                    WHERE doc_id = ?
                """
                relationship_results = self.db_conn.execute(relationships_query, [doc_id]).fetchall()
            else:
                relationships_query = "SELECT source, target, type, confidence, doc_id FROM relationships"
                relationship_results = self.db_conn.execute(relationships_query).fetchall()
            
            edges = []
            for row in relationship_results:
                edges.append({
                    "source": row[0],
                    "target": row[1],
                    "type": row[2],
                    "confidence": float(row[3]) if row[3] else 1.0,
                    "doc_id": row[4] if len(row) > 4 else "unknown",
                })
            
            logger.info(f"GraphAnalysisService: Queried {len(nodes)} nodes and {len(edges)} edges from database")
            return {
                "nodes": nodes,
                "edges": edges,
            }
        except Exception as e:
            logger.error(f"GraphAnalysisService: Error querying database: {e}", exc_info=True)
            # Fallback to in-memory
            return {
                "nodes": list(self._nodes.values()),
                "edges": self._edges,
            }
    
    
    async def handle_relationship_found(self, payload: EventPayload):
        """Process discovered relationships and update the graph."""
        doc_id = payload.get("doc_id", "unknown")
        relationships = payload.get("relationships", [])
        
        logger.debug(f"GraphAnalysisService: Received RELATIONSHIP_FOUND event for doc {doc_id}")
        logger.info(f"GraphAnalysisService: ✅ Activated - processing {len(relationships)} relationships")

        # Small delay for database to persist changes from other services
        await asyncio.sleep(0.2)
        
        # If using database connection, query fresh data from DB
        # Otherwise, update in-memory structures (fallback)
        if self.db_conn:
            # Query database for current graph state
            graph_data = self._query_graph_from_db(doc_id)
            nodes = graph_data["nodes"]
            edges = graph_data["edges"]
        else:
            # Fallback: Update in-memory graph structure
            logger.warning("GraphAnalysisService: Using in-memory graph (no database connection)")
            
            # Add nodes and edges to the in-memory graph
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

            # Ensure all referenced entities are present in nodes
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
            
            nodes = list(self._nodes.values())
            edges = self._edges

        # Emit graph update event with current graph state
        graph_stats = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

        await self.event_bus.publish(
            events.TOPIC_GRAPH_UPDATED,
            events.create_graph_updated_event(
                doc_id=doc_id,
                graph_stats=graph_stats,
            )
        )
        
        logger.info(f"GraphAnalysisService: Published GRAPH_UPDATED event ({len(nodes)} nodes, {len(edges)} edges)")
