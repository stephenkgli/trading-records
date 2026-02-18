"""Base import source protocol and source registry.

All import sources must implement the ImportSource protocol so the
ingestion pipeline can orchestrate them without coupling to concrete
implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.schemas.import_result import ImportResult
    from backend.schemas.trade import NormalizedTrade


class ImportSource(ABC):
    """Abstract interface for a pluggable import source.

    Subclasses must declare a unique ``source_name`` and implement
    ``fetch_normalized_trades`` to produce ``NormalizedTrade`` records.
    """

    source_name: str = "unknown"

    @abstractmethod
    def fetch_normalized_trades(
        self, *, db: Session | None = None, **kwargs: object
    ) -> list[NormalizedTrade]:
        """Fetch and normalize trades from the source.

        Returns:
            A list of NormalizedTrade records ready for validation and import.
        """


class SourceRegistry:
    """Registry of available import sources.

    Sources register themselves at import time so the pipeline can look
    them up by name at runtime.
    """

    _sources: dict[str, type[ImportSource]] = {}

    @classmethod
    def register(cls, source_cls: type[ImportSource]) -> type[ImportSource]:
        """Register an import source class.

        Can be used as a decorator::

            @SourceRegistry.register
            class MySource(ImportSource):
                source_name = "my_source"
                ...
        """
        cls._sources[source_cls.source_name] = source_cls
        return source_cls

    @classmethod
    def get(cls, name: str) -> type[ImportSource] | None:
        """Look up a registered source by name."""
        return cls._sources.get(name)

    @classmethod
    def available(cls) -> list[str]:
        """Return the names of all registered sources."""
        return list(cls._sources.keys())
