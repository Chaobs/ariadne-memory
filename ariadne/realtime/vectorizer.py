"""
Realtime Vectorizer — Coordinates real-time vectorization of AI agent conversation memories.

Manages FileWatcher and ObservationIngestor instances, provides high-level API
for CLI and Web UI integration.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from ariadne.realtime.ingestor import ObservationIngestor
from ariadne.realtime.watcher import FileWatcher
from ariadne.session.observation_store import ObservationStore
from ariadne.memory.manager import MemoryManager
from ariadne.config import get_config

logger = logging.getLogger(__name__)


class RealtimeVectorizer:
    """
    Coordinator for real-time vectorization of AI agent memory files.
    
    Provides a unified interface for:
    - Starting/stopping directory monitoring
    - Manual ingestion of files/directories
    - Configuration management
    - Status reporting
    """
    
    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        observation_store: Optional[ObservationStore] = None,
        default_memory_system: str = "default",
        watch_patterns: Optional[List[str]] = None,
        debounce_seconds: float = 2.0,
    ):
        """
        Initialize the real-time vectorizer.
        
        Args:
            memory_manager: MemoryManager instance for vector storage.
            observation_store: ObservationStore instance for observation tracking.
            default_memory_system: Default memory system name for document ingestion.
            watch_patterns: File patterns to watch (defaults to common memory files).
            debounce_seconds: Debounce interval for file events.
        """
        self.memory_manager = memory_manager or MemoryManager()
        self.observation_store = observation_store or ObservationStore()
        self.default_memory_system = default_memory_system
        self.watch_patterns = watch_patterns or [
            "*.md", "MEMORY.md", "*.txt", "*.json", "*.yaml", "*.yml"
        ]
        self.debounce_seconds = debounce_seconds
        
        # Create ingestor
        self.ingestor = ObservationIngestor(
            memory_manager=self.memory_manager,
            observation_store=self.observation_store,
            default_memory_system=self.default_memory_system,
        )
        
        # Create watcher (will be initialized when needed)
        self.watcher: Optional[FileWatcher] = None
        
        # State tracking
        self._lock = threading.RLock()
        self._is_watching = False
        self._watch_directories: List[str] = []
        self._watch_recursive = True
        
        # Statistics
        self.stats = {
            "files_processed": 0,
            "observations_created": 0,
            "documents_ingested": 0,
            "last_processed": None,
            "start_time": datetime.now().isoformat(),
        }
        
        # Load configuration
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from Ariadne config."""
        try:
            config = get_config()
            # Check for realtime vectorization settings
            realtime_config = config.get("realtime", {})
            
            if "default_memory_system" in realtime_config:
                self.default_memory_system = realtime_config["default_memory_system"]
            
            if "watch_patterns" in realtime_config:
                self.watch_patterns = realtime_config["watch_patterns"]
            
            if "debounce_seconds" in realtime_config:
                self.debounce_seconds = realtime_config["debounce_seconds"]
                
        except Exception as e:
            logger.debug(f"Failed to load realtime config: {e}")
    
    def start_watching(
        self,
        directories: List[str | Path],
        recursive: bool = True,
    ) -> bool:
        """
        Start watching directories for memory file changes.
        
        Args:
            directories: List of directory paths to watch.
            recursive: Whether to watch subdirectories recursively.
        
        Returns:
            True if watching started successfully, False otherwise.
        """
        with self._lock:
            if self._is_watching:
                logger.warning("Already watching directories")
                return False
            
            try:
                # Create watcher if not already created
                if self.watcher is None:
                    self.watcher = FileWatcher(
                        ingestor=self.ingestor,
                        patterns=self.watch_patterns,
                        debounce_seconds=self.debounce_seconds,
                    )
                
                # Start watching
                self.watcher.start(directories, recursive)
                
                # Update state
                self._is_watching = True
                self._watch_directories = [str(Path(d).resolve()) for d in directories]
                self._watch_recursive = recursive
                
                logger.info(f"Started watching {len(directories)} directories")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start watching: {e}")
                return False
    
    def stop_watching(self) -> bool:
        """
        Stop watching all directories.
        
        Returns:
            True if stopped successfully, False otherwise.
        """
        with self._lock:
            if not self._is_watching or self.watcher is None:
                logger.warning("Not currently watching")
                return False
            
            try:
                self.watcher.stop()
                self._is_watching = False
                self._watch_directories = []
                logger.info("Stopped watching directories")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop watching: {e}")
                return False
    
    def ingest_file(
        self,
        file_path: str | Path,
        create_observations: bool = True,
        ingest_as_documents: bool = True,
        **kwargs,
    ) -> Tuple[List[Any], List[str]]:
        """
        Manually ingest a memory file.
        
        Args:
            file_path: Path to the memory file.
            create_observations: Whether to create Observation records.
            ingest_as_documents: Whether to ingest as documents into vector storage.
            **kwargs: Additional arguments passed to ObservationIngestor.ingest_file.
        
        Returns:
            Tuple of (list of observations, list of document IDs).
        """
        try:
            observations, doc_ids = self.ingestor.ingest_file(
                file_path,
                create_observations=create_observations,
                ingest_as_documents=ingest_as_documents,
                **kwargs,
            )
            
            # Update statistics
            with self._lock:
                self.stats["files_processed"] += 1
                self.stats["observations_created"] += len(observations)
                self.stats["documents_ingested"] += len(doc_ids)
                self.stats["last_processed"] = datetime.now().isoformat()
            
            logger.info(f"Ingested file {file_path}: {len(observations)} observations, {len(doc_ids)} documents")
            return observations, doc_ids
            
        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")
            return [], []
    
    def ingest_directory(
        self,
        directory: str | Path,
        pattern: str = "*.md",
        recursive: bool = True,
        **kwargs,
    ) -> Tuple[List[Any], List[str]]:
        """
        Manually ingest all matching files in a directory.
        
        Args:
            directory: Directory path to ingest.
            pattern: File pattern to match.
            recursive: Whether to search subdirectories recursively.
            **kwargs: Additional arguments passed to ObservationIngestor.ingest_directory.
        
        Returns:
            Tuple of (list of observations, list of document IDs).
        """
        try:
            observations, doc_ids = self.ingestor.ingest_directory(
                directory,
                pattern=pattern,
                recursive=recursive,
                **kwargs,
            )
            
            # Update statistics
            with self._lock:
                self.stats["files_processed"] += len(doc_ids)  # Approximate file count
                self.stats["observations_created"] += len(observations)
                self.stats["documents_ingested"] += len(doc_ids)
                self.stats["last_processed"] = datetime.now().isoformat()
            
            logger.info(f"Ingested directory {directory}: {len(observations)} observations, {len(doc_ids)} documents")
            return observations, doc_ids
            
        except Exception as e:
            logger.error(f"Failed to ingest directory {directory}: {e}")
            return [], []
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the real-time vectorizer.
        
        Returns:
            Dictionary with status information.
        """
        with self._lock:
            status = {
                "is_watching": self._is_watching,
                "watch_directories": self._watch_directories.copy(),
                "watch_recursive": self._watch_recursive,
                "default_memory_system": self.default_memory_system,
                "watch_patterns": self.watch_patterns.copy(),
                "debounce_seconds": self.debounce_seconds,
                "stats": self.stats.copy(),
            }
            
            # Add watcher-specific status if available
            if self.watcher is not None:
                status["watcher_running"] = self.watcher.is_running()
                status["watched_directories"] = self.watcher.get_watched_directories()
            else:
                status["watcher_running"] = False
                status["watched_directories"] = []
            
            return status
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration.
        
        Returns:
            Dictionary with configuration.
        """
        return {
            "default_memory_system": self.default_memory_system,
            "watch_patterns": self.watch_patterns,
            "debounce_seconds": self.debounce_seconds,
        }
    
    def update_config(self, **kwargs) -> bool:
        """
        Update configuration parameters.
        
        Args:
            **kwargs: Configuration parameters to update.
        
        Returns:
            True if configuration was updated successfully, False otherwise.
        """
        with self._lock:
            try:
                # Update allowed parameters
                if "default_memory_system" in kwargs:
                    self.default_memory_system = kwargs["default_memory_system"]
                    self.ingestor.default_memory_system = self.default_memory_system
                
                if "watch_patterns" in kwargs:
                    self.watch_patterns = kwargs["watch_patterns"]
                
                if "debounce_seconds" in kwargs:
                    self.debounce_seconds = kwargs["debounce_seconds"]
                
                # If watcher exists and is running, we may need to restart it
                # For now, just update the patterns in the watcher if possible
                if self.watcher is not None and "watch_patterns" in kwargs:
                    # Note: FileWatcher doesn't have a method to update patterns dynamically
                    # Would need to restart watching
                    logger.warning("Pattern changes require watcher restart")
                
                logger.info(f"Updated configuration: {kwargs}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to update configuration: {e}")
                return False
    
    def reset_stats(self) -> None:
        """Reset statistics."""
        with self._lock:
            self.stats = {
                "files_processed": 0,
                "observations_created": 0,
                "documents_ingested": 0,
                "last_processed": None,
                "start_time": datetime.now().isoformat(),
            }
            logger.info("Statistics reset")
    
    def is_watching(self) -> bool:
        """Check if currently watching directories."""
        return self._is_watching
    
    def get_watched_directories(self) -> List[str]:
        """Get list of currently watched directories."""
        return self._watch_directories.copy()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop watching if active."""
        if self._is_watching:
            self.stop_watching()