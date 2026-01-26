"""Export Service for PyScrAI Forge.

Provides data export capabilities in various formats.
"""

from __future__ import annotations

import json
import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting data in various formats."""
    
    def __init__(self, db_connection):
        """Initialize the export service.
        
        Args:
            db_connection: DuckDB connection for querying data
        """
        self.db_conn = db_connection
        self.service_name = "ExportService"
    
    async def export_entities_json(
        self,
        output_path: Path,
        filters: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Export entities to JSON format.
        
        Args:
            output_path: Path to output file
            filters: Optional filters (entity_type, min_relationships, etc.)
            
        Returns:
            Path to exported file
        """
        query = "SELECT id, type, label, created_at, updated_at FROM entities WHERE 1=1"
        params = []
        
        if filters:
            if "entity_type" in filters:
                query += " AND type = ?"
                params.append(filters["entity_type"])
            if "min_relationships" in filters:
                # This would require a join, simplified for now
                pass
        
        rows = self.db_conn.execute(query, params).fetchall()
        
        entities = []
        for row in rows:
            entities.append({
                "id": row[0],
                "type": row[1],
                "label": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None,
            })
        
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "format_version": "1.0",
            "entity_count": len(entities),
            "entities": entities,
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(entities)} entities to {output_path}")
        return output_path
    
    async def export_entities_csv(
        self,
        output_path: Path,
        filters: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Export entities to CSV format.
        
        Args:
            output_path: Path to output file
            filters: Optional filters
            
        Returns:
            Path to exported file
        """
        query = "SELECT id, type, label, created_at, updated_at FROM entities WHERE 1=1"
        params = []
        
        if filters:
            if "entity_type" in filters:
                query += " AND type = ?"
                params.append(filters["entity_type"])
        
        rows = self.db_conn.execute(query, params).fetchall()
        
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "type", "label", "created_at", "updated_at"])
            
            for row in rows:
                created_at = row[3].isoformat() if row[3] else ""
                updated_at = row[4].isoformat() if row[4] else ""
                writer.writerow([row[0], row[1], row[2], created_at, updated_at])
        
        logger.info(f"Exported {len(rows)} entities to {output_path}")
        return output_path
    
    async def export_relationships_json(
        self,
        output_path: Path,
        filters: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Export relationships to JSON format.
        
        Args:
            output_path: Path to output file
            filters: Optional filters (relationship_type, min_confidence, etc.)
            
        Returns:
            Path to exported file
        """
        query = "SELECT source, target, type, confidence, doc_id, created_at FROM relationships WHERE 1=1"
        params = []
        
        if filters:
            if "relationship_type" in filters:
                query += " AND type = ?"
                params.append(filters["relationship_type"])
            if "min_confidence" in filters:
                query += " AND confidence >= ?"
                params.append(filters["min_confidence"])
        
        rows = self.db_conn.execute(query, params).fetchall()
        
        relationships = []
        for row in rows:
            relationships.append({
                "source": row[0],
                "target": row[1],
                "type": row[2],
                "confidence": float(row[3]) if row[3] else 0.0,
                "doc_id": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
            })
        
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "format_version": "1.0",
            "relationship_count": len(relationships),
            "relationships": relationships,
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(relationships)} relationships to {output_path}")
        return output_path
    
    async def export_graph_json(
        self,
        output_path: Path,
        include_analytics: bool = True
    ) -> Path:
        """Export complete graph to JSON format.
        
        Args:
            output_path: Path to output file
            include_analytics: Whether to include graph analytics
            
        Returns:
            Path to exported file
        """
        # Export entities
        entities_query = "SELECT id, type, label, created_at, updated_at FROM entities"
        entity_rows = self.db_conn.execute(entities_query).fetchall()
        
        entities = []
        for row in entity_rows:
            entities.append({
                "id": row[0],
                "type": row[1],
                "label": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None,
            })
        
        # Export relationships
        rel_query = "SELECT source, target, type, confidence, doc_id, created_at FROM relationships"
        rel_rows = self.db_conn.execute(rel_query).fetchall()
        
        relationships = []
        for row in rel_rows:
            relationships.append({
                "source": row[0],
                "target": row[1],
                "type": row[2],
                "confidence": float(row[3]) if row[3] else 0.0,
                "doc_id": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
            })
        
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "format_version": "1.0",
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "entities": entities,
            "relationships": relationships,
        }
        
        if include_analytics:
            # Add basic graph statistics
            export_data["analytics"] = {
                "total_nodes": len(entities),
                "total_edges": len(relationships),
                "entity_types": {},
            }
            
            # Count entity types
            for entity in entities:
                entity_type = entity["type"]
                export_data["analytics"]["entity_types"][entity_type] = \
                    export_data["analytics"]["entity_types"].get(entity_type, 0) + 1
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported graph with {len(entities)} entities and {len(relationships)} relationships to {output_path}")
        return output_path
    
    async def export_intelligence_report(
        self,
        output_path: Path,
        include_profiles: bool = True,
        include_narratives: bool = True,
        include_analytics: bool = True
    ) -> Path:
        """Export comprehensive intelligence report.
        
        Args:
            output_path: Path to output file
            include_profiles: Whether to include semantic profiles
            include_narratives: Whether to include narratives
            include_analytics: Whether to include graph analytics
            
        Returns:
            Path to exported file
        """
        report: Dict[str, Any] = {
            "export_timestamp": datetime.now().isoformat(),
            "format_version": "1.0",
            "report_type": "intelligence_summary",
        }
        
        # Export graph data
        graph_data = await self.export_graph_json(output_path.parent / "temp_graph.json")
        with open(graph_data, "r", encoding="utf-8") as f:
            graph_export = json.load(f)
        
        report["graph"] = {
            "entities": graph_export["entities"],
            "relationships": graph_export["relationships"],
        }
        
        if include_analytics:
            report["graph"]["analytics"] = graph_export.get("analytics", {})
        
        # Note: Semantic profiles and narratives would need to be stored
        # in the database or retrieved from the intelligence services
        # For now, we'll include placeholders
        
        if include_profiles:
            report["semantic_profiles"] = []  # Would be populated from intelligence services
        
        if include_narratives:
            report["narratives"] = []  # Would be populated from intelligence services
        
        # Clean up temp file
        graph_data.unlink()
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported intelligence report to {output_path}")
        return output_path
    
    async def export_markdown(
        self,
        output_path: Path,
        include_narratives: bool = True,
        include_profiles: bool = True
    ) -> Path:
        """Export data to Markdown format.
        
        Args:
            output_path: Path to output file
            include_narratives: Whether to include narratives
            include_profiles: Whether to include semantic profiles
            
        Returns:
            Path to exported file
        """
        md_content = []
        
        # Header
        md_content.append(f"# PyScrAI Intelligence Export")
        md_content.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        md_content.append("")
        
        # Pre-load semantic profiles for efficient lookup
        entity_profiles = {}
        if include_profiles:
            try:
                profiles_query = "SELECT entity_id, profile_json FROM semantic_profiles"
                profile_rows = self.db_conn.execute(profiles_query).fetchall()
                for row in profile_rows:
                    entity_id, profile_json = row
                    try:
                        entity_profiles[entity_id] = json.loads(profile_json)
                    except (json.JSONDecodeError, TypeError):
                        entity_profiles[entity_id] = {"raw": profile_json}
            except Exception as e:
                logger.debug(f"Semantic profiles table not available or error: {e}")
        
        # Entities section
        md_content.append("## Entities")
        md_content.append("")
        
        entities_query = "SELECT id, type, label FROM entities ORDER BY type, label"
        entity_rows = self.db_conn.execute(entities_query).fetchall()
        
        if entity_rows:
            current_type = None
            for row in entity_rows:
                entity_id, entity_type, label = row
                
                # Add type header if changed
                if entity_type != current_type:
                    current_type = entity_type
                    md_content.append(f"### {entity_type}")
                    md_content.append("")
                
                # Add entity with enhanced details
                md_content.append(f"#### **{label}** (ID: `{entity_id}`)")
                md_content.append("")
                
                # Add semantic profile if available
                if entity_id in entity_profiles:
                    profile = entity_profiles[entity_id]
                    md_content.append("**Semantic Profile:**")
                    
                    if isinstance(profile, dict):
                        if "summary" in profile:
                            md_content.append(f"- **Summary**: {profile['summary']}")
                        if "attributes" in profile and isinstance(profile["attributes"], list):
                            md_content.append(f"- **Attributes**: {', '.join(profile['attributes'])}")
                        if "key_relationships" in profile and isinstance(profile["key_relationships"], list):
                            md_content.append(f"- **Key Relationships**: {', '.join(profile['key_relationships'])}")
                        if "confidence" in profile:
                            md_content.append(f"- **Confidence**: {profile['confidence']:.0%}")
                        
                        # Add any other profile fields
                        skip_fields = {"summary", "attributes", "key_relationships", "confidence", "entity_id", "raw"}
                        for key, value in profile.items():
                            if key not in skip_fields:
                                md_content.append(f"- **{key.replace('_', ' ').title()}**: {value}")
                    else:
                        md_content.append(f"```\n{profile}\n```")
                    
                    md_content.append("")
                
                md_content.append("---")
                md_content.append("")
        else:
            md_content.append("*No entities found*")
            md_content.append("")
        
        # Relationships section
        md_content.append("## Relationships")
        md_content.append("")
        
        rel_query = """
        SELECT r.source, r.target, r.type, r.confidence, r.doc_id,
               e1.label as source_label, e2.label as target_label
        FROM relationships r
        LEFT JOIN entities e1 ON r.source = e1.id
        LEFT JOIN entities e2 ON r.target = e2.id
        ORDER BY r.type, r.confidence DESC
        """
        rel_rows = self.db_conn.execute(rel_query).fetchall()
        
        if rel_rows:
            current_type = None
            for row in rel_rows:
                source_id, target_id, rel_type, confidence, doc_id, source_label, target_label = row
                
                # Add type header if changed
                if rel_type != current_type:
                    current_type = rel_type
                    md_content.append(f"### {rel_type}")
                    md_content.append("")
                
                # Add relationship with enhanced details
                source_text = source_label or source_id
                target_text = target_label or target_id
                confidence_text = f" (confidence: {confidence:.2f})" if confidence else ""
                
                md_content.append(f"#### **{source_text}** → **{target_text}**{confidence_text}")
                md_content.append("")
                
                # Add doc_id if available
                if doc_id:
                    md_content.append(f"*Source: {doc_id}*")
                    md_content.append("")
                
                md_content.append("---")
                md_content.append("")
        else:
            md_content.append("*No relationships found*")
            md_content.append("")
        
        # Narratives section (document-level narratives)
        if include_narratives:
            try:
                # Try both possible narrative table structures
                try:
                    narratives_query = "SELECT doc_id, narrative FROM narratives ORDER BY doc_id"
                    narrative_rows = self.db_conn.execute(narratives_query).fetchall()
                except:
                    # Fallback for entity-based narratives
                    narratives_query = "SELECT entity_id as doc_id, narrative FROM narratives ORDER BY entity_id"
                    narrative_rows = self.db_conn.execute(narratives_query).fetchall()
                
                if narrative_rows:
                    md_content.append("## Document Narratives")
                    md_content.append("")
                    
                    for row in narrative_rows:
                        doc_id, narrative = row
                        
                        md_content.append(f"### Document: {doc_id}")
                        md_content.append("")
                        md_content.append(narrative)
                        md_content.append("")
                        md_content.append("---")
                        md_content.append("")
            except Exception as e:
                logger.debug(f"Narratives table not available or error: {e}")
        
        # Statistics
        md_content.append("## Statistics")
        md_content.append("")
        md_content.append(f"- **Total Entities**: {len(entity_rows)}")
        md_content.append(f"- **Total Relationships**: {len(rel_rows)}")
        
        if include_profiles:
            md_content.append(f"- **Entities with Semantic Profiles**: {len(entity_profiles)}")
        
        # Entity type breakdown
        entity_types = {}
        for row in entity_rows:
            entity_type = row[1]
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        if entity_types:
            md_content.append("")
            md_content.append("### Entity Types")
            for entity_type, count in sorted(entity_types.items()):
                md_content.append(f"- **{entity_type}**: {count}")
        
        md_content.append("")
        md_content.append("---")
        md_content.append("*Exported by PyScrAI Forge*")
        
        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))
        
        logger.info(f"Exported data to markdown: {output_path}")
        return output_path
