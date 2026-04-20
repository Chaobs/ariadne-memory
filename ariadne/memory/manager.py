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

from ariadne.memory.store import VectorStore, _is_db_corruption_error


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
        
        # Startup health-check: verify default store is usable.
        # If HNSW index is corrupt on disk, recover NOW before GUI tries to
        # call _update_stats() → get_store("default") → count().
        self._health_check_default()
    
    def _save_manifest(self) -> None:
        """Save manifest to disk."""
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self._manifest, f, indent=2, ensure_ascii=False)
    
    def _get_system_dir(self, name: str) -> Path:
        """Get directory path for a memory system."""
        # Sanitize name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "_- " else "_" for c in name)
        return self.base_dir / safe_name
    
    @staticmethod
    def _safe_collection_name(name: str) -> str:
        """Convert a user-facing memory system name to a ChromaDB-safe collection name.

        ChromaDB requires collection names to match:
        ``[a-zA-Z0-9._-]{3,512}``
        (3–512 chars, starting/ending with alphanumeric, only ``.``, ``_``, ``-``
        as special characters).

        This method encodes non-ASCII characters (e.g. Chinese) via URL-encoding,
        producing a deterministic, reversible ASCII string that satisfies ChromaDB's
        validation rules.

        Examples:
            "default"          → "default"
            "电商-真"          → "e4b889e59586-true"  (hex-encoded UTF-8 bytes)
        """
        import re

        # Fast path: already valid ASCII name
        if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$', name) and 3 <= len(name) <= 512:
            return name

        # Encode non-ASCII / invalid chars as hex
        safe_chars = []
        for c in name:
            if c.isalnum():
                safe_chars.append(c)
            elif c in '._-':
                safe_chars.append(c)
            else:
                # Hex-encode the UTF-8 byte(s) of this character
                for b in c.encode('utf-8'):
                    safe_chars.append(f'{b:02x}')

        result = ''.join(safe_chars)

        # Ensure minimum length of 3 and starts/ends with alphanumeric
        if len(result) < 3:
            result = result + ('_' * (3 - len(result)))
        if not result[0].isalnum():
            result = '_' + result
        if not result[-1].isalnum():
            result = result + '_'
        
        # Truncate to max 512
        return result[:512]
    
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

        This handles two things:
        1. Migrate ChromaDB collection data (old collection name → new) within
           the same directory
        2. Update the manifest (name and optionally path)

        The directory on disk is NOT renamed because ChromaDB's PersistentClient
        holds file locks that prevent ``os.rename`` / ``shutil.move`` on Windows.
        The collection data inside the database is correctly associated with the
        new name, which is what matters for search and retrieval.

        If the user wants to rename the directory as well, they can do so
        manually after shutting down the application.

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

        old_dir = Path(self._manifest[old_name]["path"])

        # Step 1: Migrate ChromaDB collection data (old collection name → new)
        old_collection = self._safe_collection_name(old_name)
        new_collection = self._safe_collection_name(new_name)

        if old_collection != new_collection:
            # Ensure store is open and accessible, then migrate
            store = self.get_store(old_name)
            self._migrate_collection(str(old_dir), old_collection, new_collection)
            # Close the old store reference so future calls get a fresh one
            self._close_store(old_name)

        # Step 2: Update manifest — keep the same directory path
        # (ChromaDB holds file locks, so renaming the directory on disk
        # would fail on Windows. The directory name is just cosmetic.)
        old_entry = self._manifest[old_name].copy()
        del self._manifest[old_name]
        self._manifest[new_name] = {
            **old_entry,
            "name": new_name,
            "path": str(old_dir),  # Keep the same directory
            "updated_at": datetime.now().isoformat(),
        }
        self._save_manifest()

        print(f"Renamed '{old_name}' to '{new_name}'")
        return True

    def _migrate_collection(self, persist_dir: str, old_col: str, new_col: str) -> None:
        """Migrate ChromaDB collection data from old name to new name.

        ChromaDB does not support renaming collections directly, so we:
        1. Open the existing collection (old name)
        2. Read all documents
        3. Create a new collection (new name) and upsert the data
        4. Delete the old collection

        Args:
            persist_dir: Directory where ChromaDB data is stored
            old_col: Old collection name (ChromaDB-safe)
            new_col: New collection name (ChromaDB-safe)
        """
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        import gc

        client = None
        try:
            # Clear any cached client to avoid "already exists with different settings"
            chromadb.api.shared_system_client.SharedSystemClient.clear_system_cache()

            # Use the SAME settings as VectorStore to avoid settings mismatch
            settings = ChromaSettings(anonymized_telemetry=False)
            client = chromadb.PersistentClient(path=persist_dir, settings=settings)

            # Get old collection
            try:
                old_collection = client.get_collection(old_col)
            except Exception:
                # Old collection doesn't exist — nothing to migrate
                return

            count = old_collection.count()
            if count == 0:
                # Empty collection — just delete it and create new one
                try:
                    client.delete_collection(old_col)
                except Exception:
                    pass
                client.get_or_create_collection(new_col)
                return

            # Read all data from old collection in batches
            all_ids, all_docs, all_metadatas, all_embeddings = [], [], [], []
            batch_size = 5000
            offset = 0
            has_embeddings = False

            while offset < count:
                result = old_collection.get(
                    limit=batch_size,
                    offset=offset,
                    include=["documents", "metadatas", "embeddings"],
                )
                if not result["ids"]:
                    break
                all_ids.extend(result["ids"])
                all_docs.extend(result["documents"])
                all_metadatas.extend(result["metadatas"])
                # ChromaDB returns embeddings as numpy arrays which cannot be
                # tested with plain truthiness ("ambiguous truth value" error).
                # Use len() instead.
                emb = result.get("embeddings")
                if emb is not None and len(emb) > 0:
                    all_embeddings.extend(emb)
                    has_embeddings = True
                offset += len(result["ids"])
                if len(result["ids"]) < batch_size:
                    break

            # Create new collection and upsert data
            new_collection = client.get_or_create_collection(new_col)
            if all_ids:
                upsert_kwargs = {
                    "ids": all_ids,
                    "documents": all_docs,
                    "metadatas": all_metadatas,
                }
                if has_embeddings and len(all_embeddings) > 0:
                    upsert_kwargs["embeddings"] = all_embeddings
                new_collection.upsert(**upsert_kwargs)

            # Delete old collection
            try:
                client.delete_collection(old_col)
            except Exception as e:
                print(f"Warning: Could not delete old collection '{old_col}': {e}")

            print(f"Migrated collection: {old_col} -> {new_col} ({len(all_ids)} docs)")

        except Exception as e:
            print(f"Warning: Collection migration failed ({old_col} -> {new_col}): {e}")
            # Non-fatal — the directory move already succeeded
        finally:
            # Clean up client to release file locks
            if client is not None:
                del client
            gc.collect()
    
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
    
    def _health_check_default(self) -> None:
        """Verify the default memory system is healthy at startup.

        ChromaDB's lazy HNSW init means corruption is only detected on first
        real operation.  By probing at startup we catch (and auto-fix) any
        corruption **before** the GUI calls ``_update_stats()`` or ingest.
        
        Errors here are handled silently — the user sees nothing wrong.
        """
        try:
            self._create_healthy_store(self.DEFAULT_COLLECTION)
            print(f"[Health] Default system '{self.DEFAULT_COLLECTION}' OK")
        except Exception as e:
            # _create_healthy_store already attempted recovery.
            # If we're still failing, log but don't crash startup.
            print(f"[Health] WARNING: Could not verify default system: {e}")
    
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
        
        # Get document count via healthy store (auto-recovers if needed)
        try:
            store = self._create_healthy_store(name)
            info["document_count"] = store.count()
        except Exception:
            info["document_count"] = 0
        
        return info
    
    # === Store Operations ===
    
    def _create_healthy_store(self, name: str) -> VectorStore:
        """Create (or retrieve cached) a **verified-healthy** VectorStore.

        This is the single entry-point that guarantees the returned store can
        actually perform ``count()`` / ``query()`` / ``add()`` without raising
        lazy-load HNSW errors.

        Recovery strategy:
        1. Create or return cached ``VectorStore`` (constructor may succeed even
           with corrupt on-disk data because ChromaDB uses lazy init).
        2. Call ``probe()`` to force HNSW index activation.
        3. If probe reveals corruption → wipe persisted files, evict cache,
           and retry once.

        Args:
            name: Memory system name.

        Returns:
            A VectorStore that has been verified healthy via probe().
        
        Raises:
            Exception: If the store cannot be brought to a healthy state.
        """
        if name in self._stores:
            store = self._stores[name]
            try:
                store.probe()
                return store
            except Exception:
                # Cached store went bad between calls; evict and recreate below
                self._close_store(name)

        path = self._manifest[name]["path"]
        safe_name = self._safe_collection_name(name)

        last_exc = None
        for attempt in range(2):
            try:
                store = VectorStore(persist_dir=path, collection_name=safe_name)
                store.probe()  # ⚠️ Force lazy HNSW load NOW, not later
                self._stores[name] = store
                return store
            except Exception as exc:
                last_exc = exc
                if attempt == 0 and _is_db_corruption_error(exc):
                    print(f"[Recovery] Probing '{name}' detected corruption: {exc}")
                    # Evict stale handle before wiping files
                    if name in self._stores:
                        self._close_store(name)
                    # Wipe ALL persisted content (sqlite3 + HNSW binaries + etc.)
                    if VectorStore._wipe_chroma_files(path):
                        print(f"[Recovery] Wiped corrupted ChromaDB data at {path}")
                        continue
                raise

        raise last_exc  # Should not reach here, but just in case
    
    def get_store(self, name: Optional[str] = None) -> VectorStore:
        """
        Get a **verified-healthy** VectorStore for a memory system.

        This method guarantees the returned store is fully operational:
        - If the persisted ChromaDB data is corrupt (including lazy-load HNSW
          errors), it is **automatically wiped and recreated**.
        - The caller never sees an HNSW / compactor / segment reader error.
        
        Args:
            name: Name of memory system. Defaults to DEFAULT_COLLECTION.
            
        Returns:
            VectorStore instance for the memory system (guaranteed healthy)
        
        Raises:
            Exception: Only if recovery fails after 2 attempts (extremely rare).
        """
        if name is None:
            name = self.DEFAULT_COLLECTION
        
        if name not in self._manifest:
            # Auto-create if doesn't exist
            self.create(name, silent=True)
        
        return self._create_healthy_store(name)
    
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
        
        **Important for Windows**: After calling this method, wait at least
        1 second (or call ``time.sleep(1)``) before performing filesystem
        operations like ``shutil.rmtree`` or ``shutil.move`` on the same
        directories — the OS may still hold file handles briefly.
        
        Call this before delete/rename operations to free Python-level
        references, but do not rely on it for immediate filesystem access.
        """
        self._close_all_stores()
    
    @staticmethod
    def graceful_shutdown(manager: "MemoryManager" = None) -> None:
        """Graceful shutdown: close all stores with proper cleanup.

        Call this when the application exits (GUI close button / CLI finish).
        This ensures all ChromaDB handles are released cleanly.

        Args:
            manager: Optional MemoryManager instance. If None, uses global.
        """
        if manager is None:
            # Import here to avoid circular dependency
            try:
                from ariadne.memory.manager import get_manager
                manager = get_manager()
            except Exception:
                return
        
        if manager is not None:
            manager._close_all_stores()
            print("[Shutdown] All connections closed gracefully")
    
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

        After copying/moving the directory, the ChromaDB collection is
        migrated to match the new system name if needed.
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

        # Migrate ChromaDB collection name if needed
        # The imported database may have collections with different names;
        # we need to ensure the collection matches our new system name.
        new_collection = self._safe_collection_name(name)
        self._migrate_imported_collection(str(dest_path), new_collection)

        ms = MemorySystem(name=name, path=str(dest_path))
        self._manifest[name] = ms.to_dict()
        self._save_manifest()

        print(f"Imported memory system from {source_path} as '{name}'")
        return True

    def _migrate_imported_collection(self, persist_dir: str, target_col: str) -> None:
        """Ensure an imported database has the correct collection name.

        When a memory system is exported and re-imported with a different
        name, the ChromaDB collections inside still use the old name.
        This method finds the existing collection and migrates it to
        the target name.

        Args:
            persist_dir: Directory where ChromaDB data is stored
            target_col: Desired collection name (ChromaDB-safe)
        """
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        import gc

        client = None
        try:
            # Clear any cached client to avoid "already exists with different settings"
            chromadb.api.shared_system_client.SharedSystemClient.clear_system_cache()

            # Use the SAME settings as VectorStore
            settings = ChromaSettings(anonymized_telemetry=False)
            client = chromadb.PersistentClient(path=persist_dir, settings=settings)

            # Check if target collection already exists
            try:
                existing = client.get_collection(target_col)
                if existing.count() >= 0:
                    # Target collection exists — nothing to do
                    return
            except Exception:
                pass

            # Find all collections and migrate the first non-target one
            collections = client.list_collections()
            for col_info in collections:
                col_name = col_info.name if hasattr(col_info, 'name') else str(col_info)
                if col_name != target_col:
                    # Found a collection with the old name — migrate it
                    # Note: we can reuse the same client since it's already open
                    self._migrate_collection_with_client(client, col_name, target_col)
                    return

            # No collections found — create empty target collection
            client.get_or_create_collection(target_col)

        except Exception as e:
            print(f"Warning: Import collection migration failed for {persist_dir}: {e}")
        finally:
            if client is not None:
                del client
            gc.collect()

    def _migrate_collection_with_client(self, client, old_col: str, new_col: str) -> None:
        """Migrate collection using an existing ChromaDB client.

        Same logic as _migrate_collection but reuses an existing client
        instead of creating a new one (avoids the "already exists" error).

        Args:
            client: Existing ChromaDB PersistentClient
            old_col: Old collection name (ChromaDB-safe)
            new_col: New collection name (ChromaDB-safe)
        """
        try:
            old_collection = client.get_collection(old_col)
        except Exception:
            return

        count = old_collection.count()
        if count == 0:
            try:
                client.delete_collection(old_col)
            except Exception:
                pass
            client.get_or_create_collection(new_col)
            return

        all_ids, all_docs, all_metadatas, all_embeddings = [], [], [], []
        batch_size = 5000
        offset = 0
        has_embeddings = False

        while offset < count:
            result = old_collection.get(
                limit=batch_size,
                offset=offset,
                include=["documents", "metadatas", "embeddings"],
            )
            if not result["ids"]:
                break
            all_ids.extend(result["ids"])
            all_docs.extend(result["documents"])
            all_metadatas.extend(result["metadatas"])
            emb = result.get("embeddings")
            if emb is not None and len(emb) > 0:
                all_embeddings.extend(emb)
                has_embeddings = True
            offset += len(result["ids"])
            if len(result["ids"]) < batch_size:
                break

        new_collection = client.get_or_create_collection(new_col)
        if all_ids:
            upsert_kwargs = {
                "ids": all_ids,
                "documents": all_docs,
                "metadatas": all_metadatas,
            }
            if has_embeddings and len(all_embeddings) > 0:
                upsert_kwargs["embeddings"] = all_embeddings
            new_collection.upsert(**upsert_kwargs)

        try:
            client.delete_collection(old_col)
        except Exception as e:
            print(f"Warning: Could not delete old collection '{old_col}': {e}")

        print(f"Migrated collection: {old_col} -> {new_col} ({len(all_ids)} docs)")


# Global manager instance
_manager: Optional[MemoryManager] = None

def get_manager() -> MemoryManager:
    """Get the global MemoryManager instance."""
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
