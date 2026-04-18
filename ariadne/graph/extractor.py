"""
Entity and Relation extraction for Knowledge Graph.

Uses LLM to extract structured entities and relations from text.
"""

from ariadne.graph.models import Entity, Relation, EntityType, RelationType, GraphDocument
from ariadne.llm.base import BaseLLM, LLMResponse
from ariadne.ingest.base import Document
from typing import List, Optional, Tuple, Callable
import logging
import json
import re

logger = logging.getLogger(__name__)


class EntityExtractor:
    """
    Extract entities from text using LLM.
    
    Uses few-shot prompting to extract named entities with their types
    and properties from unstructured text.
    
    Example:
        extractor = EntityExtractor(llm)
        entities = extractor.extract_entities(
            "Albert Einstein was born in Ulm in 1879."
        )
    """
    
    EXTRACTION_PROMPT = """You are an expert entity extraction system. Extract all named entities from the following text and classify them.

Text:
{text}

For each entity, identify:
1. Name (canonical form)
2. Type (person, organization, location, event, concept, work, topic)
3. Brief description (1-2 sentences)
4. Any aliases or alternative names

Return the entities in this JSON format:
{{
    "entities": [
        {{
            "name": "Entity Name",
            "type": "person|organization|location|event|concept|work|topic",
            "description": "Brief description",
            "aliases": ["alias1", "alias2"]
        }}
    ]
}}

Only extract entities that are clearly mentioned. Return empty array if none found."""

    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        min_confidence: float = 0.7,
        batch_size: int = 1,
    ):
        """
        Initialize the extractor.
        
        Args:
            llm: Optional LLM instance for extraction. If None, uses rule-based extraction.
            min_confidence: Minimum confidence threshold for extracted entities.
            batch_size: Number of texts to process in parallel (requires LLM).
        """
        self.llm = llm
        self.min_confidence = min_confidence
        self.batch_size = batch_size
    
    def extract_entities(self, text: str, source: str = "") -> List[Entity]:
        """
        Extract entities from text.
        
        Args:
            text: Text to extract entities from.
            source: Optional source document path.
            
        Returns:
            List of extracted Entity objects.
        """
        if self.llm:
            return self._extract_with_llm(text, source)
        else:
            return self._extract_rule_based(text, source)
    
    def _extract_with_llm(self, text: str, source: str = "") -> List[Entity]:
        """Use LLM for entity extraction."""
        # Truncate text if too long
        if len(text) > 4000:
            text = text[:4000] + "..."
        
        prompt = self.EXTRACTION_PROMPT.format(text=text)
        
        try:
            response = self.llm.chat(
                prompt=prompt,
                system="You are a helpful entity extraction assistant."
            )
            
            entities = self._parse_entities(response.content)
            
            # Add source to each entity
            for entity in entities:
                if source:
                    entity.add_source(source)
            
            return entities
            
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}, falling back to rule-based")
            return self._extract_rule_based(text, source)
    
    def _extract_rule_based(self, text: str, source: str = "") -> List[Entity]:
        """Fallback rule-based entity extraction."""
        entities = []
        
        # Simple pattern-based extraction
        # This is a basic implementation; production code might use spaCy or similar
        
        # Capitalized words that might be proper nouns
        capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        
        for name in set(capitalized):
            if len(name) > 2 and not self._is_common_word(name):
                entity = Entity(
                    name=name,
                    entity_type=EntityType.UNKNOWN,
                    confidence=0.5,
                )
                if source:
                    entity.add_source(source)
                entities.append(entity)
        
        return entities
    
    def _is_common_word(self, word: str) -> bool:
        """Check if a capitalized word is a common word (not a proper noun)."""
        common_words = {
            "The", "This", "That", "These", "Those",
            "Chapter", "Section", "Figure", "Table",
            "Abstract", "Introduction", "Conclusion", "References",
            "Example", "Note", "See", "Also", "But", "And", "Or",
        }
        return word in common_words
    
    def _parse_entities(self, content: str) -> List[Entity]:
        """Parse entities from LLM response."""
        entities = []
        
        try:
            # Try to extract JSON from response
            json_str = self._extract_json(content)
            data = json.loads(json_str)
            
            for item in data.get("entities", []):
                try:
                    entity_type = EntityType(item.get("type", "unknown"))
                    entity = Entity(
                        name=item["name"],
                        entity_type=entity_type,
                        description=item.get("description", ""),
                        aliases=item.get("aliases", []),
                        confidence=0.8,  # LLM extraction confidence
                    )
                    entities.append(entity)
                except KeyError:
                    continue
                    
        except json.JSONDecodeError:
            logger.warning("Failed to parse entity JSON")
        
        return entities
    
    def _extract_json(self, content: str) -> str:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        content = content.strip()
        
        # Remove markdown code blocks
        if "```json" in content:
            parts = content.split("```json")
            if len(parts) > 1:
                content = parts[1].split("```")[0]
        elif "```" in content:
            parts = content.split("```")
            if len(parts) > 1:
                content = parts[1]
        
        return content.strip()


