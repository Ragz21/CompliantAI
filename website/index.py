import sys
import os
from flask import Flask, render_template, request, jsonify, send_from_directory, session, send_file
import time
import json
import traceback
from werkzeug.utils import secure_filename
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ans_query import analyze_esg_file, create_pdf
from datetime import datetime
from map_reduce_example import total_reduce

app = Flask(__name__)
app.secret_key = 'compliant_ai_secret_key'  # For session management

# Configure upload and output folders
UPLOAD_FOLDER = 'input_data'
OUTPUT_FOLDER = 'output_data'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Store documents in memory (in a real app, this would be a database)
documents = []

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_output_filename(original_name, tags):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    tags_str = '_'.join(tags)
    base_name = os.path.splitext(original_name)[0]
    return f"{base_name}_{tags_str}_{timestamp}.txt"

@app.route('/')
def index():
    return render_template('index.html', documents=documents)

# The static files (like index.css) will be served from the "static" folder by Flask automatically.

# (Keep your other endpoints as-is, e.g., /upload, /files, /update_tag, etc.)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Add document to the list
        document = {
            'name': filename,
            'path': filepath,
            'tags': []  # Initialize with empty tags
        }
        documents.append(document)
        
        return jsonify({
            'success': True,
            'message': f'File {filename} uploaded successfully',
            'document': document
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/files', methods=['GET'])
def list_files():
    # Get list of files from the upload folder
    files = os.listdir(UPLOAD_FOLDER)
    pdf_files = []
    
    for f in files:
        if f.lower().endswith('.pdf'):
            # Find document in our documents list
            doc = next((doc for doc in documents if doc['name'] == f), None)
            if doc:
                pdf_files.append({
                    'name': f,
                    'tags': doc.get('tags', [])
                })
            else:
                # If document not in our list, add it with empty tags
                doc = {
                    'name': f,
                    'path': os.path.join(UPLOAD_FOLDER, f),
                    'tags': []
                }
                documents.append(doc)
                pdf_files.append({
                    'name': f,
                    'tags': []
                })
    
    return jsonify(pdf_files)

@app.route('/output_files', methods=['GET'])
def list_output_files():
    files = os.listdir(OUTPUT_FOLDER)
    output_files = []
    
    for f in files:
        if f.endswith('.txt') or f.endswith('.pdf'):
            try:
                filename_wo_ext = f.replace('.txt', '')
                parts = filename_wo_ext.split('_')
                timestamp_str = '_'.join(parts[-2:])  # Last two parts form the timestamp
                base_parts = parts[:-2]  # Everything before the timestamp
                
                # The last part before the timestamp is always a tag
                # Work backwards to find where tags start
                tags = []
                name_parts = []
                
                # Known tags to look for
                known_tags = ['GDPR', 'ESG', 'SASB', 'HIPAA', 'FINRA']
                
                for part in reversed(base_parts):
                    if part in known_tags:
                        tags.insert(0, part)
                    else:
                        name_parts.insert(0, part)
                
                # Join the name parts back together
                display_name = ' '.join(name_parts)
                
                # Format timestamp
                try:
                    dt = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    formatted_time = dt.strftime('%B %d, %Y %I:%M %p')
                except Exception as e:
                    print(f"Error parsing timestamp {timestamp_str}: {str(e)}")
                    formatted_time = timestamp_str
                
                # Read file content
                with open(os.path.join(OUTPUT_FOLDER, f), 'r', encoding='utf-8') as file:
                    content = file.read()
                
                output_files.append({
                    'filename': f,
                    'display_name': display_name,
                    'tags': tags,
                    'timestamp': formatted_time,
                    'content': content
                })
            except Exception as e:
                print(f"Error parsing file {f}: {str(e)}")
                continue
    
    # Sort by timestamp (newest first)
    output_files.sort(key=lambda x: datetime.strptime(x['timestamp'], '%B %d, %Y %I:%M %p'), reverse=True)
    return jsonify(output_files)

@app.route('/update_tag', methods=['POST'])
def update_tag():
    data = request.json
    file_name = data.get('file_name')
    tags = data.get('tags', [])
    
    if not file_name:
        return jsonify({'error': 'Missing file name'}), 400
    
    # Find the document and update its tags
    doc = next((doc for doc in documents if doc['name'] == file_name), None)
    if doc:
        doc['tags'] = tags
        return jsonify({
            'success': True,
            'message': f'Tags updated for {file_name}',
            'tags': tags
        })
    
    return jsonify({'error': 'Document not found'}), 404

@app.route('/analyze', methods=['POST'])
def analyze_file():
    data = request.json
    file_name = data.get('file_name')
    tags = data.get('tags', [])

    if not file_name or not tags:
        return jsonify({'error': 'Missing file or tags'}), 400

    document = next((doc for doc in documents if doc['name'] == file_name), None)
    if not document:
        return jsonify({'error': 'Document not found'}), 404

    try:
        report = total_reduce(document['path'])
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

    output_filename = generate_output_filename(file_name, tags)
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
    except Exception as e:
        return jsonify({'error': 'Failed to save analysis'}), 500

    try:
        pdf_path = create_pdf(output_path)
        print(f"[DEBUG] PDF created at: {pdf_path}")
    except Exception as e:
        return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500

    return jsonify({
        'success': True,
        'file_name': file_name,
        'tags': tags,
        'report': report,
        'output_file': output_filename[:-3]+'.pdf',
        'pdf_file': os.path.basename(pdf_path)
    })

# def generate_mock_report(file_name, tags):
#     """Generate a mock analysis report based on the file name and tags."""
#     report = f"Analysis Report for {file_name}\n\n"
#     report += f"Tags: {', '.join(tags)}\n\n"
    
#     report += "Compliance Checks:\n"
#     report += "----------------\n"
    
#     # Add some mock compliance checks based on tags
#     if 'GDPR' in tags:
#         report += "- GDPR compliance: PASSED\n"
#         report += "  - Data protection measures are in place\n"
#         report += "  - Privacy notices are properly formatted\n"
    
#     if 'ESG' in tags:
#         report += "- ESG compliance: PASSED\n"
#         report += "  - Environmental impact assessment completed\n"
#         report += "  - Social responsibility metrics documented\n"
    
#     if 'SASB' in tags:
#         report += "- SASB compliance: PASSED\n"
#         report += "  - Industry-specific metrics reported\n"
#         report += "  - Financial impact of sustainability measures documented\n"
    
#     if 'HIPAA' in tags:
#         report += "- HIPAA compliance: PASSED\n"
#         report += "  - Patient data protection measures verified\n"
#         report += "  - Security controls are properly implemented\n"
    
#     if 'FINRA' in tags:
#         report += "- FINRA compliance: PASSED\n"
#         report += "  - Trading practices reviewed\n"
#         report += "  - Customer protection measures verified\n"
    
#     report += "\nNotes:\n"
#     report += "------\n"
#     report += "- This is a mock analysis report for demonstration purposes.\n"
#     report += "- In a real application, this would contain actual analysis results.\n"
#     report += f"- Analysis was performed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
#     return report


@app.route('/input_data/<path:filename>')
def serve_pdf(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/output_data/<path:filename>')
def serve_output(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

@app.route('/analysis')
def analysis_page():
    return render_template('analysis.html')

if __name__ == '__main__':
    app.run(debug=True)