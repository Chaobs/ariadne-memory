"""
File Watcher — Monitors directories for changes to AI agent memory files.

Uses watchdog to detect file creation, modification, and deletion events.
Triggers real-time ingestion via ObservationIngestor.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import List, Optional, Callable, Set
from datetime import datetime, timedelta

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    # Dummy classes for when watchdog is not available
    class FileSystemEventHandler:
        pass
    class Observer:
        pass

from ariadne.realtime.ingestor import ObservationIngestor

logger = logging.getLogger(__name__)


class MemoryFileHandler(FileSystemEventHandler):
    """
    Watchdog event handler for memory file changes.
    """
    
    def __init__(
        self,
        ingestor: ObservationIngestor,
        patterns: Optional[List[str]] = None,
        debounce_seconds: float = 2.0,
    ):
        """
        Initialize the handler.
        
        Args:
            ingestor: ObservationIngestor instance to process file changes.
            patterns: List of filename patterns to watch (e.g., ["*.md", "MEMORY.md"]).
                     If None, defaults to common memory file patterns.
            debounce_seconds: Debounce interval to prevent rapid re-processing.
        """
        self.ingestor = ingestor
        self.patterns = patterns or ["*.md", "*.txt", "*.json", "*.yaml", "*.yml"]
        self.debounce_seconds = debounce_seconds
        
        # Track recently processed files to avoid duplicates
        self.recent_files: dict[str, float] = {}
        
        # Compile patterns for faster matching
        from fnmatch import fnmatch
        self._fnmatch = fnmatch
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory:
            self._process_event(event.src_path, "created")
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if not event.is_directory:
            self._process_event(event.src_path, "modified")
    
    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move/rename events."""
        if not event.is_directory:
            # Process both source (deleted) and destination (created)
            if event.src_path:
                self._process_event(event.src_path, "deleted")
            if event.dest_path:
                self._process_event(event.dest_path, "created")
    
    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        if not event.is_directory:
            self._process_event(event.src_path, "deleted")
    
    def _process_event(self, file_path: str, event_type: str) -> None:
        """
        Process a file system event with debouncing and pattern filtering.
        """
        # Check if file matches our patterns
        if not self._matches_pattern(file_path):
            return
        
        # Debounce: ignore if recently processed
        now = time.time()
        if file_path in self.recent_files:
            last_time = self.recent_files[file_path]
            if now - last_time < self.debounce_seconds:
                logger.debug(f"Debouncing {event_type} event for {file_path}")
                return
        
        # Update recent files tracking
        self.recent_files[file_path] = now
        
        # Clean up old entries from recent_files
        cutoff = now - (self.debounce_seconds * 10)  # Keep entries for 10x debounce interval
        self.recent_files = {
            k: v for k, v in self.recent_files.items() if v > cutoff
        }
        
        # Process based on event type
        if event_type == "created" or event_type == "modified":
            self._ingest_file(file_path, event_type)
        elif event_type == "deleted":
            self._handle_deletion(file_path)
    
    def _matches_pattern(self, file_path: str) -> bool:
        """Check if file path matches any of the watch patterns."""
        filename = Path(file_path).name
        for pattern in self.patterns:
            if self._fnmatch(filename, pattern):
                return True
        return False
    
    def _ingest_file(self, file_path: str, event_type: str) -> None:
        """Ingest a file that was created or modified."""
        try:
            logger.info(f"Processing {event_type} file: {file_path}")
            
            # Use the ingestor to process the file
            observations, doc_ids = self.ingestor.ingest_file(
                file_path,
                create_observations=True,
                ingest_as_documents=True,
            )
            
            logger.info(f"Ingested {len(observations)} observations from {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")
    
    def _handle_deletion(self, file_path: str) -> None:
        """Handle file deletion (currently just logs)."""
        logger.info(f"File deleted: {file_path}")
        # TODO: Implement deletion from vector storage if needed


