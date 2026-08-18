"""Domain-layer modules (framework-free business objects).

Kept separate from ``services`` (orchestration) and ``repositories`` (data
access) so that both can depend on it without creating a cycle. ``Deck`` is
the first resident.
"""

from jellyswipe.domain.deck import Card, Deck

__all__ = ["Card", "Deck"]
