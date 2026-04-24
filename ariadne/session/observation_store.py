"""
Observation Store — high-level API for storing observations and syncing to ChromaDB.

Integrates with Ariadne's existing VectorStore for semantic search over
session observations, following Claude-Mem's ChromaSync pattern.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from ariadne.session.models import Observation, ObservationType, SessionRecord
from ariadne.session.store import SessionStore, get_store

logger = logging.getLogger(__name__)


class ObservationStore:
    """
    Manages observation persistence and ChromaDB synchronization.

    Observations are stored in SQLite (authoritative) and synced to ChromaDB
    (for semantic search).  Each observation is indexed as a separate ChromaDB
    document so that fine-grained retrieval is possible.
    """

    # ChromaDB collection name for session observations
    CHROMA_COLLECTION = "session_observations"

    def __init__(
        self,
        session_store: Optional[SessionStore] = None,
        vector_store=None,        # ariadne.memory.VectorStore instance (optional)
    ):
        self._store = session_store or get_store()
        self._vector_store = vector_store
        self._chroma_col = None   # lazy-init

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, obs: Observation) -> Observation:
        """Persist an observation and queue it for ChromaDB sync.

        The SQLite write is committed immediately so that observations are
        durable even if ChromaDB sync fails.  ChromaDB sync is best-effort.
        """
        saved = self._store.add_observation(obs)
        # Sync to ChromaDB is best-effort — we don't want a ChromaDB failure
        # to cause the SQLite commit to be rolled back.
        try:
            self._sync_to_chroma([saved])
        except Exception:
            pass  # ChromaDB sync failure is non-fatal
        return saved

    def add_many(self, observations: List[Observation]) -> List[Observation]:
        """Persist multiple observations at once.

        Each observation is committed individually so that a ChromaDB failure
        on observation N does not roll back observations 1..N-1.
        """
        saved = []
        for obs in observations:
            saved.append(self._store.add_observation(obs))
            try:
                self._sync_to_chroma([obs])
            except Exception:
                pass
        return saved

    def get(self, obs_id: str) -> Optional[Observation]:
        return self._store.get_observation(obs_id)

    def list_for_session(
        self,
        session_id: str,
        obs_type: Optional[ObservationType] = None,
        limit: int = 100,
    ) -> List[Observation]:
        return self._store.list_observations(
            session_id=session_id, obs_type=obs_type, limit=limit
        )

    def search_semantic(
        self,
        query: str,
        limit: int = 10,
        project_path: Optional[str] = None,
    ) -> List[Tuple[Observation, float]]:
        """
        Semantic search over observations using ChromaDB.

        Returns list of (Observation, score) pairs.
        Falls back to keyword search if ChromaDB is unavailable.
        """
        try:
            col = self._get_chroma_collection()
            if col is None:
                return self._keyword_search(query, limit, project_path)

            where = None
            if project_path:
                where = {"project_path": {"$eq": project_path}}

            results = col.query(
                query_texts=[query],
                n_results=min(limit, max(1, col.count())),
                where=where,
                include=["documents", "distances", "metadatas"],
            )

            obs_list: List[Tuple[Observation, float]] = []
            if results and results.get("ids") and results["ids"][0]:
                for obs_id, distance in zip(
                    results["ids"][0], results["distances"][0]
                ):
                    obs = self._store.get_observation(obs_id)
                    if obs:
                        # Convert distance to similarity score (0-1)
                        score = max(0.0, 1.0 - float(distance))
                        obs_list.append((obs, score))

            # If ChromaDB returned nothing, fall back to keyword search
            if not obs_list:
                logger.debug("ChromaDB returned no results, falling back to keyword search")
                return self._keyword_search(query, limit, project_path)

            return obs_list

        except Exception as e:
            logger.warning(f"ChromaDB semantic search failed, falling back: {e}")
            return self._keyword_search(query, limit, project_path)

    def search_timeline(
        self,
        session_id: str,
    ) -> List[Observation]:
        """Get all observations for a session, ordered by time (timeline view)."""
        return self._store.list_observations(
            session_id=session_id, limit=200
        )

    def sync_pending(self) -> int:
        """Sync all unsynced observations to ChromaDB. Returns count synced."""
        unsynced = self._store.list_observations(unsynced_only=True, limit=500)
        if not unsynced:
            return 0
        self._sync_to_chroma(unsynced)
        return len(unsynced)

    # ------------------------------------------------------------------
    # ChromaDB integration
    # ------------------------------------------------------------------

    def _get_chroma_collection(self):
        """Lazily initialize ChromaDB collection."""
        if self._chroma_col is not None:
            return self._chroma_col
        try:
            from ariadne.memory import VectorStore
            if self._vector_store is None:
                vs = VectorStore()
            else:
                vs = self._vector_store

            # Access the underlying chromadb client
            client = vs._client
            self._chroma_col = client.get_or_create_collection(
                name=self.CHROMA_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            return self._chroma_col
        except Exception as e:
            logger.debug(f"ChromaDB collection unavailable: {e}")
            return None

    def _sync_to_chroma(self, observations: List[Observation]) -> None:
        """Sync observations to ChromaDB (best-effort)."""
        if not observations:
            return
        try:
            col = self._get_chroma_collection()
            if col is None:
                return

            documents = []
            ids = []
            metadatas = []

            for obs in observations:
                documents.append(obs.to_text())
                ids.append(obs.id)
                metadatas.append({
                    "session_id": obs.session_id,
                    "obs_type": obs.obs_type.value,
                    "tool_name": obs.tool_name or "",
                    "created_at": obs.created_at,
                    "files": ",".join(obs.files[:10]),  # ChromaDB metadata is flat
                    "concepts": ",".join(obs.concepts[:10]),
                })

            # Upsert to handle duplicates gracefully
            col.upsert(
                documents=documents,
                ids=ids,
                metadatas=metadatas,
            )

            # Mark as synced in SQLite
            self._store.mark_chroma_synced([obs.id for obs in observations])
            logger.debug(f"Synced {len(observations)} observations to ChromaDB")

        except Exception as e:
            logger.warning(f"ChromaDB sync failed (non-fatal): {e}")

    def _keyword_search(
        self,
        query: str,
        limit: int,
        project_path: Optional[str],
    ) -> List[Tuple[Observation, float]]:
        """Simple keyword fallback search over SQLite observations.

        Matches individual query terms against observation text, so that
        "login validation" matches "Added login form validation" even though
        the exact phrase is not a substring.

        Filters by project_path if provided (requires joining with sessions table).
        """
        import sqlite3
        from pathlib import Path

        # Build query with optional project_path join
        base_sql = """
            SELECT o.* FROM observations o
            JOIN sessions s ON o.session_id = s.id
        """
        params: list = []
        conditions = []
        if project_path:
            conditions.append("s.project_path = ?")
            params.append(project_path)
        if conditions:
            base_sql += " WHERE " + " AND ".join(conditions)

        # Get store's db_path
        db_path = self._store.db_path
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(base_sql + " ORDER BY o.created_at DESC LIMIT ?",
                            [*params, 500]).fetchall()
        conn.close()

        # Convert rows to Observation objects
        query_terms = set(query.lower().split())
        results = []
        for row in rows:
            obs = Observation.from_dict(dict(row))
            text_lower = obs.to_text().lower()
            # Count how many query terms appear in the text
            matched = sum(1 for term in query_terms if term in text_lower)
            if matched > 0:
                score = matched / max(1, len(query_terms))
                results.append((obs, float(score)))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
