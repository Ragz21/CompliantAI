from llms.esg import ESG
from llms.rag import RAG

def insert_docs(folder_path):
    # folder_path = ""
    llm = RAG(config_path="config/config.yaml")
    llm.index_documents(folder=folder_path, use_esg=True)

    print("Indexed ESG documents successfully.")

def main():

    # insert_docs("")
    lt = ESG(config_path="config/config.yaml")
    user_query = input("Enter your ESG query: ")
    response = lt.answer_query(user_query)
    print("ESG Response:")
    print(response)

if __name__ == "__main__":
    main()