class FileWatcher:
    """
    Watches directories for memory file changes and triggers real-time ingestion.
    
    This class manages one or more watchdog observers and provides
    start/stop control.
    """
    
    def __init__(
        self,
        ingestor: Optional[ObservationIngestor] = None,
        patterns: Optional[List[str]] = None,
        debounce_seconds: float = 2.0,
    ):
        """
        Initialize the file watcher.
        
        Args:
            ingestor: ObservationIngestor instance. If None, a default one will be created.
            patterns: File patterns to watch.
            debounce_seconds: Debounce interval for file events.
        """
        if not WATCHDOG_AVAILABLE:
            raise ImportError(
                "watchdog package is required for file watching. "
                "Install with: pip install watchdog"
            )
        
        self.ingestor = ingestor or ObservationIngestor()
        self.patterns = patterns
        self.debounce_seconds = debounce_seconds
        
        self.observer: Optional[Observer] = None
        self.handlers: dict[str, MemoryFileHandler] = {}
        self.watched_directories: Set[str] = set()
        
        self._lock = threading.RLock()
        self._running = False
    
    def start(self, directories: List[str | Path], recursive: bool = True) -> None:
        """
        Start watching the specified directories.
        
        Args:
            directories: List of directory paths to watch.
            recursive: Whether to watch subdirectories recursively.
        """
        if not directories:
            logger.warning("No directories specified for watching")
            return
        
        with self._lock:
            if self._running:
                logger.warning("FileWatcher is already running")
                return
            
            self.observer = Observer()
            
            for dir_path in directories:
                path = Path(dir_path).resolve()
                if not path.exists() or not path.is_dir():
                    logger.warning(f"Directory does not exist: {path}")
                    continue
                
                # Create handler for this directory
                handler = MemoryFileHandler(
                    ingestor=self.ingestor,
                    patterns=self.patterns,
                    debounce_seconds=self.debounce_seconds,
                )
                
                # Schedule watching
                self.observer.schedule(
                    handler,
                    str(path),
                    recursive=recursive,
                )
                
                self.handlers[str(path)] = handler
                self.watched_directories.add(str(path))
                logger.info(f"Started watching directory: {path} (recursive={recursive})")
            
            if not self.watched_directories:
                logger.error("No valid directories to watch")
                return
            
            # Start the observer
            self.observer.start()
            self._running = True
            logger.info(f"FileWatcher started with {len(self.watched_directories)} directories")
    
    def stop(self) -> None:
        """Stop watching all directories."""
        with self._lock:
            if not self._running or self.observer is None:
                return
            
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None
            self._running = False
            
            self.handlers.clear()
            self.watched_directories.clear()
            logger.info("FileWatcher stopped")
    
    def add_directory(self, directory: str | Path, recursive: bool = True) -> bool:
        """
        Add a directory to watch while the watcher is running.
        
        Args:
            directory: Directory path to add.
            recursive: Whether to watch subdirectories recursively.
        
        Returns:
            True if directory was added successfully, False otherwise.
        """
        if not self._running or self.observer is None:
            logger.error("Cannot add directory: FileWatcher is not running")
            return False
        
        path = Path(directory).resolve()
        if not path.exists() or not path.is_dir():
            logger.warning(f"Directory does not exist: {path}")
            return False
        
        if str(path) in self.watched_directories:
            logger.warning(f"Directory already being watched: {path}")
            return True
        
        # Create handler
        handler = MemoryFileHandler(
            ingestor=self.ingestor,
            patterns=self.patterns,
            debounce_seconds=self.debounce_seconds,
        )
        
        # Schedule watching
        self.observer.schedule(handler, str(path), recursive=recursive)
        
        self.handlers[str(path)] = handler
        self.watched_directories.add(str(path))
        logger.info(f"Added directory to watch: {path} (recursive={recursive})")
        return True
    
    def remove_directory(self, directory: str | Path) -> bool:
        """
        Remove a directory from being watched.
        
        Args:
            directory: Directory path to remove.
        
        Returns:
            True if directory was removed successfully, False otherwise.
        """
        # Note: watchdog doesn't provide an unschedule API easily.
        # We'll need to stop and restart the observer.
        logger.warning("remove_directory not fully implemented - need to restart observer")
        return False
    
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._running
    
    def get_watched_directories(self) -> List[str]:
        """Get list of currently watched directories."""
        return list(self.watched_directories)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop watching."""
        self.stop()