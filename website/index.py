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
UPLOAD_FOLDER = 'website/input_data'
OUTPUT_FOLDER = 'website/output_data'
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

from werkzeug.utils import secure_filename

@app.route('/files', methods=['GET'])
def list_files():
    # Get list of files from the upload folder
    files = os.listdir(UPLOAD_FOLDER)
    pdf_files = []

    for f in files:
        if f.lower().endswith('.pdf'):
            safe_name = secure_filename(f)  # remove special chars, spaces
            original_path = os.path.join(UPLOAD_FOLDER, f)
            safe_path = os.path.join(UPLOAD_FOLDER, safe_name)

            # If the safe version doesn't exist yet, rename it
            if f != safe_name and not os.path.exists(safe_path):
                os.rename(original_path, safe_path)
                f = safe_name

            # Find document in our documents list
            doc = next((doc for doc in documents if doc['name'] == f), None)
            if not doc:
                doc = {
                    'name': f,
                    'path': os.path.join(UPLOAD_FOLDER, f),
                    'tags': []
                }
                documents.append(doc)

            pdf_files.append({
                'name': f,
                'tags': doc['tags']
            })

    return jsonify(pdf_files)


@app.route('/output_files', methods=['GET'])
def list_output_files():
    files = os.listdir(OUTPUT_FOLDER)
    output_files = []
    
    for f in files:
        if f.endswith('.txt') or f.endswith('.pdf'):
            try:
                filename_wo_ext = os.path.splitext(f)[0]
                parts = filename_wo_ext.split('_')
                timestamp_str = '_'.join(parts[-2:])
                base_parts = parts[:-2]

                tags = []
                name_parts = []
                known_tags = ['GDPR', 'ESG', 'SASB', 'HIPAA', 'FINRA']

                for part in reversed(base_parts):
                    if part in known_tags:
                        tags.insert(0, part)
                    else:
                        name_parts.insert(0, part)

                display_name = ' '.join(name_parts)
                try:
                    dt = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    formatted_time = dt.strftime('%B %d, %Y %I:%M %p')
                except Exception as e:
                    print(f"Error parsing timestamp {timestamp_str}: {str(e)}")
                    formatted_time = timestamp_str

                # Read content only if it's a .txt file
                content = ""
                if f.endswith('.txt'):
                    with open(os.path.join(OUTPUT_FOLDER, f), 'r', encoding='utf-8') as file:
                        content = file.read()
                elif f.endswith('.pdf'):
                    content = None  # signal to frontend to load with iframe

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

# @app.route('/analyze', methods=['POST'])
# def analyze_file():
#     data = request.json
#     file_name = data.get('file_name')
#     tags = data.get('tags', [])

#     if not file_name or not tags:
#         return jsonify({'error': 'Missing file or tags'}), 400

#     document = next((doc for doc in documents if doc['name'] == file_name), None)
#     if not document:
#         return jsonify({'error': 'Document not found'}), 404

#     try:
#         report = total_reduce(document['path'])
#     except Exception as e:
#         traceback.print_exc()
#         return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

#     # Generate filenames
#     base_name = os.path.splitext(generate_output_filename(file_name, tags))[0]
#     txt_path = os.path.join(app.config['OUTPUT_FOLDER'], base_name + ".txt")

#     # Write temporary text report
#     try:
#         with open(txt_path, 'w', encoding='utf-8') as f:
#             f.write(report)
#     except Exception as e:
#         return jsonify({'error': 'Failed to save temporary analysis'}), 500

#     # Convert to PDF
#     try:
#         pdf_path = create_pdf(txt_path)
#         os.remove(txt_path)  # Clean up .txt if not needed
#     except Exception as e:
#         return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500

#     return jsonify({
#         'success': True,
#         'file_name': file_name,
#         'tags': tags,
#         'pdf_file': os.path.basename(pdf_path),
#         'pdf_file_url': f"/output_data/{os.path.basename(pdf_path)}"
#     })

