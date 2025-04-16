from llms.esg import ESG
from llms.rag import RAG
from fpdf import FPDF
from PyPDF2 import PdfReader, PdfFileMerger, PdfFileReader
import os
import re
import subprocess

# Initialize ESG model
esg_model = ESG(config_path="config/config.yaml")

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

def create_pdf(input_file):
    # Derive output folder and base filename
    folder = os.path.dirname(input_file)
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    tex_path = os.path.join(folder, f"{base_name}.tex")
    pdf_path = os.path.join(folder, f"{base_name}.pdf")

    # Read markdown-style content from input file
    with open(input_file, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # Convert markdown to LaTeX
    def markdown_to_latex(text):
        text = re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', text)
        text = re.sub(r'\*(.*?)\*', r'\\textit{\1}', text)
        text = re.sub(r'### (.*)', r'\\subsubsection*{\1}', text)
        text = re.sub(r'## (.*)', r'\\subsection*{\1}', text)
        text = re.sub(r'# (.*)', r'\\section*{\1}', text)
        text = re.sub(r'- (.*)', r'\\item \1', text)
        if '\\item' in text:
            text = '\\begin{itemize}\n' + text + '\n\\end{itemize}'
        return text.replace('%', '\\%')

    # Wrap content in a LaTeX document
    def wrap_latex(content):
        return f"""
                \\documentclass{{article}}
                \\usepackage[utf8]{{inputenc}}
                \\usepackage{{enumitem}}
                \\title{{LLM Analysis Report}}
                \\date{{\\today}}

                \\begin{{document}}

                \\maketitle

                {content}

                \\end{{document}}
                """

    latex_content = wrap_latex(markdown_to_latex(md_text))

    # Write LaTeX to .tex file
    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(latex_content)

    # Compile .tex to .pdf
    try:
        subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-output-directory', folder, tex_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"LaTeX compilation failed:\n{e.stderr.decode()}")

    return pdf_path

def analyze_esg_file(file_path: str, tags: list) -> str:
    """
    Analyze a PDF file for ESG compliance based on provided tags.

    Args:
        file_path (str): Path to the PDF file.
        tags (list): Tags like ['ESG', 'GDPR']

    Returns:
        str: Generated analysis report.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} does not exist.")
    
    # Extract text from PDF
    text = extract_text_from_pdf(file_path)

    # Formulate query
    query = "Please evaluate this company’s ESG compliance based on its statements about emissions reduction, employee welfare, and board transparency in the uploaded report."
    
    # Get answer from LLM
    return esg_model.answer_query(query, text)

