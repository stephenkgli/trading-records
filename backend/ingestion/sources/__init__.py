"""Pluggable import source interface and registry.

Each import source implements the ImportSource protocol.
New sources can be registered without modifying the pipeline.
"""

from backend.ingestion.sources.base import ImportSource, SourceRegistry

__all__ = ["ImportSource", "SourceRegistry"]
