import json
import uuid
import hashlib
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter, MarkdownTextSplitter
from core.llm.base import BaseLLM

import json
import ollama

logger = logging.getLogger(__name__)

class DocumentProcessor(BaseLLM):
    def __init__(self, config_path: str = None, **kwargs):
        super().__init__(config_path, **kwargs)
        doc_config = self.config.get("document_processor", {})
        self.system_prompt = self._get_system_prompt("config/prompts/document_processor.txt")
        self.chunking_config = {"chunking_profiles": doc_config.get("chunking_profiles", {})}
        self.embedding_model = doc_config.get("embedding_model", "nomic-embed-text")
        # print()
        # print(doc_config)
        # logger.info(f"DocumentProcessor initialized with system_prompt: {self.system_prompt}, chunking_config: {self.chunking_config}, embedding_model: {self.embedding_model}")
    
    def _generate_chunk_id(self, text: str) -> str:
        return f"{hashlib.sha256(text.encode()).hexdigest()[:16]}-{str(uuid.uuid4())[:4]}"
    
    def generate_embedding(self, text: str, model: str) -> list:
        response = ollama.embeddings(model=model, prompt=text)
        return response["embedding"]
    
    def _select_chunking_profile(self, doc_type: str) -> dict:
        profiles = self.chunking_config.get("chunking_profiles", {})
        profile = profiles.get(doc_type, profiles.get("default", {}))
        logger.info(f"Selected chunking profile for doc_type '{doc_type}': {profile}")
        return profile
    
    def _get_text_splitter(self, doc_type: str):
        profile = self._select_chunking_profile(doc_type)
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
    
    def _preprocess_document(self, document: str, doc_type: str) -> str:
        # TODO: to check format
        # if doc_type == "abc":
        #     return document.replace().replace()
        return document
    
    def _validate_metadata(self, metadata: dict, doc_type: str):
        expected = self._select_chunking_profile(doc_type).get('metadata_headers', [])
        missing = [h for h in expected if h not in metadata]
        if missing:
            logger.warning(f"Missing metadata headers: {missing}")
    
    def _parse_enrichment_response(self, chunk: str, response: str) -> dict:
        try:
            metadata = json.loads(response.strip("```"))
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response")
            metadata = {"raw_response": response}
        return {
            "text": chunk,
            "embedding": self.generate_embedding(chunk, self.embedding_model),
            "metadata": metadata
        }
    
    def _enrich_esg_chunk(self, chunk: str) -> dict:
        prompt = f"""
        {self.system_prompt}
        
        Analyze this ESG document chunk and extract structured information:
        
        {chunk}
        
        Output JSON with:
        - "summary": 3-sentence overview
        - "standard": Official standard name/number
        - "requirements": List of requirement texts with hierarchy
        - "recommendations": List of recommendation texts
        - "guidance": List of guidance explanations
        - "metrics": List of mentioned metrics
        - "entities": Organizations, frameworks, or regulations mentioned
        """
        response = self._call_llm(prompt)
        enriched = self._parse_enrichment_response(chunk, response)
        enriched["metadata"]["chunk_id"] = self._generate_chunk_id(chunk)
        logger.info(f"ESG chunk enriched with chunk_id: {enriched['metadata']['chunk_id']}")
        # print()
        # print('----------------')
        # print(enriched)
        self._validate_metadata(enriched["metadata"], "esg")
        return enriched
    
    # TODO: _enrich_finra_chunk, _enrich_gdpr_chunk

    def _enrich_generic_chunk(self, chunk: str) -> dict:
        # Placeholder for generic enrichment logic
        response = self._call_llm(f"{self.system_prompt}\nProcess the following chunk:\n{chunk}")
        enriched = self._parse_enrichment_response(chunk, response)
        enriched["metadata"]["chunk_id"] = self._generate_chunk_id(chunk)
        self._validate_metadata(enriched["metadata"], "default")
        return enriched
    
    def _call_llm(self, prompt: str) -> str:
        logger.info(f"Calling BaseLLM.generate with prompt: {prompt}")
        response = self.generate(prompt)
        return response
    
    def process_document(self, document: str, doc_type: str = "esg") -> list:
        logger.info(f"Starting document processing for doc_type: {doc_type}")
        processed_doc = self._preprocess_document(document, doc_type)
        splitter = self._get_text_splitter(doc_type)
        chunks = splitter.split_text(processed_doc)
        logger.info(f"Document split into {len(chunks)} chunks")
        enriched_chunks = []
        for idx, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {idx+1}/{len(chunks)}")
            if doc_type.startswith("esg"):
                enriched = self._enrich_esg_chunk(chunk)
            # TODO: _enrich_finra_chunk, _enrich_gdpr_chunk
            # elif doc_type.startswith(""):
            #     enriched = self._enrich_esg_chunk(chunk)
            else:
                enriched = self._enrich_generic_chunk(chunk)
            enriched_chunks.append(enriched)
        logger.info("Completed document processing")
        return enriched_chunks