class RelationExtractor:
    """
    Extract relations between entities using LLM.
    
    Given a list of entities and the source text, identifies
    meaningful relationships between them.
    
    Example:
        extractor = RelationExtractor(llm)
        relations = extractor.extract_relations(
            entities=entities,
            text="Einstein developed the theory of relativity.",
            source="einstein.txt"
        )
    """
    
    RELATION_PROMPT = """You are an expert at identifying relationships between entities.

Given the following entities and text, identify all meaningful relations between pairs of entities.

Entities:
{entities}

Text:
{text}

For each relation, identify:
1. Source entity name
2. Target entity name
3. Relation type (related_to, is_a, part_of, created_by, located_in, discussed_in, etc.)
4. Brief description of the relationship

Return in JSON format:
{{
    "relations": [
        {{
            "source": "Entity A",
            "target": "Entity B",
            "type": "relation_type",
            "description": "How they are related"
        }}
    ]
}}

Only include relations that are clearly supported by the text."""

    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        min_confidence: float = 0.7,
    ):
        """
        Initialize the extractor.
        
        Args:
            llm: Optional LLM instance. Falls back to co-occurrence if None.
            min_confidence: Minimum confidence for extracted relations.
        """
        self.llm = llm
        self.min_confidence = min_confidence
    
    def extract_relations(
        self,
        entities: List[Entity],
        text: str,
        source: str = "",
    ) -> List[Relation]:
        """
        Extract relations between entities.
        
        Args:
            entities: List of entities to find relations between.
            text: Source text containing the entities.
            source: Optional source document path.
            
        Returns:
            List of extracted Relation objects.
        """
        if not entities:
            return []
        
        if self.llm:
            return self._extract_with_llm(entities, text, source)
        else:
            return self._extract_co_occurrence(entities, text, source)
    
    def _extract_with_llm(
        self,
        entities: List[Entity],
        text: str,
        source: str = "",
    ) -> List[Relation]:
        """Use LLM for relation extraction."""
        # Truncate text if too long
        if len(text) > 3000:
            text = text[:3000] + "..."
        
        # Format entities
        entity_text = "\n".join(
            f"- {e.name} ({e.entity_type.value}): {e.description}"
            for e in entities[:20]  # Limit to 20 entities
        )
        
        prompt = self.RELATION_PROMPT.format(
            entities=entity_text,
            text=text,
        )
        
        try:
            response = self.llm.chat(prompt=prompt)
            relations = self._parse_relations(response.content, entities)
            
            # Add source to each relation
            for relation in relations:
                if source:
                    relation.add_source(source)
            
            return relations
            
        except Exception as e:
            logger.warning(f"LLM relation extraction failed: {e}")
            return self._extract_co_occurrence(entities, text, source)
    
    def _extract_co_occurrence(
        self,
        entities: List[Entity],
        text: str,
        source: str = "",
    ) -> List[Relation]:
        """
        Fallback: extract relations based on entity co-occurrence.
        
        If two entities appear close together in the text,
        they are considered potentially related.
        """
        relations = []
        
        # Sort entities by first appearance in text
        entity_positions = []
        for entity in entities:
            pos = text.lower().find(entity.name.lower())
            if pos >= 0:
                entity_positions.append((pos, entity))
        
        entity_positions.sort(key=lambda x: x[0])
        
        # Create relations between nearby entities
        for i, (pos1, ent1) in enumerate(entity_positions):
            for pos2, ent2 in entity_positions[i+1:]:
                # If entities are within 200 characters, consider them related
                if pos2 - pos1 < 200:
                    relation = Relation(
                        source_id=ent1.entity_id,
                        target_id=ent2.entity_id,
                        relation_type=RelationType.RELATED_TO,
                        description=f"Co-occurred in text near '{text[pos1:pos2+50]}...'",
                        confidence=0.5,
                    )
                    if source:
                        relation.add_source(source)
                    relations.append(relation)
                else:
                    break  # Entities are too far apart
        
        return relations
    
    def _parse_relations(
        self,
        content: str,
        entities: List[Entity],
    ) -> List[Relation]:
        """Parse relations from LLM response."""
        relations = []
        entity_map = {e.name.lower(): e for e in entities}
        
        try:
            json_str = self._extract_json(content)
            data = json.loads(json_str)
            
            for item in data.get("relations", []):
                try:
                    source_name = item["source"].lower()
                    target_name = item["target"].lower()
                    
                    # Find matching entities
                    source_entity = entity_map.get(source_name)
                    target_entity = entity_map.get(target_name)
                    
                    # Try partial match if exact match fails
                    if not source_entity:
                        for name, entity in entity_map.items():
                            if source_name in name or name in source_name:
                                source_entity = entity
                                break
                    if not target_entity:
                        for name, entity in entity_map.items():
                            if target_name in name or name in target_name:
                                target_entity = entity
                                break
                    
                    if source_entity and target_entity:
                        # Map relation type
                        rel_type = self._map_relation_type(item.get("type", "related_to"))
                        
                        relation = Relation(
                            source_id=source_entity.entity_id,
                            target_id=target_entity.entity_id,
                            relation_type=rel_type,
                            description=item.get("description", ""),
                            confidence=0.8,
                        )
                        relations.append(relation)
                        
                except KeyError:
                    continue
                    
        except json.JSONDecodeError:
            logger.warning("Failed to parse relation JSON")
        
        return relations
    
    def _map_relation_type(self, type_str: str) -> RelationType:
        """Map a string relation type to a RelationType enum."""
        type_map = {
            "related_to": RelationType.RELATED_TO,
            "similar_to": RelationType.SIMILAR_TO,
            "part_of": RelationType.PART_OF,
            "instance_of": RelationType.INSTANCE_OF,
            "is_a": RelationType.IS_A,
            "has_a": RelationType.HAS_A,
            "belongs_to": RelationType.BELONGS_TO,
            "created_by": RelationType.CREATED_BY,
            "located_in": RelationType.LOCATED_IN,
            "participated_in": RelationType.PARTICIPATED_IN,
            "defines": RelationType.DEFINES,
            "cites": RelationType.CITES,
            "references": RelationType.REFERENCES,
            "discusses": RelationType.DISCUSSES,
        }
        return type_map.get(type_str.lower(), RelationType.RELATED_TO)
    
    def _extract_json(self, content: str) -> str:
        """Extract JSON from LLM response."""
        content = content.strip()
        if "```json" in content:
            parts = content.split("```json")
            if len(parts) > 1:
                content = parts[1].split("```")[0]
        elif "```" in content:
            parts = content.split("```")
            if len(parts) > 1:
                content = parts[1]
        return content.strip()


