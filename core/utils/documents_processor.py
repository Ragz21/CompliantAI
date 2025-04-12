import json
import uuid
import hashlib
import logging
import re
from langchain.text_splitter import RecursiveCharacterTextSplitter, MarkdownTextSplitter
from core.llm.base import BaseLLM
import ollama

logger = logging.getLogger(__name__)


class TextSplitterFactory:
    @staticmethod
    def get_text_splitter(doc_type: str, chunking_config: dict):
        profiles = chunking_config.get("chunking_profiles", {})
        profile = profiles.get(doc_type, profiles.get("default", {}))
        logger.info(f"Selected chunking profile for doc_type '{doc_type}': {profile}")
        strategy = profile.get("strategy", "recursive")
        if strategy == "recursive":
            splitter = RecursiveCharacterTextSplitter(
                separators=profile.get("separators", ["\n\n"]),
                chunk_size=profile.get("chunk_size", 1000),
                chunk_overlap=profile.get("chunk_overlap", 200)
            )
        elif strategy == "markdown":
            splitter = MarkdownTextSplitter(
                chunk_size=profile.get("chunk_size", 800),
                chunk_overlap=profile.get("chunk_overlap", 100)
            )
        else:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=profile.get("chunk_size", 1000),
                chunk_overlap=profile.get("chunk_overlap", 200)
            )
        logger.info(f"Using text splitter '{strategy}' for doc_type '{doc_type}' with chunk_size {profile.get('chunk_size')} and chunk_overlap {profile.get('chunk_overlap')}")
        return splitter


class ChunkEnricher:
    def __init__(self, system_prompt: str, embedding_model: str, llm):
        self.system_prompt = system_prompt
        self.embedding_model = embedding_model
        self.llm = llm  # Expecting an object with a 'generate' method

    def generate_embedding(self, text: str):
        response = ollama.embeddings(model=self.embedding_model, prompt=text)
        return response["embedding"]

    def _generate_chunk_id(self, text: str) -> str:
        return f"{hashlib.sha256(text.encode()).hexdigest()[:16]}-{str(uuid.uuid4())[:4]}"
    
    def _safe_json_load(self, text):
        # Try to directly find JSON-like content
        cleaned = text.strip()
        
        # Remove markdown code blocks if any
        cleaned = re.sub(r"^```(json)?", "", cleaned)
        cleaned = re.sub(r"```$", "", cleaned)
        
        # Replace wrong quotes
        cleaned = cleaned.replace("‘", '"').replace("’", '"').replace("“", '"').replace("”", '"')
        cleaned = cleaned.strip()

        # Try to extract JSON part if there's extra junk
        match = re.search(r'(\{.*\})', cleaned, re.DOTALL)
        if match:
            json_text = match.group(1)
            return json.loads(json_text)
        
        # Fallback if no match
        return json.loads(cleaned)

    def _parse_enrichment_response(self, chunk: str, response: str) -> dict:
        try:
            metadata = self._safe_json_load(response)
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response after cleaning")
            metadata = {"raw_response": response}
        return {
            "text": chunk,
            "embedding": self.generate_embedding(chunk),
            "metadata": metadata
        }

    def enrich_chunk(self, doc_type: str, chunk: str, metadata_headers: list = None) -> dict:
        if doc_type.startswith("esg"):
            prompt = f"""
                        {self.system_prompt}

                        Analyze this {doc_type} document chunk and extract structured information.

                        IMPORTANT: Only output VALID JSON. 
                        No text or explanation outside JSON. 
                        No markdown formatting.

                        Here is the chunk:
                        {chunk}

                        Expected JSON with keys:
                        - summary
                        - standard
                        - requirements
                        - recommendations
                        - guidance
                        - metrics
                        - entities
                        """
        else:
            prompt = f"{self.system_prompt}\nProcess the following chunk:\n{chunk}"
        
        logger.info(f"Calling LLM with prompt for doc_type {doc_type}")
        response = self.llm.generate(prompt)
        enriched = self._parse_enrichment_response(chunk, response)
        enriched["metadata"]["chunk_id"] = self._generate_chunk_id(chunk)
        if metadata_headers:
            missing = [h for h in metadata_headers if h not in enriched["metadata"]]
            if missing:
                logger.warning(f"Missing metadata headers: {missing}")
        return enriched

    def extract_graph_triples(self, chunk: str) -> list:
        prompt = f"""
            {self.system_prompt}

            Extract graph triples from the following text.

            IMPORTANT INSTRUCTIONS:
            - Only output valid JSON list.
            - No explanations.
            - No extra text.
            - No code blocks.
            - Start directly with '[' and end directly with ']'.

            Example:
            [
                ["Subject1", "predicate1", "Object1"],
                ["Subject2", "predicate2", "Object2"]
            ]

            Text:
            {chunk}
            """
        logger.info("Extracting graph triples from chunk")
        response = self.llm.generate(prompt)
        try:
            triples = self._safe_json_load(response)
        except json.JSONDecodeError:
            logger.error("Failed to parse graph triples from LLM response")
            triples = []
        return triples

class DocumentProcessor(BaseLLM):
    def __init__(self, config_path: str = None, **kwargs):
        super().__init__(config_path, **kwargs)
        doc_config = self.config.get("document_processor", {})
        self.system_prompt = self._get_system_prompt("config/prompts/document_processor.txt")
        self.chunking_config = {"chunking_profiles": doc_config.get("chunking_profiles", {})}
        self.embedding_model = doc_config.get("embedding_model", "nomic-embed-text")
    
    def _generate_chunk_id(self, text: str) -> str:
        return f"{hashlib.sha256(text.encode()).hexdigest()[:16]}-{str(uuid.uuid4())[:4]}"
    
    def _preprocess_document(self, document: str, doc_type: str) -> str:
        return document
    
    def process_document(self, document: str, doc_type: str = "esg") -> list:
        logger.info(f"Starting document processing for doc_type: {doc_type}")
        processed_doc = self._preprocess_document(document, doc_type)
        splitter = TextSplitterFactory.get_text_splitter(doc_type, self.chunking_config)
        chunks = splitter.split_text(processed_doc)
        logger.info(f"Document split into {len(chunks)} chunks")
        profile = self.chunking_config.get("chunking_profiles", {}).get(doc_type, {})
        metadata_headers = profile.get("metadata_headers", [])
        enricher = ChunkEnricher(self.system_prompt, self.embedding_model, self)
        enriched_chunks = []
        for idx, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {idx+1}/{len(chunks)}")
            enriched = enricher.enrich_chunk(doc_type, chunk, metadata_headers)
            enriched_chunks.append(enriched)
        logger.info("Completed document processing")
        return enriched_chunks
    
    def process_document_for_graph(self, document: str, doc_type: str = "esg") -> list:
        logger.info(f"Starting graph processing for document of doc_type: {doc_type}")
        processed_doc = self._preprocess_document(document, doc_type)
        splitter = TextSplitterFactory.get_text_splitter(doc_type, self.chunking_config)
        chunks = splitter.split_text(processed_doc)
        all_triples = []
        enricher = ChunkEnricher(self.system_prompt, self.embedding_model, self)
        for idx, chunk in enumerate(chunks):
            logger.info(f"Extracting graph triples from chunk {idx+1}/{len(chunks)}")
            triples = enricher.extract_graph_triples(chunk)
            all_triples.extend(triples)
        logger.info("Completed graph processing for document")
        return all_triples