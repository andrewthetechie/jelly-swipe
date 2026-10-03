"""Domain-layer modules (framework-free business objects).

Kept separate from ``services`` (orchestration) and ``repositories`` (data
access) so that both can depend on it without creating a cycle. ``Deck``
owns deck JSON and ``MatchFacts`` owns the match fact set.
"""

from jellyswipe.domain.deck import Card, Deck
from jellyswipe.domain.match_facts import MatchFacts

__all__ = ["Card", "Deck", "MatchFacts"]
