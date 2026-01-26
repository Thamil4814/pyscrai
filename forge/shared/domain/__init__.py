"""
Shared Domain Module
====================

Business logic for extraction, resolution, graph, intelligence, and session management.
"""

# Extraction
from forge.shared.domain.ingestion.extraction.service import DocumentExtractionService

# Resolution
from forge.shared.domain.knowledge.resolution.service import EntityResolutionService
from forge.shared.domain.knowledge.resolution.deduplication_service import DeduplicationService

# Graph
from forge.shared.domain.knowledge.graph.service import GraphAnalysisService
from forge.shared.domain.knowledge.graph.advanced_analyzer import AdvancedGraphAnalysisService

# Intelligence
from forge.shared.domain.analysis.profiler import SemanticProfilerService
from forge.shared.domain.synthesis.narrative import NarrativeSynthesisService
from forge.shared.domain.synthesis.reporting import EntityCardService
from forge.shared.domain.synthesis.streaming import IntelligenceStreamingService

# Interaction
from forge.shared.domain.workflow.interaction.workflow_service import UserInteractionWorkflowService

# Session
from forge.shared.domain.context.session.session_manager import SessionManager

__all__ = [
    # Extraction
    "DocumentExtractionService",
    # Resolution
    "EntityResolutionService",
    "DeduplicationService",
    # Graph
    "GraphAnalysisService",
    "AdvancedGraphAnalysisService",
    # Intelligence
    "SemanticProfilerService",
    "NarrativeSynthesisService",
    "EntityCardService",
    "IntelligenceStreamingService",
    # Interaction
    "UserInteractionWorkflowService",
    # Session
    "SessionManager",
]
