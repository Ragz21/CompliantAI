import re
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llms.esg import ESG
from PyPDF2 import PdfReader

# Generate a mini-report using the ESG summarize_text method
def generate_mini_report(esg_system, text_chunk):
    """Generate a mini-report for the given text chunk using ESG."""
    return esg_system.mini_report(text_chunk)

# Combine multiple mini-reports into one comprehensive report using ESG summarize_text method
def combine_reports(esg_system, reports):
    """Combine multiple mini-reports into one comprehensive report using ESG."""
    combined_message = "\n\n".join(reports)
    return esg_system.summarize_text(combined_message)

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file using PyPDF2.
    """
    text = ""
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        raise RuntimeError(f"Failed to extract PDF text: {str(e)}")
    return text.strip()

def total_reduce(file_path):
    try:
        # Extract text from PDF
        text = extract_text_from_pdf(file_path)
    except FileNotFoundError:
        raise RuntimeError(f"Input file '{file_path}' not found.")

    # Chunk text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=50000,
        chunk_overlap=0,
        separators=["\n"]
    )
    chunks = text_splitter.split_text(text)
    
    if not chunks:
        raise ValueError("No content to process after splitting.")
    
    esg_system = ESG(config_path="config/config.yaml")

    mini_report_texts = [generate_mini_report(esg_system, chunk) for chunk in chunks[0:3]]

    # Reduce reports recursively
    group_size = 3
    while len(mini_report_texts) > 1:
        combined_report_texts = []
        for i in range(0, len(mini_report_texts), group_size):
            group = mini_report_texts[i:i+group_size]
            combined = combine_reports(esg_system, group)
            combined_report_texts.append(combined)
        mini_report_texts = combined_report_texts

    final_context = mini_report_texts[0]
    query = "Generate a complete ESG compliance report based on the findings below."
    final_report = esg_system.answer_query(query, context=final_context)
    return final_report