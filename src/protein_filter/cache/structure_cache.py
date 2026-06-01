"""Structure caching module for protein_filter_lib.

This module provides LRU caching for PDB structure parsing to avoid
repeated parsing of the same PDB files, improving performance for
batch processing of thousands of structures.
"""

from collections import OrderedDict
from typing import Optional
from Bio.PDB import PDBParser, Structure
import threading


class StructureCache:
    """
    LRU cache for PDB structures.
    
    Uses OrderedDict for O(1) LRU eviction.
    Thread-safe for concurrent access.
    """
    _cache: OrderedDict[str, Structure] = OrderedDict()
    _max_size: int = 128
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get(cls, pdb_path: str, force_reload: bool = False) -> Structure:
        """
        Get structure from cache or parse if not cached.
        
        Args:
            pdb_path: Path to PDB file
            force_reload: If True, ignore cache and reload
            
        Returns:
            Biopython Structure object
        """
        with cls._lock:
            if not force_reload and pdb_path in cls._cache:
                cls._cache.move_to_end(pdb_path)
                return cls._cache[pdb_path]
            
            parser = PDBParser(QUIET=True)
            structure = parser.get_structure("s", pdb_path)
            
            if len(cls._cache) >= cls._max_size:
                cls._cache.popitem(last=False)
            
            cls._cache[pdb_path] = structure
            return structure

    @classmethod
    def clear(cls) -> None:
        """Clear all cached structures."""
        with cls._lock:
            cls._cache.clear()

    @classmethod
    def remove(cls, pdb_path: str) -> bool:
        """
        Remove specific entry from cache.
        
        Returns:
            True if entry existed and was removed
        """
        with cls._lock:
            if pdb_path in cls._cache:
                del cls._cache[pdb_path]
                return True
            return False

    @classmethod
    def size(cls) -> int:
        """Get current cache size."""
        with cls._lock:
            return len(cls._cache)

    @classmethod
    def set_max_size(cls, max_size: int) -> None:
        """Set maximum cache size."""
        with cls._lock:
            cls._max_size = max_size
            while len(cls._cache) > cls._max_size:
                cls._cache.popitem(last=False)


def get_cached_structure(pdb_path: str, force_reload: bool = False) -> Structure:
    """
    Convenience function to get cached structure.
    
    Args:
        pdb_path: Path to PDB file
        force_reload: If True, reload from disk
        
    Returns:
        Biopython Structure object
    """
    return StructureCache.get(pdb_path, force_reload)


def clear_structure_cache() -> None:
    """Clear the structure cache."""
    StructureCache.clear()


def get_cache_stats() -> dict:
    """Get cache statistics."""
    return {
        "current_size": StructureCache.size(),
        "max_size": StructureCache._max_size,
    }