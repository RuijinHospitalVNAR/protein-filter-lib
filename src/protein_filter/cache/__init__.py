"""Cache module for protein_filter_lib.

Provides caching mechanisms for expensive operations like PDB parsing.
"""

from protein_filter.cache.structure_cache import (
    StructureCache,
    get_cached_structure,
    clear_structure_cache,
    get_cache_stats,
)

__all__ = [
    "StructureCache",
    "get_cached_structure",
    "clear_structure_cache",
    "get_cache_stats",
]