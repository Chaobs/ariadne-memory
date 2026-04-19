"""
Ariadne Memory Manager — Multi-memory system management.

Supports:
- Multiple independent memory stores (like separate notebooks)
- CRUD operations: create, rename, move, delete, list
- Merge multiple memory systems into a new one
- Each memory system is a separate ChromaDB collection

All data stored under project root: .ariadne/memories/
"""

import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Use project-local paths instead of user home directory
from ariadne.paths import MEMORIES_DIR

from ariadne.memory.store import VectorStore


class MemorySystem:
    """Represents a single memory system (collection)."""
    
    def __init__(self, name: str, path: str, description: str = ""):
        self.name = name
        self.path = path  # Directory path for this memory system
        self.description = description
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "MemorySystem":
        ms = cls(
            name=data["name"],
            path=data["path"],
            description=data.get("description", ""),
        )
        ms.created_at = data.get("created_at", datetime.now().isoformat())
        ms.updated_at = data.get("updated_at", datetime.now().isoformat())
        return ms


class MemoryManager:
    """
    Manages multiple memory systems.
    
    Each memory system is stored in a separate directory under the base path.
    A manifest file tracks all memory systems.
    
    Usage:
        >>> manager = MemoryManager()
        >>> manager.create("Research Notes")
        >>> store = manager.get_store("Research Notes")
        >>> store.add(documents)
        >>> manager.list_systems()
    """
    
    DEFAULT_COLLECTION = "default"
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize MemoryManager.
        
        Args:
            base_dir: Base directory for all memory systems.
                     Defaults to .ariadne/memories/ under project root.
        """
        if base_dir is None:
            base_dir = str(MEMORIES_DIR)
        
        # Robust path handling
        try:
            self.base_dir = Path(base_dir).expanduser().resolve()
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            # Fallback to temp directory if home is not writable
            import tempfile
            self.base_dir = Path(tempfile.gettempdir()) / "ariadne_memories"
            self.base_dir.mkdir(parents=True, exist_ok=True)
            print(f"Warning: Using fallback directory {self.base_dir}")
        
        self.manifest_path = self.base_dir / "manifest.json"
        self._manifest: Dict[str, dict] = {}
        # Cache of open VectorStore instances so we can close them before file operations
        self._stores: Dict[str, "VectorStore"] = {}
        self._load_manifest()
    
    def _load_manifest(self) -> None:
        """Load manifest from disk."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    self._manifest = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._manifest = {}
        
        # Ensure default system exists
        if self.DEFAULT_COLLECTION not in self._manifest:
            self.create(self.DEFAULT_COLLECTION, "Default memory system", silent=True)

        # Clean up orphaned ChromaDB files left at memories root
        # (e.g. from old versions or interrupted operations)
        self._cleanup_orphaned_db_files()
    
    def _save_manifest(self) -> None:
        """Save manifest to disk."""
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self._manifest, f, indent=2, ensure_ascii=False)
    
    def _get_system_dir(self, name: str) -> Path:
        """Get directory path for a memory system."""
        # Sanitize name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "_- " else "_" for c in name)
        return self.base_dir / safe_name
    
    # === CRUD Operations ===
    
    def create(self, name: str, description: str = "", silent: bool = False) -> bool:
        """
        Create a new memory system.
        
        Args:
            name: Name of the memory system (must be unique)
            description: Optional description
            silent: If True, don't raise error on duplicate
            
        Returns:
            True if created, False if already exists (unless silent)
        """
        if name in self._manifest:
            if silent:
                return True
            raise ValueError(f"Memory system '{name}' already exists")
        
        system_dir = self._get_system_dir(name)
        if system_dir.exists():
            raise ValueError(f"Directory already exists: {system_dir}")
        
        # Create directory
        system_dir.mkdir(parents=True, exist_ok=True)
        
        # Create metadata
        ms = MemorySystem(
            name=name,
            path=str(system_dir),
            description=description,
        )
        
        # Add to manifest
        self._manifest[name] = ms.to_dict()
        self._save_manifest()
        
        if not silent:
            print(f"Created memory system: {name}")
        
        return True
    
    def rename(self, old_name: str, new_name: str) -> bool:
        """
        Rename a memory system.
        
        Args:
            old_name: Current name
            new_name: New name (must not exist)
            
        Returns:
            True if renamed successfully
        """
        if old_name not in self._manifest:
            raise ValueError(f"Memory system '{old_name}' not found")
        
        if new_name in self._manifest:
            raise ValueError(f"Memory system '{new_name}' already exists")
        
        # Close VectorStore to release chroma.sqlite3 file lock
        self._close_store(old_name)
        
        old_dir = Path(self._manifest[old_name]["path"])
        new_dir = self._get_system_dir(new_name)
        
        # Guard against shutil.move nesting: if new_dir already exists on disk,
        # shutil.move(src, dst) will move src **inside** dst instead of
        # replacing it — producing the dreaded nested-dir layout (e.g. B/A).
        if new_dir.exists():
            if new_dir.is_dir() and any(new_dir.iterdir()):
                raise ValueError(
                    f"Target directory already exists and is non-empty: {new_dir}\n"
                    f"This would cause nesting. Please delete or move '{new_dir}' first."
                )
            # Empty dir — safe to remove so shutil.move can create it fresh
            try:
                new_dir.rmdir()
            except OSError:
                pass
        
        # Move directory (with retry for Windows file locks)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                shutil.move(str(old_dir), str(new_dir))
                break
            except PermissionError as e:
                import time
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    # Force garbage collection to release any remaining handles
                    import gc; gc.collect()
                else:
                    raise e
        
        # Update manifest
        del self._manifest[old_name]
        self._manifest[new_name] = {
            **self._manifest.get(new_name, {}),
            "name": new_name,
            "path": str(new_dir),
            "updated_at": datetime.now().isoformat(),
        }
        self._save_manifest()
        
        print(f"Renamed '{old_name}' to '{new_name}'")
        return True
    
    def move(self, name: str, new_parent_dir: str) -> bool:
        """
        Move a memory system to a different parent directory.
        
        Args:
            name: Name of the memory system
            new_parent_dir: New parent directory path
            
        Returns:
            True if moved successfully
        """
        if name not in self._manifest:
            raise ValueError(f"Memory system '{name}' not found")
        
        old_path = Path(self._manifest[name]["path"])
        new_parent = Path(new_parent_dir)
        new_parent.mkdir(parents=True, exist_ok=True)
        
        new_path = new_parent / old_path.name
        shutil.move(str(old_path), str(new_path))
        
        self._manifest[name]["path"] = str(new_path)
        self._manifest[name]["updated_at"] = datetime.now().isoformat()
        self._save_manifest()
        
        print(f"Moved '{name}' to {new_path}")
        return True
    
    def delete(self, name: str, confirm: bool = True) -> bool:
        """
        Delete a memory system.
        
        Args:
            name: Name of the memory system
            confirm: If True, requires explicit confirmation (use False for testing)
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If memory system not found or is default system
        """
        if name not in self._manifest:
            raise ValueError(f"Memory system '{name}' not found")
        
        if name == self.DEFAULT_COLLECTION:
            raise ValueError("Cannot delete the default memory system")
        
        # Get info before deletion for warning message
        info = self.get_info(name)
        doc_count = info.get("document_count", 0) if info else 0
        
        if confirm:
            warning = f"""
[DANGER] You are about to delete a memory system!

  Name: {name}
  Documents: {doc_count}
  Path: {self._manifest[name]["path"]}

This operation CANNOT be undone. All data will be permanently deleted.

Type 'yes' to confirm deletion: """
            response = input(warning)
            if response.lower() != "yes":
                print("Deletion cancelled.")
                return False
        
        # Remove from manifest
        path = self._manifest[name]["path"]
        del self._manifest[name]
        self._save_manifest()
        
        # Close VectorStore to release chroma.sqlite3 file lock
        self._close_store(name)
        
        # Delete directory with retries (Windows file locks need time to release)
        if Path(path).exists():
            max_retries = 5
            last_error = None
            for attempt in range(max_retries):
                try:
                    shutil.rmtree(path)
                    break
                except (OSError, PermissionError) as e:
                    import time, gc
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))  # Increasing backoff
                        gc.collect()  # Force GC to release file handles
                    else:
                        # Final attempt: try deleting individual files
                        print(f"Warning: Could not fully delete directory {path}: {last_error}")
                        try:
                            self._force_delete_recursive(Path(path))
                            break
                        except Exception as e2:
                            print(f"Error: Force delete also failed for {path}: {e2}")
        
        print(f"Deleted memory system: {name}")
        return True
    
    @staticmethod
    def _force_delete_recursive(path: Path) -> None:
        """Force delete directory by removing files one by one (handles locked files)."""
        import gc
        for root, dirs, files in os.walk(path, topdown=False):
            for f in files:
                fpath = Path(root) / f
                try:
                    fpath.unlink(missing_ok=True)
                except (OSError, PermissionError):
                    # Make file writable then try again
                    try:
                        import stat
                        fpath.chmod(stat.S_IWRITE)
                        fpath.unlink(missing_ok=True)
                    except OSError:
                        pass
            for d in dirs:
                dpath = Path(root) / d
                try:
                    dpath.rmdir()
                except OSError:
                    pass
            gc.collect()
        try:
            path.rmdir()
        except OSError:
            pass

    def list_systems(self) -> List[MemorySystem]:
        """
        List all memory systems.
        
        Returns:
            List of MemorySystem objects
        """
        systems = []
        for data in self._manifest.values():
            systems.append(MemorySystem.from_dict(data))
        return sorted(systems, key=lambda x: x.name)
    
    def get_info(self, name: str) -> Optional[Dict]:
        """
        Get information about a memory system.
        
        Args:
            name: Name of the memory system
            
        Returns:
            Dictionary with metadata and document count
        """
        if name not in self._manifest:
            return None
        
        info = self._manifest[name].copy()
        
        # Get document count
        try:
            store = self.get_store(name)
            info["document_count"] = store.count()
        except Exception:
            info["document_count"] = 0
        
        return info
    
    # === Store Operations ===
    
    def get_store(self, name: Optional[str] = None) -> VectorStore:
        """
        Get VectorStore for a memory system.
        
        Args:
            name: Name of memory system. Defaults to DEFAULT_COLLECTION.
            
        Returns:
            VectorStore instance for the memory system
        """
        if name is None:
            name = self.DEFAULT_COLLECTION
        
        if name not in self._manifest:
            # Auto-create if doesn't exist
            self.create(name, silent=True)
        
        # Return cached store if available
        if name in self._stores:
            return self._stores[name]
        
        path = self._manifest[name]["path"]
        store = VectorStore(persist_dir=path)
        self._stores[name] = store
        return store
    
    def _close_store(self, name: str) -> None:
        """Close and remove the VectorStore cache for a memory system.

        **Important design decision (v0.3.4)**: We deliberately do NOT call
        ``client.close()`` here.  ChromaDB's PersistentClient uses a
        long-lived SQLite connection that may hold unflushed WAL pages on
        Windows.  Calling ``close()`` while those pages are still buffered
        can leave the ``chroma.sqlite3`` file in a corrupted state
        (SQLITE_NOTADB / code: 26).  Instead we simply drop our Python
        references and let GC reclaim the handle naturally — SQLite will
        flush cleanly when the process exits or the next client opens it.
        """
        import gc
        if name in self._stores:
            try:
                store = self._stores.pop(name)
                # Soft release: drop all internal references so Python's GC
                # can eventually collect the underlying ChromaDB/SQLite objects.
                # We intentionally do NOT call client.close() — see docstring.
                for attr in ("_client", "_collection"):
                    if hasattr(store, attr):
                        try:
                            delattr(store, attr)
                        except AttributeError:
                            pass
                del store  # dereference
                gc.collect()
            except Exception as e:
                print(f"Warning: Error closing store for '{name}': {e}")
    
    def _close_all_stores(self) -> None:
        """Close all cached VectorStore instances to release file locks."""
        for name in list(self._stores.keys()):
            self._close_store(name)

    def close_all_connections(self) -> None:
        """
        Public API: Drop all cached VectorStore references to release memory.

        This is a *soft* close — it does **not** call ``client.close()`` on
        ChromaDB's PersistentClient (see ``_close_store`` docstring for why).
        Call this before delete/rename operations to free Python-level
        references, but do not rely on it for immediate filesystem access.
        """
        self._close_all_stores()
    
    def get_default_store(self) -> VectorStore:
        """Get the default VectorStore."""
        return self.get_store(self.DEFAULT_COLLECTION)
    
    # === Merge Operations ===
    
    def merge(self, source_names: List[str], new_name: str, 
             delete_sources: bool = False) -> bool:
        """
        Merge multiple memory systems into a new one.

        Args:
            source_names: List of source memory system names
            new_name: Name for the new merged memory system
            delete_sources: If True, delete source systems after merge

        Returns:
            True if merged successfully
        """
        # Validate sources
        target_exists = new_name in self._manifest
        for name in source_names:
            if name not in self._manifest:
                raise ValueError(f"Memory system '{name}' not found")
            if name == new_name and not target_exists:
                raise ValueError(f"Cannot merge: '{name}' is the target")
        
        if target_exists and new_name not in source_names:
            # Merging into existing non-source system (e.g., merge into "default") — OK
            pass
        elif target_exists and new_name in source_names:
            raise ValueError(f"Memory system '{new_name}' cannot be both source and target")
        
        # Create new memory system only if it doesn't already exist
        if not target_exists:
            self.create(new_name, f"Merged from: {', '.join(source_names)}", silent=True)
        
        new_store = self.get_store(new_name)
        
        # Actually copy documents from each source to the target
        total_docs = 0
        for name in source_names:
            source_store = self.get_store(name)
            
            try:
                count = source_store.count()
                
                if count == 0:
                    continue
                
                # Get ALL documents from source using ChromaDB's get() API
                # ChromaDB returns up to 10,000 documents by default; paginate if needed
                all_ids, all_docs, all_metadatas = [], [], []
                
                offset = 0
                batch_size = 10000  # ChromaDB's default limit
                
                while offset < count:
                    result = source_store._collection.get(
                        limit=batch_size,
                        offset=offset,
                        include=["documents", "metadatas"],
                    )
                    
                    if not result["ids"]:
                        break
                    
                    all_ids.extend(result["ids"])
                    all_docs.extend(result["documents"])
                    all_metadatas.extend(result["metadatas"])
                    
                    offset += len(result["ids"])
                    if len(result["ids"]) < batch_size:
                        break
                
                total_docs += len(all_ids)
                
                # Upsert into target collection
                if all_ids:
                    new_store._collection.upsert(
                        ids=all_ids,
                        documents=all_docs,
                        metadatas=all_metadatas,
                    )
                    
            except Exception as e:
                print(f"Warning: Could not read from '{name}': {e}")
        
        # Update new system metadata
        self._manifest[new_name]["source_systems"] = source_names
        self._manifest[new_name]["document_count"] = total_docs
        self._save_manifest()
        
        # Optionally delete sources
        if delete_sources:
            for name in source_names:
                if name != self.DEFAULT_COLLECTION:
                    self.delete(name, confirm=True)
        
        print(f"Merged {len(source_names)} systems into '{new_name}' ({total_docs} documents)")
        return True
    
    def merge_all(self, new_name: str, exclude_default: bool = True) -> bool:
        """
        Merge all memory systems into a new one.
        
        Args:
            new_name: Name for the new merged memory system
            exclude_default: If True, exclude the default system
            
        Returns:
            True if merged successfully
        """
        source_names = [
            name for name in self._manifest.keys()
            if name != self.DEFAULT_COLLECTION or not exclude_default
        ]
        
        return self.merge(source_names, new_name, delete_sources=True)
    
    # === Utility ===
    
    def _cleanup_orphaned_db_files(self) -> None:
        """Remove orphaned ``chroma.sqlite3`` files at the memories base directory.

        Each memory system lives in its **own** sub-directory (e.g.
        ``.ariadne/memories/default/chroma.sqlite3``).  A ``chroma.sqlite3``
        file directly under the base ``memories/`` dir is a leftover from an
        old version or a crashed operation and can cause "file is not a database"
        errors (SQLITE_NOTADB, code 26).
        """
        for pattern in ("chroma.sqlite3", "*.sqlite3-journal", "*.sqlite3-wal"):
            for f in self.base_dir.glob(pattern):
                try:
                    size_mb = f.stat().st_size / (1024 * 1024)
                    f.unlink(missing_ok=True)
                    print(f"Cleaned up orphaned DB: {f.name} ({size_mb:.1f} MB)")
                except OSError as e:
                    print(f"Warning: Could not remove orphaned DB {f}: {e}")
    
    def clear(self, name: str) -> bool:
        """Clear all documents from a memory system."""
        store = self.get_store(name)
        store.clear()
        print(f"Cleared memory system: {name}")
        return True
    
    def export(self, name: str, export_path: str) -> bool:
        """Export a memory system to a directory.

        If export_path is a directory, a subfolder named after
        the current memory system is created inside it.
        """
        if name not in self._manifest:
            raise ValueError(f"Memory system '{name}' not found")
        
        source_path = Path(self._manifest[name]["path"])
        dest_path = Path(export_path)

        # If dest_path already exists and is a directory (user selected folder),
        # create subfolder with the memory system's actual directory name
        if dest_path.exists() and dest_path.is_dir():
            dest_path = dest_path / source_path.name

        shutil.copytree(str(source_path), str(dest_path), dirs_exist_ok=True)
        print(f"Exported '{name}' to {dest_path}")
        return True
    
    def import_memory(self, source_path: str, name: str) -> bool:
        """Import a memory system from a directory.

        If the source is inside the memories base directory (e.g. another
        exported folder), use ``move`` instead of ``copy`` to avoid
        file-lock conflicts on Windows.
        """
        source = Path(source_path).resolve()
        if not source.exists():
            raise ValueError(f"Source path does not exist: {source_path}")

        if name in self._manifest:
            raise ValueError(f"Memory system '{name}' already exists")

        dest_path = self._get_system_dir(name)

        # Use move when source is inside the base dir (avoids copy-on-same-device locks)
        try:
            if str(source).lower().startswith(str(self.base_dir).lower()):
                # Source is within our memories tree → move it
                shutil.move(str(source), str(dest_path))
            else:
                # External source → copy
                shutil.copytree(source, dest_path)
        except Exception as e:
            raise ValueError(f"Failed to import from {source_path}: {e}") from e

        ms = MemorySystem(name=name, path=str(dest_path))
        self._manifest[name] = ms.to_dict()
        self._save_manifest()

        print(f"Imported memory system from {source_path} as '{name}'")
        return True


# Global manager instance
_manager: Optional[MemoryManager] = None

def get_manager() -> MemoryManager:
    """Get the global MemoryManager instance."""
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
