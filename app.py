"""Flask microservice for parsing text files."""

import os
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

from parsers import BaseParser
from extractors import TaskExtractor
from utils import FileHandler, get_parser_for_file

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'md', 'sql', 'doc', 'xlsx', 'xls'}

task_extractor = TaskExtractor()
file_handler = FileHandler()


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and \
           BaseParser.get_file_extension(filename) in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload and parse a file.
    
    Expected: multipart/form-data with 'file' field
    Returns: JSON with parsing results
    """
    if 'file' not in request.files:
        return jsonify({
            'error': 'No file provided',
            'status': 'error'
        }), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({
            'error': 'No file selected',
            'status': 'error'
        }), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}',
            'status': 'error'
        }), 400
    
    # Save uploaded file temporarily
    filename = secure_filename(file.filename)
    file_extension = BaseParser.get_file_extension(filename)
    
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as tmp_file:
            file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        # Get appropriate parser
        parser = get_parser_for_file(filename)
        if parser is None:
            return jsonify({
                'error': f'Parser not available for file type: {file_extension}',
                'status': 'error'
            }), 400
        
        # Parse file
        try:
            content = parser.parse(tmp_path)
        except Exception as e:
            # Clean up temporary file on error
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return jsonify({
                'error': f'Error parsing file: {str(e)}',
                'status': 'error'
            }), 500
        
        # Keep tmp_path for problem file saving (will be cleaned up later)
        
        # Extract tasks
        tasks = task_extractor.extract_tasks(content)
        
        # Check for problems
        problem_details = task_extractor.has_problems(tasks, content)
        has_problems_flag = problem_details is not None
        
        # If there are problems, save to problem directory
        problem_file_path = None
        problem_json_path = None
        if has_problems_flag:
            # Log warning to console
            print(f"\n⚠️  WARNING: Problems detected in file '{filename}'")
            print(f"   Reason: {problem_details['problem_reason']}")
            print(f"   Tasks found: {problem_details['tasks_found']}/4")
            if problem_details['empty_tasks']:
                print(f"   Empty tasks: {problem_details['empty_tasks']}")
            if problem_details['detected_markers']:
                print(f"   Detected markers: {', '.join(problem_details['detected_markers'])}")
            print(f"   File saved to problem/ directory\n")
            
            # Save original file to problem directory
            try:
                if os.path.exists(tmp_path):
                    problem_file_path = file_handler.save_problem_file(tmp_path, filename)
                else:
                    # If file was already deleted, create a text file with content
                    problem_file_dir = os.path.join(file_handler.problem_dir, "original_files")
                    os.makedirs(problem_file_dir, exist_ok=True)
                    problem_file_path = os.path.join(problem_file_dir, filename)
                    # If original was not text, save as .txt
                    if file_extension not in ['txt', 'md', 'sql']:
                        problem_file_path = os.path.join(problem_file_dir, 
                                                         os.path.splitext(filename)[0] + '.txt')
                    with open(problem_file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
            except Exception as e:
                print(f"   Error saving problem file: {str(e)}")
            
            # Save problem JSON report
            try:
                problem_json_path = file_handler.save_problem_json(
                    filename, file_extension, content, tasks, problem_details
                )
            except Exception as e:
                print(f"   Error saving problem JSON: {str(e)}")
        
        # Save to JSON (normal directory)
        try:
            json_path = file_handler.save_to_json(filename, file_extension, content, tasks)
        except Exception as e:
            return jsonify({
                'error': f'Error saving JSON: {str(e)}',
                'status': 'error',
                'parsed_content': content,
                'tasks': tasks
            }), 500
        
        # Append to CSV immediately (without buffering)
        try:
            if has_problems_flag:
                # Append to problem CSV
                problem_csv_path = file_handler.append_to_problem_csv(
                    filename, file_extension, content, tasks, problem_details
                )
            else:
                # Append to main CSV
                csv_path = file_handler.append_to_csv(
                    filename, file_extension, content, tasks
                )
        except Exception as e:
            print(f"   Warning: Error writing to CSV: {str(e)}")
        
        response_data = {
            'status': 'success',
            'filename': filename,
            'file_type': file_extension,
            'tasks_count': len(tasks),
            'json_path': json_path,
            'tasks': tasks
        }
        
        # Add problem information if exists
        if has_problems_flag:
            response_data['has_problems'] = True
            response_data['problem_details'] = problem_details
            if problem_file_path:
                response_data['problem_file_path'] = problem_file_path
            if problem_json_path:
                response_data['problem_json_path'] = problem_json_path
            if 'problem_csv_path' in locals():
                response_data['problem_csv_path'] = problem_csv_path
        else:
            if 'csv_path' in locals():
                response_data['csv_path'] = csv_path
        
        # Clean up temporary file
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        
        return jsonify(response_data), 200
    
    except Exception as e:
        # Clean up on error
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        
        return jsonify({
            'error': f'Unexpected error: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'text-parser-microservice'
    }), 200


@app.route('/export/csv', methods=['GET'])
def export_csv():
    """
    Export all processed files to CSV format.
    
    Query parameters:
        detailed: if 'true', creates detailed CSV with separate rows for each task
    """
    try:
        import json
        import csv
        from io import StringIO
        
        detailed = request.args.get('detailed', 'false').lower() == 'true'
        data_loaded_dir = file_handler.output_dir
        
        if not os.path.exists(data_loaded_dir):
            return jsonify({
                'error': 'No processed files found',
                'status': 'error'
            }), 404
        
        # Load JSON files
        json_data = []
        for filename in os.listdir(data_loaded_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(data_loaded_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        json_data.append(data)
                except Exception:
                    continue
        
        if not json_data:
            return jsonify({
                'error': 'No processed files found',
                'status': 'error'
            }), 404
        
        # Create CSV content
        output = StringIO()
        
        if detailed:
            # Detailed format: one row per task
            fieldnames = ['filename', 'file_type', 'parsed_at', 'task_number', 'task_content']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for item in json_data:
                filename = item.get('filename', '')
                file_type = item.get('file_type', '')
                parsed_at = item.get('parsed_at', '')
                tasks = item.get('tasks', [])
                
                for task in tasks:
                    task_num = task.get('task_number', '')
                    task_content = task.get('content', '').replace('\n', ' ').replace('\r', ' ')
                    task_content = ' '.join(task_content.split())
                    if len(task_content) > 5000:
                        task_content = task_content[:5000] + '...'
                    
                    writer.writerow({
                        'filename': filename,
                        'file_type': file_type,
                        'parsed_at': parsed_at,
                        'task_number': task_num,
                        'task_content': task_content
                    })
        else:
            # Standard format: one row per file
            fieldnames = ['full_filename', 'filename', 'type', 'task_1', 'task_2', 'task_3', 'task_4', 'content']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            def clean_text(text, max_length=None):
                if not text:
                    return ''
                cleaned = text.replace('\n', ' ').replace('\r', ' ')
                cleaned = ' '.join(cleaned.split())
                if max_length and len(cleaned) > max_length:
                    cleaned = cleaned[:max_length] + '...'
                return cleaned
            
            for item in json_data:
                full_filename = item.get('filename', '')
                # Extract filename without extension
                filename = os.path.splitext(full_filename)[0] if '.' in full_filename else full_filename
                file_type = item.get('file_type', '')
                content = item.get('content', '')
                tasks = item.get('tasks', [])
                
                task_1 = tasks[0].get('content', '') if len(tasks) > 0 else ''
                task_2 = tasks[1].get('content', '') if len(tasks) > 1 else ''
                task_3 = tasks[2].get('content', '') if len(tasks) > 2 else ''
                task_4 = tasks[3].get('content', '') if len(tasks) > 3 else ''
                
                writer.writerow({
                    'full_filename': full_filename,
                    'filename': filename,
                    'type': file_type,
                    'task_1': clean_text(task_1),
                    'task_2': clean_text(task_2),
                    'task_3': clean_text(task_3),
                    'task_4': clean_text(task_4),
                    'content': clean_text(content)
                })
        
        csv_content = output.getvalue()
        output.close()
        
        # Return CSV as response
        from flask import Response
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=exported_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        )
    
    except Exception as e:
        return jsonify({
            'error': f'Error exporting CSV: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/', methods=['GET'])
def index():
    """Root endpoint with API information."""
    return jsonify({
        'service': 'Text Parser Microservice',
        'version': '1.0.0',
        'endpoints': {
            'POST /upload': 'Upload and parse a file',
            'GET /health': 'Health check',
            'GET /export/csv': 'Export all processed files to CSV'
        },
        'supported_formats': list(ALLOWED_EXTENSIONS)
    }), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
