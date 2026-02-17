"""Cache manager for repository summaries."""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import logging
import threading

logger = logging.getLogger(__name__)


class CacheManager:
    """Thread-safe in-memory cache for repository summaries."""
    
    def __init__(self, ttl_minutes: int = 60):
        """
        Initialize cache manager.
        
        Args:
            ttl_minutes: Time-to-live for cache entries in minutes
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(minutes=ttl_minutes)
        self._lock = threading.Lock()
    
    def _get_key(self, owner: str, repo: str) -> str:
        """
        Generates cache key for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            MD5 hash of owner/repo
        """
        return hashlib.md5(f"{owner}/{repo}".lower().encode()).hexdigest()
    
    def get(self, owner: str, repo: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Gets cached summary if exists and not expired.
        
        Args:
            owner: Repository owner
            repo: Repository name
            force_refresh: If True, bypass cache and return None
            
        Returns:
            Cached data dict or None
        """
        if force_refresh:
            logger.debug(f"Cache bypass requested for {owner}/{repo}")
            return None
        
        key = self._get_key(owner, repo)
        
        with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                if datetime.now() < entry["expires_at"]:
                    logger.info(f"Cache hit for {owner}/{repo}")
                    return entry["data"]
                else:
                    # Expired, remove from cache
                    del self.cache[key]
                    logger.debug(f"Cache expired for {owner}/{repo}")
        
        logger.debug(f"Cache miss for {owner}/{repo}")
        return None
    
    def set(self, owner: str, repo: str, data: Dict[str, Any]) -> None:
        """
        Caches a summary (thread-safe).
        
        Args:
            owner: Repository owner
            repo: Repository name
            data: Data to cache
        """
        key = self._get_key(owner, repo)
        
        with self._lock:
            self.cache[key] = {
                "data": data,
                "expires_at": datetime.now() + self.ttl
            }
        
        logger.info(f"Cached summary for {owner}/{repo}")
    
    def invalidate(self, owner: str, repo: str) -> None:
        """
        Removes a cached entry (thread-safe).
        
        Args:
            owner: Repository owner
            repo: Repository name
        """
        key = self._get_key(owner, repo)
        
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                logger.info(f"Invalidated cache for {owner}/{repo}")
    
    def clear(self) -> None:
        """Clears all cached entries."""
        with self._lock:
            self.cache.clear()
            logger.info("Cache cleared")


# Global cache instance
cache_manager = CacheManager()
