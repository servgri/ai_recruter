"""Parser service Blueprint."""

from flask import Blueprint, request, jsonify
from utils import get_parser_for_file
from utils.database import Database
from utils.file_utils import calculate_file_hash, save_file_with_hash, calculate_content_hash
from utils.logger import log_action
from services.processing_service import ProcessingService
from parsers import BaseParser
import os
import tempfile

parser_bp = Blueprint('parser', __name__, url_prefix='/parser')

db = Database()
processing_service = None  # Will be initialized with socketio


@parser_bp.route('/upload', methods=['POST'])
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
    
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'md', 'sql', 'doc', 'xlsx', 'xls'}
    if not ('.' in file.filename and 
            BaseParser.get_file_extension(file.filename) in ALLOWED_EXTENSIONS):
        return jsonify({
            'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}',
            'status': 'error'
        }), 400
    
    filename = file.filename
    file_extension = BaseParser.get_file_extension(filename)
    
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as tmp_file:
            file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        # Calculate file hash
        try:
            file_hash = calculate_file_hash(tmp_path)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return jsonify({
                'error': f'Error calculating file hash: {str(e)}',
                'status': 'error'
            }), 500
        
        # Check for duplicate (100% match)
        existing_doc = db.find_document_by_hash(file_hash)
        if existing_doc:
            # Duplicate found - delete uploaded file and return error
            existing_doc_id = existing_doc.get('id')
            existing_filename = existing_doc.get('full_filename', 'неизвестный файл')
            
            log_action("file_upload", doc_id=existing_doc_id, status="error",
                      details={"filename": filename, "file_type": file_extension, 
                              "file_hash": file_hash, "duplicate": True,
                              "error": "Файл уже существует в базе данных",
                              "existing_filename": existing_filename})
            
            # Delete temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            
            return jsonify({
                'status': 'error',
                'error': f'Файл уже загружен ранее: {existing_filename}',
                'duplicate': True,
                'existing_doc_id': existing_doc_id,
                'existing_filename': existing_filename
            }), 400
        
        # Get appropriate parser
        parser = get_parser_for_file(filename)
        if parser is None:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return jsonify({
                'error': f'Parser not available for file type: {file_extension}',
                'status': 'error'
            }), 400
        
        # Parse file
        try:
            content = parser.parse(tmp_path)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return jsonify({
                'error': f'Error parsing file: {str(e)}',
                'status': 'error'
            }), 500
        
        # Save file to loaded/ directory with hash-based name
        try:
            with open(tmp_path, 'rb') as f:
                file_content = f.read()
            saved_path, saved_hash = save_file_with_hash(
                file_content, file_extension, filename, loaded_dir='loaded'
            )
        except Exception as e:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return jsonify({
                'error': f'Error saving file to loaded/: {str(e)}',
                'status': 'error'
            }), 500
        
        # Delete temporary file now that we have saved copy in loaded/
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        
        # Save to database (initial save with basic info and hash)
        doc_id = db.save_document(
            filename, file_extension, content, [], 
            processing_status='pending', file_hash=saved_hash
        )
        
        # Log file upload
        log_action("file_upload", doc_id=doc_id, 
                  details={"filename": filename, "file_type": file_extension, 
                          "file_hash": saved_hash, "tasks_count": 0}, status="success")
        
        # Start async processing using file from loaded/ directory
        if processing_service:
            processing_service.process_file_async(doc_id, saved_path, filename, file_extension)
        else:
            # Fallback: process synchronously if processing_service not initialized
            from services.processing_service import ProcessingService
            ps = ProcessingService()
            ps.process_file_async(doc_id, saved_path, filename, file_extension)
        
        return jsonify({
            'status': 'success',
            'doc_id': doc_id,
            'filename': filename,
            'file_type': file_extension,
            'message': 'File uploaded, processing started',
            'duplicate': False
        }), 200
    
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        
        # Log upload error
        log_action("file_upload", status="error",
                  details={"filename": filename if 'filename' in locals() else 'unknown',
                          "file_type": file_extension if 'file_extension' in locals() else 'unknown',
                          "error": str(e)})
        
        return jsonify({
            'error': f'Unexpected error: {str(e)}',
            'status': 'error'
        }), 500
