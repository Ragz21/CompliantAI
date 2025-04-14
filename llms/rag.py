from core.llm.base import BaseLLM
import os
import logging
from core.utils.documents_processor import DocumentProcessor
from core.db.vector_db import EsgDB
from core.db.graph_db import EsgGraphDB
import ollama

logger = logging.getLogger(__name__)

class RAG(BaseLLM):
    """RAG with Multi-DB Routing"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        super().__init__(config_path=config_path)
        self.system_prompt = self._get_system_prompt("config/prompts/sorcerer_supreme.txt")
        self.esg_vector_db = EsgDB(config_path=config_path)
        self.esg_graph_db = EsgGraphDB(config_path=config_path)
        # TODO: other DB
        self.embedding_model = self.config.get("document_processor", {}).get("embedding_model", "nomic-embed-text")

    def insert_documents_and_triples(self, vector_db, graph_db, enriched_chunks, dp):
        """
        Insert enriched chunks into the vector database and graph database.
        """
        # Insert into Vector DB
        for chunk in enriched_chunks:
            vector_db.insert_documents(
                ids=[chunk["metadata"]["chunk_id"]],
                documents=[chunk["text"]],
                metadatas=[chunk["metadata"]],
                embeddings=[chunk["embedding"]]
            )
        # Insert into Graph DB
        for chunk in enriched_chunks:
            graph_triples = dp.process_document_for_graph(chunk["text"])
            if graph_triples:
                graph_db.insert_triples(graph_triples)

    def index_documents(self, folder: str, doc_type: str):
        """
        Process all text files in a folder and insert their enriched data into
        EsgDB if use_esg is True, or KnowhereDB otherwise.
        """
        # Define document processor        
        dp = DocumentProcessor(config_path="config/config.yaml")

        # Process each file in the folder
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path) and filename.endswith(".txt"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                enriched_chunks = dp.process_document(content, doc_type=doc_type)
                if doc_type == "esg":
                    # Insert into Vector DB and Graph DB
                    self.insert_documents_and_triples(self.esg_vector_db, self.esg_graph_db, enriched_chunks, dp)
                elif doc_type == "gdpr":
                    # Insert into Vector DB and Graph DB
                    self.insert_documents_and_triples(self.gdpr_vector_db, self.gdpr_graph_db, enriched_chunks, dp)
                else:
                    # Insert into Vector DB and Graph DB
                    self.insert_documents_and_triples(self.finra_vector_db, self.finra_graph_db, enriched_chunks, dp)
                # Log
                logger.info(f"Indexed file {filename} into {doc_type.upper()} Vector DB and Graph DB")

    def answer_query(self, query: str, doc_type: str, k:int) -> dict:
        """
        Query the correct vector database (EsgDB, GdprDB, FinraDB) based on the flag,
        then return the retrieved context.
        """
        query_embedding = self.generate_embedding(query, self.embedding_model)
        if doc_type == "esg":
            results = self.esg_vector_db.query([query_embedding], n_results=k)
        elif doc_type == "gdpr":
            results = self.gdpr_vector_db.query([query_embedding], n_results=k)
        else:
            results = self.finra_vector_db.query([query_embedding], n_results=k)
        context = "\n".join([result["document"] for result in results])
        return {"context": context, "retrieved": results}
        
    def generate_embedding(self, text: str, model: str) -> list:
        response = ollama.embeddings(model=model, prompt=text)
        return response["embedding"]