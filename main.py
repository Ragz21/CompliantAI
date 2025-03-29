from llms.rag import RAG
from core.utils.documents_processor import DocumentProcessor
from llms.esg import ESG

def main():
    # Running Main AIs
    esg_system = ESG(config_path="config/config.yaml")
    query = "What are the requirements of 301-2?"
    answer = esg_system.answer_query(query)
    print("ESG Answer:")
    print(answer)

    # # Running RAG
    # rag_system = RAG(config_path="config/config.yaml")
    # folder_path = "/Users/ragz/Library/Mobile Documents/com~apple~CloudDocs/Freelance/AIROI/AI/output copy/"
    # rag_system.index_documents(folder=folder_path, use_esg=True)
    # query = "What are the requirements of 301-2"
    # result = rag_system.answer_query(query, use_esg=True, k=3)
    # print("Query Results:")
    # print(result)

    # # For Document Processor
    # processor = DocumentProcessor(config_path="config/config.yaml")
    # sample_document = """
    # This is a sample ESG document.
    # It contains information about sustainability metrics, standards, and guidelines.
    # """
    # enriched_chunks = processor.process_document(sample_document, doc_type="esg")
    # print("Enriched Document Chunks:")
    # for idx, chunk in enumerate(enriched_chunks, start=1):
    #     print(f"Chunk {idx}:")
    #     print(chunk)
    #     print("-" * 40)

if __name__ == "__main__":
    main()
