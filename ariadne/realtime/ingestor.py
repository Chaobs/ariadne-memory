"""
Observation Ingestor — Processes external AI agent memory files into Observations and vector storage.

Supports:
- Markdown memory files (MEMORY.md, YYYY-MM-DD.md)
- JSON/YAML session logs
- Automatic parsing and transformation to Observation models
- Integration with ObservationStore and MemoryManager
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from ariadne.session.models import Observation, ObservationType, SessionRecord, Platform
from ariadne.session.observation_store import ObservationStore
from ariadne.memory.manager import MemoryManager
from ariadne.ingest.base import Document, SourceType
from ariadne.config import get_config

logger = logging.getLogger(__name__)


class ObservationIngestor:
    """
    Ingestor for external AI agent memory files.
    
    Transforms memory files (e.g., WorkBuddy's MEMORY.md) into Observations
    and optionally ingests them as documents into vector storage.
    """
    
    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        observation_store: Optional[ObservationStore] = None,
        default_memory_system: str = "default",
    ):
        """
        Initialize the ingestor.
        
        Args:
            memory_manager: MemoryManager instance for vector storage.
                           If None, a default instance will be created.
            observation_store: ObservationStore instance for tracking observations.
                               If None, a default instance will be created.
            default_memory_system: Name of the memory system to use for document ingestion.
        """
        self.memory_manager = memory_manager or MemoryManager()
        self.obs_store = observation_store or ObservationStore()
        self.default_memory_system = default_memory_system
        
        # Regex patterns for parsing markdown memory files
        self.date_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2})\.md$')
        self.section_pattern = re.compile(r'^##\s+(.+)$')
        self.bullet_pattern = re.compile(r'^-\s+(.+)$')
        
    def ingest_file(
        self,
        file_path: str | Path,
        session_id: Optional[str] = None,
        project_path: Optional[str] = None,
        platform: Platform = Platform.GENERIC,
        create_observations: bool = True,
        ingest_as_documents: bool = True,
    ) -> Tuple[List[Observation], List[str]]:
        """
        Ingest a single memory file.
        
        Args:
            file_path: Path to the memory file.
            session_id: Optional session ID to associate with created observations.
                        If None, a new session will be created.
            project_path: Project path for the session. Defaults to current directory.
            platform: Platform enum for the session.
            create_observations: Whether to create Observation records.
            ingest_as_documents: Whether to ingest content as documents into vector storage.
        
        Returns:
            Tuple of (list of created Observation objects, list of document IDs).
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning(f"File does not exist: {file_path}")
            return [], []
            
        # Determine file type and parse accordingly
        if file_path.suffix.lower() == '.md':
            return self._ingest_markdown_file(
                file_path, session_id, project_path, platform,
                create_observations, ingest_as_documents
            )
        elif file_path.suffix.lower() in ['.json', '.yaml', '.yml']:
            return self._ingest_structured_file(
                file_path, session_id, project_path, platform,
                create_observations, ingest_as_documents
            )
        else:
            # Try as plain text
            return self._ingest_text_file(
                file_path, session_id, project_path, platform,
                create_observations, ingest_as_documents
            )
    
    @staticmethod
    def _read_text_robust(path: Path) -> str:
        """Read text with automatic encoding detection.
        
        Tries in order: utf-8-sig (BOM), utf-8, gb18030 (CJK),
        latin-1 (universal fallback).
        """
        encodings = ["utf-8-sig", "utf-8", "gb18030", "latin-1"]
        for enc in encodings:
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
        # If all encodings fail, try latin-1 with replacement
        return path.read_text(encoding="latin-1", errors="replace")

    def _ingest_markdown_file(
        self,
        file_path: Path,
        session_id: Optional[str],
        project_path: Optional[str],
        platform: Platform,
        create_observations: bool,
        ingest_as_documents: bool,
    ) -> Tuple[List[Observation], List[str]]:
        """
        Ingest a markdown memory file (MEMORY.md or dated daily log).
        """
        observations = []
        doc_ids = []
        
        # Read file content
        try:
            content = self._read_text_robust(file_path)
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return [], []
            
        # Check if this is a dated daily log
        date_match = self.date_pattern.match(file_path.name)
        file_date = date_match.group(1) if date_match else None
        
        # Parse into sections and bullets
        lines = content.split('\n')
        current_section = None
        current_items = []
        
        for line in lines:
            line = line.rstrip()
            
            # Check for section header
            section_match = self.section_pattern.match(line)
            if section_match:
                # Process previous section if any
                if current_section and current_items:
                    obs, docs = self._process_section(
                        file_path, current_section, current_items,
                        session_id, project_path, platform, file_date,
                        create_observations, ingest_as_documents
                    )
                    observations.extend(obs)
                    doc_ids.extend(docs)
                
                # Start new section
                current_section = section_match.group(1).strip()
                current_items = []
                continue
                
            # Check for bullet item
            bullet_match = self.bullet_pattern.match(line)
            if bullet_match and current_section:
                item = bullet_match.group(1).strip()
                if item:
                    current_items.append(item)
        
        # Process the last section
        if current_section and current_items:
            obs, docs = self._process_section(
                file_path, current_section, current_items,
                session_id, project_path, platform, file_date,
                create_observations, ingest_as_documents
            )
            observations.extend(obs)
            doc_ids.extend(docs)
        
        # If no sections were found, treat entire file as single observation
        if not observations and content.strip():
            obs, docs = self._process_raw_content(
                file_path, content,
                session_id, project_path, platform, file_date,
                create_observations, ingest_as_documents
            )
            observations.extend(obs)
            doc_ids.extend(docs)
        
        logger.info(f"Ingested {len(observations)} observations from {file_path}")
        return observations, doc_ids
    
    def _process_section(
        self,
        file_path: Path,
        section_title: str,
        items: List[str],
        session_id: Optional[str],
        project_path: Optional[str],
        platform: Platform,
        file_date: Optional[str],
        create_observations: bool,
        ingest_as_documents: bool,
    ) -> Tuple[List[Observation], List[str]]:
        """
        Process a section of a markdown file into observations and documents.
        """
        observations = []
        doc_ids = []
        
        # Create or get session
        session = self._get_or_create_session(
            session_id, project_path, platform, file_path, section_title
        )
        
        # Determine observation type based on section title
        obs_type = self._infer_observation_type(section_title)
        
        # Create one observation per item (or combine all items into one)
        for i, item in enumerate(items):
            summary = f"{section_title}: {item[:100]}{'...' if len(item) > 100 else ''}"
            detail = item
            
            # Create observation if requested
            if create_observations:
                obs = Observation.new(
                    session_id=session.id,
                    obs_type=obs_type,
                    summary=summary,
                    detail=detail,
                    files=[str(file_path)],
                    concepts=[section_title],
                )
                saved_obs = self.obs_store.add(obs)
                observations.append(saved_obs)
            
            # Ingest as document if requested
            if ingest_as_documents:
                doc_id = self._ingest_as_document(
                    content=detail,
                    source_path=str(file_path),
                    metadata={
                        "section": section_title,
                        "item_index": i,
                        "file_date": file_date,
                        "observation_type": obs_type.value if create_observations else None,
                    }
                )
                if doc_id:
                    doc_ids.append(doc_id)
        
        return observations, doc_ids
    
    def _process_raw_content(
        self,
        file_path: Path,
        content: str,
        session_id: Optional[str],
        project_path: Optional[str],
        platform: Platform,
        file_date: Optional[str],
        create_observations: bool,
        ingest_as_documents: bool,
    ) -> Tuple[List[Observation], List[str]]:
        """
        Process raw file content when no structured sections are found.
        """
        observations = []
        doc_ids = []
        
        # Create or get session
        session = self._get_or_create_session(
            session_id, project_path, platform, file_path, "General"
        )
        
        # Create a single observation for the entire content
        if create_observations:
            summary = f"{file_path.name}: {content[:200]}{'...' if len(content) > 200 else ''}"
            obs = Observation.new(
                session_id=session.id,
                obs_type=ObservationType.GENERAL,
                summary=summary,
                detail=content,
                files=[str(file_path)],
            )
            saved_obs = self.obs_store.add(obs)
            observations.append(saved_obs)
        
        # Ingest as document
        if ingest_as_documents:
            doc_id = self._ingest_as_document(
                content=content,
                source_path=str(file_path),
                metadata={
                    "file_date": file_date,
                    "observation_type": ObservationType.GENERAL.value if create_observations else None,
                }
            )
            if doc_id:
                doc_ids.append(doc_id)
        
        return observations, doc_ids
    
    def _get_or_create_session(
        self,
        session_id: Optional[str],
        project_path: Optional[str],
        platform: Platform,
        file_path: Path,
        context: str,
    ) -> SessionRecord:
        """
        Get existing session or create a new one.
        """
        if session_id:
            # Try to get existing session
            # Note: SessionStore retrieval not yet implemented in this method
            # For now, create a new session with the given ID
            pass
        
        # Create new session
        if project_path is None:
            project_path = str(file_path.parent)
            
        session = SessionRecord.new(
            project_path=project_path,
            platform=platform,
        )
        # TODO: Store session in SessionStore
        # For now, we'll just return it
        return session
    
    def _infer_observation_type(self, section_title: str) -> ObservationType:
        """
        Infer observation type from section title.
        """
        title_lower = section_title.lower()
        
        if any(word in title_lower for word in ['bug', 'error', 'fix', 'issue']):
            return ObservationType.BUGFIX
        elif any(word in title_lower for word in ['feature', 'enhancement', 'improvement']):
            return ObservationType.FEATURE
        elif any(word in title_lower for word in ['refactor', 'cleanup', 'optimization']):
            return ObservationType.REFACTOR
        elif any(word in title_lower for word in ['change', 'update', 'modification']):
            return ObservationType.CHANGE
        elif any(word in title_lower for word in ['discovery', 'learn', 'find', 'insight']):
            return ObservationType.DISCOVERY
        elif any(word in title_lower for word in ['decision', 'choice', 'plan', 'strategy']):
            return ObservationType.DECISION
        elif any(word in title_lower for word in ['security', 'vulnerability', 'risk']):
            return ObservationType.SECURITY_ALERT
        else:
            return ObservationType.GENERAL
    
    def _ingest_as_document(
        self,
        content: str,
        source_path: str,
        metadata: Dict[str, Any],
    ) -> Optional[str]:
        """
        Ingest content as a document into the default memory system.
        
        Returns:
            Document ID if successful, None otherwise.
        """
        try:
            # Create Document object
            doc = Document(
                content=content,
                source_type=SourceType.MARKDOWN,
                source_path=source_path,
                metadata=metadata,
            )
            
            # Get vector store for default memory system
            store = self.memory_manager.get_store(self.default_memory_system)
            if store:
                store.add([doc])
                logger.debug(f"Ingested document {doc.doc_id} into memory system '{self.default_memory_system}'")
                return doc.doc_id
            else:
                logger.error(f"Failed to get store for memory system '{self.default_memory_system}'")
                return None
                
        except Exception as e:
            logger.error(f"Failed to ingest document: {e}")
            return None
    
    def _ingest_structured_file(
        self,
        file_path: Path,
        session_id: Optional[str],
        project_path: Optional[str],
        platform: Platform,
        create_observations: bool,
        ingest_as_documents: bool,
    ) -> Tuple[List[Observation], List[str]]:
        """
        Ingest structured JSON/YAML file.
        """
        # TODO: Implement JSON/YAML parsing
        logger.warning(f"Structured file ingestion not yet implemented: {file_path}")
        return [], []
    
    def _ingest_text_file(
        self,
        file_path: Path,
        session_id: Optional[str],
        project_path: Optional[str],
        platform: Platform,
        create_observations: bool,
        ingest_as_documents: bool,
    ) -> Tuple[List[Observation], List[str]]:
        """
        Ingest plain text file.
        """
        try:
            content = self._read_text_robust(file_path)
        except Exception as e:
            logger.error(f"Failed to read text file {file_path}: {e}")
            return [], []
            
        return self._process_raw_content(
            file_path, content,
            session_id, project_path, platform, None,
            create_observations, ingest_as_documents
        )
    
    def ingest_directory(
        self,
        directory: str | Path,
        pattern: str = "*.md",
        recursive: bool = True,
        **kwargs,
    ) -> Tuple[List[Observation], List[str]]:
        """
        Ingest all matching files in a directory.
        """
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            logger.warning(f"Directory does not exist: {dir_path}")
            return [], []
            
        all_observations = []
        all_doc_ids = []
        
        # Find files
        if recursive:
            files = list(dir_path.rglob(pattern))
        else:
            files = list(dir_path.glob(pattern))
            
        for file_path in files:
            if file_path.is_file():
                obs, doc_ids = self.ingest_file(file_path, **kwargs)
                all_observations.extend(obs)
                all_doc_ids.extend(doc_ids)
        
        logger.info(f"Ingested {len(all_observations)} observations from {len(files)} files in {directory}")
        return all_observations, all_doc_ids