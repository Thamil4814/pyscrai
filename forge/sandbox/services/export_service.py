"""Export service for creating simulation packages from Sandbox projects.

This service creates portable zip archives containing:
- intel.duckdb (raw extraction data)
- world.duckdb (sandbox enrichments)  
- manifest.json (package metadata)
- templates/ directory (project-specific templates)
"""

import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Union

class ExportService:
    """Service for exporting complete simulation packages."""
    
    def create_package(self, project_path: Path, output_path: Optional[Path] = None) -> Path:
        """Create a simulation package archive.
        
        Args:
            project_path: Path to the project directory
            output_path: Output path for the zip file (optional)
            
        Returns:
            Path to the created zip archive
        """
        project_path = Path(project_path)
        # If the path is not already in forge/data/projects, update it
        if not str(project_path).replace('\\','/').startswith('forge/data/projects/'):
            project_path = Path('forge/data/projects') / project_path.name
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{project_path.name}_simulation_{timestamp}.zip"
            output_path = project_path.parent / filename
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create manifest
        manifest = self._create_manifest(project_path)
        
        # Create zip archive
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            
            # Add intel.duckdb (required)
            intel_path = project_path / "intel.duckdb"
            if intel_path.exists():
                zipf.write(intel_path, "intel.duckdb")
            else:
                raise FileNotFoundError(f"intel.duckdb not found in {project_path}")
            
            # Add world.duckdb (if exists)
            world_path = project_path / "world.duckdb"
            if world_path.exists():
                zipf.write(world_path, "world.duckdb")
            
            # Add config.json (if exists)
            config_path = project_path / "config.json"
            if config_path.exists():
                zipf.write(config_path, "config.json")
            
            # Add templates directory (if exists)
            templates_path = project_path / "templates"
            if templates_path.exists():
                for template_file in templates_path.rglob("*"):
                    if template_file.is_file():
                        arcname = f"templates/{template_file.relative_to(templates_path)}"
                        zipf.write(template_file, arcname)
            
            # Add manifest.json
            zipf.writestr("manifest.json", json.dumps(manifest, indent=2))
        
        return output_path
    
    def _create_manifest(self, project_path: Path) -> Dict[str, Any]:
        """Create package manifest with metadata."""
        import getpass
        
        # Load project config if available
        config_data = {}
        config_path = project_path / "config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except Exception:
                pass
        
        # Get database stats
        intel_stats = self._get_database_stats(project_path / "intel.duckdb")
        world_stats = self._get_database_stats(project_path / "world.duckdb")
        
        manifest = {
            "format_version": "1.0",
            "package_type": "pyscrai_simulation",
            "timestamp": datetime.now().isoformat(),
            "project_name": project_path.name,
            "author": getpass.getuser(),  # Current username
            "description": f"Simulation package for {project_path.name}",
            
            "contents": {
                "intel_db": intel_stats,
                "world_db": world_stats,
                "has_config": (project_path / "config.json").exists(),
                "has_templates": (project_path / "templates").exists(),
                "template_count": len(list((project_path / "templates").glob("*.j2"))) if (project_path / "templates").exists() else 0
            },
            
            "metadata": {
                "extractor_config": config_data,
                "export_timestamp": datetime.now().isoformat(),
                "export_version": "3.0.0"
            }
        }
        
        return manifest
    
    def _get_database_stats(self, db_path: Path) -> Dict[str, Union[bool, int, float, str]]:
        """Get basic statistics from a database file."""
        stats: Dict[str, Union[bool, int, float, str]] = {
            "exists": False,
            "size_mb": 0.0,
            "entity_count": 0,
            "relationship_count": 0,
            "agent_count": 0,
            "location_count": 0,
            "error": ""
        }
        if not db_path.exists():
            return stats
        try:
            import duckdb
            conn = duckdb.connect(str(db_path), read_only=True)
            stats["exists"] = True
            stats["size_mb"] = round(db_path.stat().st_size / (1024*1024), 2)
            # Try to get table counts
            try:
                # Check entities table
                result = conn.execute("SELECT COUNT(*) FROM entities").fetchone()
                stats["entity_count"] = result[0] if result else 0
            except:
                stats["entity_count"] = 0
            try:
                # Check relationships table  
                result = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()
                stats["relationship_count"] = result[0] if result else 0
            except:
                stats["relationship_count"] = 0
            # For world.duckdb, check additional tables
            if "world" in str(db_path):
                try:
                    result = conn.execute("SELECT COUNT(*) FROM active_agents").fetchone()
                    stats["agent_count"] = result[0] if result else 0
                except:
                    stats["agent_count"] = 0
                try:
                    result = conn.execute("SELECT COUNT(*) FROM spatial_bookmarks").fetchone()
                    stats["location_count"] = result[0] if result else 0
                except:
                    stats["location_count"] = 0
            conn.close()
        except Exception as e:
            stats["error"] = str(e)
        return stats
    
    def import_package(self, archive_path: Path, target_dir: Path) -> Dict[str, Any]:
        """Import a simulation package to a target directory.
        
        Args:
            archive_path: Path to the zip archive
            target_dir: Directory to extract to
            
        Returns:
            Import result with status and metadata
        """
        archive_path = Path(archive_path)
        target_dir = Path(target_dir)
        
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")
        
        # Create target directory
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract archive
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            zipf.extractall(target_dir)
        
        # Load and validate manifest
        manifest_path = target_dir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        else:
            manifest = {"error": "No manifest found"}
        
        # Verify critical files
        intel_exists = (target_dir / "intel.duckdb").exists()
        world_exists = (target_dir / "world.duckdb").exists()
        config_exists = (target_dir / "config.json").exists()
        
        return {
            "status": "success" if intel_exists else "error",
            "manifest": manifest,
            "files": {
                "intel_db": intel_exists,
                "world_db": world_exists,
                "config": config_exists
            },
            "target_path": target_dir
        }