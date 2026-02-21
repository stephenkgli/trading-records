"""Error hierarchy for market data providers."""


class ProviderError(Exception):
    """Base exception for provider errors."""

    pass


class ProviderAuthError(ProviderError):
    """Authentication failed."""

    pass


class ProviderDataError(ProviderError):
    """No data available for symbol/range."""

    pass


# RateLimitError is in rate_limit.py (not a ProviderError subclass,
# since it's a local safety check, not a remote provider failure)