class GraphEnricher:
    """
    Full pipeline for enriching documents with knowledge graph data.
    
    Combines entity extraction and relation extraction into a single workflow.
    
    Example:
        enricher = GraphEnricher(llm)
        graph_doc = enricher.enrich(document)
    """
    
    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        entity_extractor: Optional[EntityExtractor] = None,
        relation_extractor: Optional[RelationExtractor] = None,
    ):
        """
        Initialize the enricher.
        
        Args:
            llm: Optional LLM instance.
            entity_extractor: Optional custom entity extractor.
            relation_extractor: Optional custom relation extractor.
        """
        self.llm = llm
        self.entity_extractor = entity_extractor or EntityExtractor(llm)
        self.relation_extractor = relation_extractor or RelationExtractor(llm)
    
    def enrich(self, document: Document) -> GraphDocument:
        """
        Enrich a document with knowledge graph data.
        
        Args:
            document: The source document to enrich.
            
        Returns:
            A GraphDocument with extracted entities and relations.
        """
        # Extract entities
        entities = self.entity_extractor.extract_entities(
            text=document.content,
            source=document.source_path,
        )
        
        # Extract relations
        relations = self.relation_extractor.extract_relations(
            entities=entities,
            text=document.content,
            source=document.source_path,
        )
        
        return GraphDocument(
            doc_id=document.doc_id,
            entities=entities,
            relations=relations,
        )
    
    def enrich_batch(
        self,
        documents: List[Document],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[GraphDocument]:
        """
        Enrich multiple documents.
        
        Args:
            documents: List of documents to enrich.
            progress_callback: Optional callback(completed, total).
            
        Returns:
            List of enriched GraphDocuments.
        """
        graph_docs = []
        total = len(documents)
        
        for i, doc in enumerate(documents):
            graph_docs.append(self.enrich(doc))
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return graph_docs
