import logging
import yaml
import os
import json
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class GraphConnector:
    """Base class for Neo4j Graph DB connections."""
    
    def __init__(self, config: dict):
        self.config = config
        self.uri = config.get("uri", "bolt://localhost:7687")
        self.user = config.get("user", "neo4j")
        self.password = config.get("password", "neo4j")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        logger.info(f"Connected to Neo4j at {self.uri} as user {self.user}")
    
    def close(self):
        self.driver.close()
        logger.info("Neo4j driver closed")
    
    def insert_triples(self, triples: list):
        """Insert triples into the graph database.
        Each triple is a tuple (subject, predicate, object)."""
        with self.driver.session() as session:
            for triple in triples:
                subject, predicate, object_ = triple
                session.write_transaction(self._insert_triple, subject, predicate, object_)
        logger.info(f"Inserted {len(triples)} triples into the graph database.")
    
    @staticmethod
    def _insert_triple(tx, subject: str, predicate: str, object_: str):
        cypher_query = """
        MERGE (a:Entity {name: $subject})
        MERGE (b:Entity {name: $object})
        MERGE (a)-[r:RELATION {type: $predicate}]->(b)
        """
        tx.run(cypher_query, subject=subject, predicate=predicate, object=object_)
    
    def query(self, cypher_query: str, parameters: dict = {}):
        """Execute a Cypher query and return the results."""
        with self.driver.session() as session:
            result = session.run(cypher_query, parameters)
            results = [record.data() for record in result]
            logger.info(f"Query executed: {cypher_query} with parameters: {parameters}")
            return results
    
    def delete_all(self):
        """Delete all nodes and relationships from the graph database."""
        with self.driver.session() as session:
            session.write_transaction(lambda tx: tx.run("MATCH (n) DETACH DELETE n"))
        logger.info("Deleted all nodes and relationships from the graph database.")


class EsgGraphDB(GraphConnector):
    """Platform-specific knowledge graph store for ESG data using Neo4j."""
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path) as f:
            config = yaml.safe_load(f)['databases']['esg_graph_db']
        super().__init__(config)


class FinraGraphDB(GraphConnector):
    """Platform-specific knowledge graph store for FINRA data using Neo4j."""
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path) as f:
            config = yaml.safe_load(f)['databases']['finra_graph_db']
        super().__init__(config)


class GdprGraphDB(GraphConnector):
    """Platform-specific knowledge graph store for GDPR data using Neo4j."""
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path) as f:
            config = yaml.safe_load(f)['databases']['gdpr_graph_db']
        super().__init__(config)