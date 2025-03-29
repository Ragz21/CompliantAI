import re
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llms.esg import ESG

# Generate a mini-report using the ESG summarize_text method
def generate_mini_report(esg_system, text_chunk):
    """Generate a mini-report for the given text chunk using ESG."""
    return esg_system.mini_report(text_chunk)

# Combine multiple mini-reports into one comprehensive report using ESG summarize_text method
def combine_reports(esg_system, reports):
    """Combine multiple mini-reports into one comprehensive report using ESG."""
    combined_message = "\n\n".join(reports)
    return esg_system.summarize_text(combined_message)


def main():
    input_file = "sample_input.txt" 
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Input file '{input_file}' not found.")
        return
    
    #TODO: Add logical chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=3000,
        chunk_overlap=0,
        separators=["\n"]
    )
    chunks = text_splitter.split_text(text)
    print(f"Total steps required to process your document: {len(chunks)}")
    
    esg_system = ESG(config_path="config/config.yaml")
    
    mini_report_texts = []
    print("Generating mini-reports for each chunk...")
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}...")
        mini_report = generate_mini_report(esg_system, chunk)
        mini_report_texts.append(mini_report)
    
    round_counter = 1
    group_size = 3
    while len(mini_report_texts) > 1:
        print(f"Combining reports: Round {round_counter} (Total reports: {len(mini_report_texts)})")
        combined_report_texts = []
        for i in range(0, len(mini_report_texts), group_size):
            group = mini_report_texts[i:i+group_size]
            combined_report = combine_reports(esg_system, group)
            combined_report_texts.append(combined_report)
        mini_report_texts = combined_report_texts
        round_counter += 1
    
    final_report_text = mini_report_texts[0]
    print("Final Report:")
    print(final_report_text)


if __name__ == "__main__":
    main()
