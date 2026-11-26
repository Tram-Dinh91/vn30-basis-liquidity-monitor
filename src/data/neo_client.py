"""Alias for backwards compatibility. Implementation moved to src.neo_api.client."""
from src.neo_api.client import NeoApiClient, RateLimiter

__all__ = ["NeoApiClient", "RateLimiter"]