@app.route('/analyze', methods=['POST'])
def analyze_file():
    data = request.json
    file_name = data.get('file_name')
    tags = data.get('tags', [])
    
    if not file_name or not tags:
        return jsonify({'error': 'Missing file name or tags'}), 400
    
    # Find the document in our list
    doc = next((d for d in documents if d['name'] == file_name), None)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    
    try:
        # Analyze the document
        print(f"Analyzing file: {doc['path']}")
        report = total_reduce(doc['path'])
        
        # Generate output filename with tags
        base_name = os.path.splitext(generate_output_filename(file_name, tags))[0]
        txt_path = os.path.join(app.config['OUTPUT_FOLDER'], base_name + ".txt")
        
        # Ensure OUTPUT_FOLDER exists
        os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
        
        print(f"Writing temporary text report to: {txt_path}")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        try:
            # Create PDF
            print(f"Creating PDF from: {txt_path}")
            pdf_path = create_pdf(txt_path)
            pdf_filename = os.path.basename(pdf_path)
            
            # Verify the PDF exists
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF file not created at: {pdf_path}")
                
            print(f"PDF created at: {pdf_path}")
            
            # Clean up text file if successful
            os.remove(txt_path)
            
            return jsonify({
                'success': True,
                'file_name': file_name,
                'tags': tags,
                'pdf_file': pdf_filename,
                'pdf_file_url': f"/output_data/{pdf_filename}"
            })
            
        except Exception as e:
            error_msg = f"PDF generation failed: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            return jsonify({'error': error_msg}), 500
            
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500

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

