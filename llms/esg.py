from core.llm.base import BaseLLM
from llms.rag import RAG
import logging

logger = logging.getLogger(__name__)

class ESG(BaseLLM):
    """
    ESG is an ESG-focused LLM that inherits from BaseLLM.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        super().__init__(config_path=config_path)
        self.system_prompt = self._get_system_prompt("config/prompts/esg.txt")
        self.rag = RAG(config_path=config_path)
        logger.info("ESG initialized.")
        
    def answer_query(self, query: str) -> str:
        """
        Process a user's ESG query
        """
        logger.info("Received query: %s", query)
        if len(query.strip().split()) < 3:
            clarification = ("Your query seems a bit brief. "
                            "Could you please provide more details regarding your ESG standards question?")
            logger.info("Query too brief; returning clarification prompt.")
            return clarification
        result = self.rag.answer_query(query, use_esg=True, k=5)
        context = result.get("context", "")
        final_prompt = (
            f"{self.system_prompt}\n\n"
            f"Context:\n{context}\n\n"
            f"User Query: {query}\n\n"
            "Provide a detailed answer regarding ESG standards. "
            "If more information is needed, ask follow-up questions."
        )
        logger.debug("Constructed final prompt: %s", final_prompt)
        answer = self.generate(final_prompt)
        # logger.info("Generated answer: %s", answer)
        return answer
    
    def ask_followup(self, followup: str) -> str:
        """
        Process a follow-up question.
        """
        logger.info("Received follow-up question: %s", followup)
        result = self.rag.answer_query(followup, use_esg=True, k=5)
        answer = result.get("answer", "I'm sorry, I couldn't retrieve ESG information for your follow-up query.")
        logger.info("Follow-up answer: %s", answer)
        return answer