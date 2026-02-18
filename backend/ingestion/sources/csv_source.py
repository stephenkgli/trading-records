"""CSV file import source."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.ingestion.csv_importer import CSVImporter
from backend.ingestion.sources.base import ImportSource, SourceRegistry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.schemas.trade import NormalizedTrade


@SourceRegistry.register
class CSVSource(ImportSource):
    """Import source for CSV file uploads (IBKR and Tradovate formats)."""

    source_name = "csv"

    def fetch_normalized_trades(
        self,
        *,
        db: Session | None = None,
        file_content: bytes | str = b"",
        filename: str = "upload.csv",
        **kwargs: object,
    ) -> list[NormalizedTrade]:
        """Parse a CSV file and return normalized trades.

        Args:
            db: Unused for CSV (parsing is stateless).
            file_content: Raw CSV bytes or string.
            filename: Original filename for format detection.

        Returns:
            Parsed and normalized trades.
        """
        importer = CSVImporter()

        if isinstance(file_content, bytes):
            text = file_content.decode("utf-8-sig")
        else:
            text = file_content

        fmt = importer._detect_format(text)

        from backend.ingestion.csv_importer import CSVFormat

        if fmt == CSVFormat.IBKR:
            return importer._parse_ibkr_csv(text, filename)
        elif fmt == CSVFormat.TRADOVATE:
            return importer._parse_tradovate_csv(text, filename)
        elif fmt == CSVFormat.TRADOVATE_PERF:
            return importer._parse_tradovate_performance_csv(text, filename)
        else:
            raise ValueError(
                f"Unknown CSV format for file '{filename}'. "
                "Could not detect IBKR or Tradovate format from headers."
            )