@app.route('/debug/files')
def debug_files():
    """List all files in the upload and output folders with detailed information."""
    try:
        # Check if folders exist
        upload_exists = os.path.exists(UPLOAD_FOLDER)
        output_exists = os.path.exists(OUTPUT_FOLDER)
        
        # Get absolute paths
        upload_abs_path = os.path.abspath(UPLOAD_FOLDER)
        output_abs_path = os.path.abspath(OUTPUT_FOLDER)
        
        # List files in upload folder
        upload_files = []
        if upload_exists:
            for f in os.listdir(UPLOAD_FOLDER):
                file_path = os.path.join(UPLOAD_FOLDER, f)
                upload_files.append({
                    'name': f,
                    'path': file_path,
                    'abs_path': os.path.abspath(file_path),
                    'size': os.path.getsize(file_path) if os.path.isfile(file_path) else None,
                    'is_file': os.path.isfile(file_path),
                    'is_readable': os.access(file_path, os.R_OK)
                })
        
        # List files in output folder
        output_files = []
        if output_exists:
            for f in os.listdir(OUTPUT_FOLDER):
                file_path = os.path.join(OUTPUT_FOLDER, f)
                output_files.append({
                    'name': f,
                    'path': file_path,
                    'abs_path': os.path.abspath(file_path),
                    'size': os.path.getsize(file_path) if os.path.isfile(file_path) else None,
                    'is_file': os.path.isfile(file_path),
                    'is_readable': os.access(file_path, os.R_OK)
                })
        
        return jsonify({
            'app_root': os.path.abspath('.'),
            'upload_folder': {
                'path': UPLOAD_FOLDER,
                'abs_path': upload_abs_path,
                'exists': upload_exists,
                'is_readable': os.access(UPLOAD_FOLDER, os.R_OK) if upload_exists else False
            },
            'output_folder': {
                'path': OUTPUT_FOLDER,
                'abs_path': output_abs_path,
                'exists': output_exists,
                'is_readable': os.access(OUTPUT_FOLDER, os.R_OK) if output_exists else False
            },
            'upload_files': upload_files,
            'output_files': output_files,
            'documents': documents
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/debug/check_file/<path:filename>')
def debug_check_file(filename):
    """Check if a specific file exists and is readable."""
    # Try multiple paths to find the file
    paths_to_check = [
        filename,                           # As provided
        os.path.join(OUTPUT_FOLDER, filename),  # In output folder
        os.path.join(UPLOAD_FOLDER, filename),  # In upload folder
        os.path.abspath(filename),          # Absolute path
        os.path.abspath(os.path.join(OUTPUT_FOLDER, filename)),  # Absolute path in output
        os.path.abspath(os.path.join(UPLOAD_FOLDER, filename))   # Absolute path in upload
    ]
    
    results = {}
    file_found = False
    
    for path in paths_to_check:
        exists = os.path.exists(path)
        is_file = os.path.isfile(path) if exists else False
        is_readable = os.access(path, os.R_OK) if exists else False
        
        results[path] = {
            'exists': exists,
            'is_file': is_file,
            'is_readable': is_readable,
            'size': os.path.getsize(path) if is_file else None
        }
        
        if is_file:
            file_found = True
    
    return jsonify({
        'filename': filename,
        'file_found': file_found,
        'path_results': results
    })

# @app.route('/input_data/<path:filename>')
# def serve_pdf(filename):
#     return send_from_directory(UPLOAD_FOLDER, filename)
@app.route('/input_data/<path:filename>')
def serve_pdf(filename):
    """Serve files from the input directory with improved error handling."""
    try:
        # Get absolute path
        upload_folder_abs = os.path.abspath(UPLOAD_FOLDER)
        file_path = os.path.join(upload_folder_abs, filename)
        
        # Log the request for debugging
        print(f"Serving file: {filename}")
        print(f"Full path: {file_path}")
        
        # Verify the file exists
        if not os.path.exists(file_path):
            print(f"ERROR: File not found at {file_path}")
            
            # List available files in that directory
            if os.path.exists(upload_folder_abs):
                available_files = os.listdir(upload_folder_abs)
                print(f"Available files in {upload_folder_abs}: {available_files}")
            else:
                print(f"Upload folder doesn't exist: {upload_folder_abs}")
                
            return f"File not found: {filename}", 404
            
        # Verify it's a file and readable
        if not os.path.isfile(file_path):
            print(f"ERROR: Path exists but is not a file: {file_path}")
            return "Not a file", 400
            
        if not os.access(file_path, os.R_OK):
            print(f"ERROR: File exists but is not readable: {file_path}")
            return "Permission denied", 403
            
        print(f"Serving file successfully: {file_path}")
        return send_from_directory(upload_folder_abs, filename)
        
    except Exception as e:
        print(f"ERROR serving file {filename}: {str(e)}")
        traceback.print_exc()
        return f"Error serving file: {str(e)}", 500
# @app.route('/output_data/<path:filename>')
# def serve_output(filename):
#     return send_from_directory(OUTPUT_FOLDER, filename)

@app.route('/output_data/<path:filename>')
def serve_output(filename):
    """Serve files from the output directory with improved error handling."""
    try:
        # Get absolute paths
        output_folder_abs = os.path.abspath(OUTPUT_FOLDER)
        file_path = os.path.join(output_folder_abs, filename)
        
        # Log the request for debugging
        print(f"Serving file: {filename}")
        print(f"Full path: {file_path}")
        
        # Verify the file exists
        if not os.path.exists(file_path):
            print(f"ERROR: File not found at {file_path}")
            
            # Try to list available files in that directory
            if os.path.exists(output_folder_abs):
                available_files = os.listdir(output_folder_abs)
                print(f"Available files in {output_folder_abs}: {available_files}")
            else:
                print(f"Output folder doesn't exist: {output_folder_abs}")
                
            return f"File not found: {filename}", 404
            
        # Verify it's a file and readable
        if not os.path.isfile(file_path):
            print(f"ERROR: Path exists but is not a file: {file_path}")
            return "Not a file", 400
            
        if not os.access(file_path, os.R_OK):
            print(f"ERROR: File exists but is not readable: {file_path}")
            return "Permission denied", 403
            
        print(f"Serving file successfully: {file_path}")
        return send_from_directory(output_folder_abs, filename)
        
    except Exception as e:
        print(f"ERROR serving file {filename}: {str(e)}")
        traceback.print_exc()
        return f"Error serving file: {str(e)}", 500

@app.route('/analysis')
def analysis_page():
    return render_template('analysis.html')

if __name__ == '__main__':
    app.run(debug=True)