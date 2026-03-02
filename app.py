"""Flask microservice for parsing text files."""

import os
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO

from parsers import BaseParser
from extractors import TaskExtractor
from utils import get_parser_for_file
from utils.database import Database
from utils.logger import log_action

# Import Blueprint modules
from services.parser_service import parser_bp
from services.task_cleaner_service import cleaner_bp
from services.embedding_service import embedding_bp
from services.analysis_service import analysis_bp
from services.websocket_service import init_websocket
from services.processing_service import ProcessingService

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize database
db = Database()

# Initialize processing service with socketio
processing_service = ProcessingService(socketio=socketio)
# Set processing service in parser_service
from services import parser_service
parser_service.processing_service = processing_service

# Initialize WebSocket handlers
init_websocket(app, socketio)

# Register Blueprint modules
app.register_blueprint(parser_bp)
app.register_blueprint(cleaner_bp)
app.register_blueprint(embedding_bp)
app.register_blueprint(analysis_bp)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'md', 'sql', 'doc', 'xlsx', 'xls'}

task_extractor = TaskExtractor()

# Jinja2 filter for converting text tables (with | separators) to HTML tables
@app.template_filter('format_table')
def format_table_filter(text):
    """
    Convert text with pipe-separated values to HTML table.
    Detects tables by lines containing '|' separator.
    """
    if not text:
        return text
    
    from markupsafe import Markup, escape
    
    lines = text.split('\n')
    if not lines:
        return text
    
    # Detect if text contains table-like structure
    # A table should have at least 2 lines with '|' separator
    result_parts = []
    in_table = False
    current_table = []
    current_text = []
    
    for line in lines:
        stripped = line.strip()
        # Check if line looks like a table row (contains | and has multiple cells)
        if '|' in stripped and stripped.count('|') >= 1:
            # Check if it's a separator line (like "---|----|----")
            is_separator = all(c in '-|: ' for c in stripped.replace('|', ''))
            if not is_separator:
                if not in_table:
                    # Start new table - flush any accumulated text
                    if current_text:
                        result_parts.append('\n'.join(current_text))
                        current_text = []
                    in_table = True
                    current_table = []
                current_table.append(line)
            else:
                # Separator line - keep it but don't process as table row
                if in_table:
                    current_table.append(line)
        else:
            if in_table:
                # End of table - process accumulated table
                if current_table:
                    html_table = _convert_table_to_html(current_table)
                    result_parts.append(Markup(html_table))
                    current_table = []
                in_table = False
            current_text.append(line)
    
    # Process last table if exists
    if in_table and current_table:
        html_table = _convert_table_to_html(current_table)
        result_parts.append(Markup(html_table))
    
    # Add remaining text
    if current_text:
        result_parts.append('\n'.join(current_text))
    
    # Combine all parts
    if len(result_parts) == 1:
        part = result_parts[0]
        if isinstance(part, Markup):
            # Single table
            return part
        else:
            # Single text block - return as is (will be wrapped by template)
            return part
    else:
        # Mix of text and tables - combine them
        combined = []
        for part in result_parts:
            if isinstance(part, Markup):
                combined.append(str(part))
            else:
                # Text parts - escape and keep as is
                if part.strip():
                    combined.append(escape(part))
        return Markup('\n'.join(combined))

def _convert_table_to_html(table_lines):
    """Convert table lines (with | separators) to HTML table."""
    if not table_lines:
        return ''
    
    from markupsafe import escape
    
    rows = []
    for line in table_lines:
        stripped = line.strip()
        # Skip separator lines
        if all(c in '-|: ' for c in stripped.replace('|', '')):
            continue
        # Split by | and clean cells
        cells = [cell.strip() for cell in stripped.split('|')]
        # Remove empty cells at start/end if they exist
        while cells and not cells[0]:
            cells.pop(0)
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            rows.append(cells)
    
    if not rows:
        return ''
    
    # Determine if first row is header (check if it looks like header)
    # Simple heuristic: if first row has text that looks like column names
    header_row = None
    data_rows = rows
    
    # Check if first row looks like a header (contains words like "название", "тип", "поле", etc.)
    if rows:
        first_row_text = ' '.join(rows[0]).lower()
        header_keywords = ['название', 'тип', 'поле', 'текущий', 'рекомендуемый', 'обоснование', 
                          'name', 'type', 'field', 'current', 'recommended', 'justification']
        if any(keyword in first_row_text for keyword in header_keywords):
            header_row = rows[0]
            data_rows = rows[1:]
    
    # Build HTML table
    html = ['<table class="answer-table">']
    
    # Add header if detected
    if header_row:
        html.append('<thead><tr>')
        for cell in header_row:
            html.append(f'<th>{escape(cell)}</th>')
        html.append('</tr></thead>')
    
    # Add body
    html.append('<tbody>')
    for row in data_rows:
        html.append('<tr>')
        for cell in row:
            html.append(f'<td>{escape(cell)}</td>')
        html.append('</tr>')
    html.append('</tbody>')
    
    html.append('</table>')
    return ''.join(html)

# Jinja2 filter for inserting images into text at marker positions
@app.template_filter('insert_images')
def insert_images_filter(text, images):
    """
    Insert images into text at [Изображение] marker positions in order.
    Returns list of dictionaries with 'type' and 'content' keys.
    """
    if not text:
        text = ''
    if not images:
        images = []
    
    from markupsafe import Markup, escape
    
    # Sort images by position
    sorted_images = sorted([img for img in images if img.get('position') is not None], 
                          key=lambda x: x.get('position', 0))
    
    # Find all image marker positions in text
    import re
    marker_pattern = r'\[Изображение[^\]]*\]'
    markers = list(re.finditer(marker_pattern, text))
    
    if not markers:
        # No markers - return text and images separately
        result = []
        if text.strip():
            result.append({'type': 'text', 'content': text})
        for img in sorted_images:
            result.append({'type': 'image', 'content': img})
        return result
    
    # Build result: text parts and images in order
    result = []
    current_pos = 0
    image_idx = 0
    
    for marker_match in markers:
        marker_start = marker_match.start()
        marker_end = marker_match.end()
        
        # Add text before marker
        if marker_start > current_pos:
            text_before = text[current_pos:marker_start].strip()
            if text_before:
                result.append({'type': 'text', 'content': text_before})
        
        # Add image if available
        if image_idx < len(sorted_images):
            result.append({'type': 'image', 'content': sorted_images[image_idx]})
            image_idx += 1
        
        current_pos = marker_end
    
    # Add remaining text after last marker
    if current_pos < len(text):
        text_after = text[current_pos:].strip()
        if text_after:
            result.append({'type': 'text', 'content': text_after})
    
    # Add any remaining images
    while image_idx < len(sorted_images):
        result.append({'type': 'image', 'content': sorted_images[image_idx]})
        image_idx += 1
    
    return result


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
        
        # Extract tasks
        tasks = task_extractor.extract_tasks(content)
        
        # Check for problems (log only, no file/CSV writes)
        problem_details = task_extractor.has_problems(tasks, content)
        has_problems_flag = problem_details is not None
        if has_problems_flag:
            print(f"\n⚠️  WARNING: Problems detected in file '{filename}'")
            print(f"   Reason: {problem_details['problem_reason']}")
            print(f"   Tasks found: {problem_details['tasks_found']}/4")
            if problem_details['empty_tasks']:
                print(f"   Empty tasks: {problem_details['empty_tasks']}")
            if problem_details['detected_markers']:
                print(f"   Detected markers: {', '.join(problem_details['detected_markers'])}\n")
        
        response_data = {
            'status': 'success',
            'filename': filename,
            'file_type': file_extension,
            'tasks_count': len(tasks),
            'tasks': tasks
        }
        if has_problems_flag:
            response_data['has_problems'] = True
            response_data['problem_details'] = problem_details
        
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
        
        # Export from database instead of JSON files
        documents = db.get_all_documents()
        
        if not documents:
            return jsonify({
                'error': 'No processed files found',
                'status': 'error'
            }), 404
        
        # Convert database documents to JSON-like format
        json_data = []
        for doc in documents:
            # Extract tasks from database
            tasks = []
            for task_num in range(1, 5):
                task_content = doc.get(f'task_{task_num}', '')
                if task_content:
                    tasks.append({
                        'task_number': task_num,
                        'content': task_content
                    })
            
            json_data.append({
                'filename': doc.get('full_filename', ''),
                'file_type': doc.get('type', ''),
                'content': doc.get('content', ''),
                'tasks': tasks,
                'parsed_at': doc.get('created_at', '')
            })
        
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
    """Main page - redirect to upload."""
    return redirect(url_for('upload_page'))


@app.route('/upload', methods=['GET'])
def upload_page():
    """Upload page."""
    return render_template('upload.html')


@app.route('/report', methods=['GET'])
def report_page():
    """Report page."""
    return render_template('report.html')


@app.route('/api-docs', methods=['GET'])
def api_docs_page():
    """API documentation page."""
    return render_template('api_docs.html')


@app.route('/api/upload', methods=['POST'])
def api_upload():
    """API endpoint for file upload (used by frontend)."""
    # Import and call the function directly
    from services.parser_service import upload_file
    return upload_file()


@app.route('/api/documents', methods=['GET'])
def api_documents():
    """Get all documents from database with all fields."""
    try:
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', type=int)
        
        documents = db.get_all_documents(limit=limit, offset=offset)
        
        # Convert all documents to dict format (already done by get_all_documents)
        # All fields are already included from database
        
        return jsonify({
            'status': 'success',
            'documents': documents,
            'count': len(documents)
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error retrieving documents: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/statistics', methods=['GET'])
def api_statistics():
    """Get statistics data for charts."""
    try:
        documents = db.get_all_documents()
        
        # Pie chart: unread (not approved), approved, blocked
        unread_count = 0
        approved_count = 0
        blocked_count = 0
        
        # Score distribution (bar chart) - ranges: 0-2, 2-4, 4-6, 6-8, 8-10
        score_ranges = {
            '0-2': 0,
            '2-4': 0,
            '4-6': 0,
            '6-8': 0,
            '8-10': 0
        }
        
        # Timeline (line chart) - documents per day
        timeline_data = {}
        
        for doc in documents:
            # Blocked count (processing_status = 'error')
            if doc.get('processing_status') == 'error':
                blocked_count += 1
            # Approved count
            elif doc.get('approved', 0):
                approved_count += 1
            # Unread count (not approved)
            else:
                unread_count += 1
            
            # Score distribution
            avg_score = doc.get('average_score_tasks_1_3')
            if avg_score is not None:
                score = float(avg_score)
                if score < 2:
                    score_ranges['0-2'] += 1
                elif score < 4:
                    score_ranges['2-4'] += 1
                elif score < 6:
                    score_ranges['4-6'] += 1
                elif score < 8:
                    score_ranges['6-8'] += 1
                else:
                    score_ranges['8-10'] += 1
            
            # Timeline
            created_at = doc.get('created_at')
            if created_at:
                try:
                    from datetime import datetime
                    date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = date_obj.strftime('%Y-%m-%d')
                    timeline_data[date_str] = timeline_data.get(date_str, 0) + 1
                except:
                    pass
        
        # Sort timeline by date
        sorted_timeline = sorted(timeline_data.items())
        timeline_labels = [item[0] for item in sorted_timeline]
        timeline_values = [item[1] for item in sorted_timeline]
        
        return jsonify({
            'status': 'success',
            'pie_chart': {
                'unread': unread_count,
                'approved': approved_count,
                'blocked': blocked_count
            },
            'score_distribution': score_ranges,
            'timeline': {
                'labels': timeline_labels,
                'values': timeline_values
            }
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error retrieving statistics: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/report/<int:doc_id>', methods=['GET'])
def api_report(doc_id: int):
    """Get HTML report for a document."""
    try:
        document = db.get_document(doc_id)
        if not document:
            return jsonify({
                'error': f'Document with ID {doc_id} not found',
                'status': 'error'
            }), 404
        
        # Parse JSON fields
        import json
        similarity_ref = {}
        similarity_existing = {}
        cheating_metrics = {}
        
        if document.get('similarity_with_reference'):
            try:
                similarity_ref = json.loads(document['similarity_with_reference']) if isinstance(document['similarity_with_reference'], str) else document['similarity_with_reference']
            except:
                pass
        
        if document.get('similarity_with_existing'):
            try:
                similarity_existing = json.loads(document['similarity_with_existing']) if isinstance(document['similarity_with_existing'], str) else document['similarity_with_existing']
            except:
                pass
        
        if document.get('cheating_score'):
            try:
                cheating_metrics = json.loads(document['cheating_score']) if isinstance(document['cheating_score'], str) else document['cheating_score']
            except:
                pass
        
        # Skip LLM comment generation for now to avoid blocking - generate asynchronously
        # Comments will be generated during file processing in processing_service.py
        # The report will display comments if they exist, otherwise show empty comment fields
        
        # Calculate has_parsing_problems for template
        has_parsing_problems_for_template = False
        for task_num in range(1, 5):
            task_key = f'task_{task_num}'
            task_text = document.get(task_key, '')
            if not task_text or not task_text.strip():
                has_parsing_problems_for_template = True
                break
        
        # Parse task images JSON
        task_images = {}
        for task_num in range(1, 5):
            task_images_key = f'task_{task_num}_images'
            if document.get(task_images_key):
                try:
                    task_images[task_num] = json.loads(document[task_images_key]) if isinstance(document[task_images_key], str) else document[task_images_key]
                except Exception as e:
                    task_images[task_num] = []
            else:
                task_images[task_num] = []
        
        # Calculate has_any_images for template
        has_any_images_for_template = any(len(images) > 0 for images in task_images.values())
        
        # Load task prompts from task_data.csv
        task_prompts = {}
        try:
            import csv
            csv_path = None
            possible_paths = [
                os.path.join(os.getcwd(), 'task_data.csv'),
                'task_data.csv',
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    csv_path = path
                    break
            
            if csv_path:
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    row = next(reader, None)
                    if row:
                        for task_num in range(1, 5):
                            task_key = f'task_{task_num}'
                            if task_key in row:
                                task_prompts[task_num] = row[task_key] or ''
        except Exception as e:
            print(f"Error loading task prompts: {e}")
        
        # Get most similar work text if similarity > 70%
        similar_work_data = None
        if similarity_existing and similarity_existing.get('top_similar') and len(similarity_existing['top_similar']) > 0:
            top_similar = similarity_existing['top_similar'][0]
            if top_similar.get('overall_similarity', 0) > 0.7:
                similar_doc_id = top_similar.get('doc_id')
                if similar_doc_id:
                    similar_document = db.get_document(similar_doc_id)
                    if similar_document:
                        # Collect all task texts
                        similar_work_texts = {}
                        for task_num in range(1, 5):
                            task_key = f'task_{task_num}'
                            task_text = similar_document.get(task_key, '')
                            if task_text and task_text.strip():
                                similar_work_texts[task_num] = task_text
                        
                        similar_work_data = {
                            'doc_id': similar_doc_id,
                            'filename': top_similar.get('filename', 'Файл'),
                            'similarity': top_similar.get('overall_similarity', 0),
                            'task_texts': similar_work_texts
                        }

        # Parse eval_v6_results and build task_criteria (merge criteria_details with criteria_overrides)
        eval_v6_results = None
        raw_eval = document.get('eval_v6_results')
        if raw_eval and isinstance(raw_eval, str) and raw_eval.strip():
            try:
                eval_v6_results = json.loads(raw_eval)
            except json.JSONDecodeError:
                pass
        elif isinstance(raw_eval, dict):
            eval_v6_results = raw_eval

        criteria_overrides = {}
        raw_overrides = document.get('criteria_overrides')
        if raw_overrides and isinstance(raw_overrides, str) and raw_overrides.strip():
            try:
                criteria_overrides = json.loads(raw_overrides)
            except json.JSONDecodeError:
                pass
        elif isinstance(raw_overrides, dict):
            criteria_overrides = raw_overrides

        task_criteria = {}
        eval_v6_similarity = {}  # task_num -> chosen cosine (0..1)
        if eval_v6_results and isinstance(eval_v6_results.get('results'), list):
            for q_row in eval_v6_results['results']:
                qid_str = str(q_row.get('Номер вопроса', ''))
                if not qid_str.isdigit():
                    continue
                task_num = int(qid_str)
                chosen = q_row.get('Эталон выбран')
                cos_hr = q_row.get('Cosine HR')
                cos_ai = q_row.get('Cosine AI')
                if chosen == 'hr' and cos_hr is not None:
                    eval_v6_similarity[task_num] = cos_hr
                elif chosen == 'ai' and cos_ai is not None:
                    eval_v6_similarity[task_num] = cos_ai
                criteria_pack = q_row.get('Criteria pack') or {}
                details = criteria_pack.get('criteria_details') or []
                base_list = [{'name': c.get('name', ''), 'passed': bool(c.get('passed'))} for c in details]
                overrides_list = criteria_overrides.get(qid_str)
                if isinstance(overrides_list, list) and overrides_list:
                    override_by_name = {c.get('name', ''): c.get('passed', False) for c in overrides_list if c.get('name')}
                    for item in base_list:
                        if item['name'] in override_by_name:
                            item['passed'] = override_by_name[item['name']]
                task_criteria[task_num] = base_list
        for task_num in range(1, 5):
            if task_num not in task_criteria:
                task_criteria[task_num] = []

        return render_template(
            'document_report.html',
            document=document,
            similarity_ref=similarity_ref,
            similarity_existing=similarity_existing,
            cheating_metrics=cheating_metrics,
            task_images=task_images,
            task_prompts=task_prompts,
            similar_work_data=similar_work_data,
            has_any_images=has_any_images_for_template,
            has_parsing_problems=has_parsing_problems_for_template,
            eval_v6_results=eval_v6_results,
            task_criteria=task_criteria,
            eval_v6_similarity=eval_v6_similarity
        ), 200
    except Exception as e:
        return jsonify({
            'error': f'Error generating report: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/report/<int:doc_id>/save-grades', methods=['POST'])
def api_save_grades(doc_id: int):
    """Save grades and comments for a task."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'No data provided',
                'status': 'error'
            }), 400
        
        task_num = data.get('task_num')
        if not task_num or task_num not in [1, 2, 3, 4]:
            return jsonify({
                'error': 'Invalid task number',
                'status': 'error'
            }), 400
        
        # Prepare update data
        update_data = {}
        
        if task_num < 4:
            # Tasks 1-3: score (0-10)
            if 'score' in data:
                score = data.get('score')
                if score:
                    try:
                        score_val = float(score)
                        if not (0 <= score_val <= 10):
                            return jsonify({
                                'error': 'Score must be between 0 and 10',
                                'status': 'error'
                            }), 400
                        update_data[f'task_{task_num}_score'] = score_val
                    except:
                        return jsonify({
                            'error': 'Invalid score format',
                            'status': 'error'
                        }), 400
                else:
                    update_data[f'task_{task_num}_score'] = None
        else:
            # Task 4: logic_score and originality_score (0-100%)
            if 'logic_score' in data:
                logic_score = data.get('logic_score')
                if logic_score:
                    try:
                        logic_val = float(logic_score)
                        if not (0 <= logic_val <= 100):
                            return jsonify({
                                'error': 'Logic score must be between 0 and 100',
                                'status': 'error'
                            }), 400
                        update_data['task_4_logic_score'] = logic_val
                    except:
                        return jsonify({
                            'error': 'Invalid logic score format',
                            'status': 'error'
                        }), 400
                else:
                    update_data['task_4_logic_score'] = None
            
            if 'originality_score' in data:
                originality_score = data.get('originality_score')
                if originality_score:
                    try:
                        orig_val = float(originality_score)
                        if not (0 <= orig_val <= 100):
                            return jsonify({
                                'error': 'Originality score must be between 0 and 100',
                                'status': 'error'
                            }), 400
                        update_data['task_4_originality_score'] = orig_val
                    except:
                        return jsonify({
                            'error': 'Invalid originality score format',
                            'status': 'error'
                        }), 400
                else:
                    update_data['task_4_originality_score'] = None
        
        if 'comment_student' in data:
            update_data[f'task_{task_num}_comment_student'] = data.get('comment_student', '')
        
        # Recalculate average for tasks 1-3 if any score was updated
        if task_num < 4 and 'score' in data:
            from services.scoring_service import get_scoring_service
            scoring_service = get_scoring_service()
            doc = db.get_document(doc_id)
            if doc:
                avg_score = scoring_service.calculate_average_score_tasks_1_3(
                    doc.get('task_1_score') if task_num != 1 else update_data.get('task_1_score'),
                    doc.get('task_2_score') if task_num != 2 else update_data.get('task_2_score'),
                    doc.get('task_3_score') if task_num != 3 else update_data.get('task_3_score')
                )
                if avg_score is not None:
                    update_data['average_score_tasks_1_3'] = avg_score
        
        # Update document
        if update_data:
            db.update_document(doc_id, **update_data)
            document = db.get_document(doc_id)
            log_action("save_grades", doc_id=doc_id, 
                      details={"task_num": task_num, "filename": document.get('full_filename', '') if document else '', **update_data})
        
        return jsonify({
            'status': 'success',
            'message': 'Grades saved successfully'
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error saving grades: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/documents/<int:doc_id>/approve', methods=['POST'])
def api_approve_document(doc_id: int):
    """Approve a document. Only approve if overall_impression exists."""
    try:
        document = db.get_document(doc_id)
        if not document:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404
        
        # Check if overall_impression exists and is not empty
        overall_impression = document.get('overall_impression', '')
        if not overall_impression or not overall_impression.strip():
            log_action("approve", doc_id=doc_id, status="error", 
                      details={"error": "overall_impression_required", "filename": document.get('full_filename', '')})
            return jsonify({
                'error': 'Невозможно одобрить: требуется комментарий общего впечатления',
                'status': 'error'
            }), 400
        
        success = db.approve_document(doc_id)
        if success:
            log_action("approve", doc_id=doc_id, details={"filename": document.get('full_filename', '')})
            return jsonify({
                'status': 'success',
                'message': 'Document approved'
            }), 200
        else:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404
    except Exception as e:
        return jsonify({
            'error': f'Error approving document: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/report/<int:doc_id>/save-overall-impression', methods=['POST'])
def api_save_overall_impression(doc_id: int):
    """Save overall impression comment."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'No data provided',
                'status': 'error'
            }), 400
        
        overall_impression = data.get('overall_impression', '')
        
        success = db.update_document(doc_id, overall_impression=overall_impression)
        if success:
            document = db.get_document(doc_id)
            log_action("save_overall_impression", doc_id=doc_id, 
                      details={"filename": document.get('full_filename', '') if document else '', 
                              "length": len(overall_impression)})
            return jsonify({
                'status': 'success',
                'message': 'Overall impression saved'
            }), 200
        else:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404
    except Exception as e:
        return jsonify({
            'error': f'Error saving overall impression: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/report/<int:doc_id>/save-criteria', methods=['POST'])
def api_save_criteria(doc_id: int):
    """Save criteria overrides for a task (which criteria are marked passed/failed)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided', 'status': 'error'}), 400
        task_num = data.get('task_num')
        if task_num not in (1, 2, 3, 4):
            return jsonify({'error': 'Invalid task number', 'status': 'error'}), 400
        criteria = data.get('criteria')
        if not isinstance(criteria, list):
            return jsonify({'error': 'criteria must be a list', 'status': 'error'}), 400
        document = db.get_document(doc_id)
        if not document:
            return jsonify({'error': 'Document not found', 'status': 'error'}), 404
        raw = document.get('criteria_overrides')
        overrides = {}
        if raw and isinstance(raw, str) and raw.strip():
            try:
                overrides = json.loads(raw)
            except json.JSONDecodeError:
                pass
        elif isinstance(raw, dict):
            overrides = raw
        overrides[str(task_num)] = [{'name': c.get('name', ''), 'passed': bool(c.get('passed'))} for c in criteria if c.get('name')]
        success = db.update_document(doc_id, criteria_overrides=json.dumps(overrides, ensure_ascii=False))
        if success:
            return jsonify({'status': 'success', 'message': 'Criteria saved'}), 200
        return jsonify({'error': 'Update failed', 'status': 'error'}), 500
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500


@app.route('/api/documents/<int:doc_id>/unapprove', methods=['POST'])
def api_unapprove_document(doc_id: int):
    """Unapprove a document."""
    try:
        success = db.update_document(doc_id, approved=0)
        if success:
            document = db.get_document(doc_id)
            log_action("unapprove", doc_id=doc_id, details={"filename": document.get('full_filename', '') if document else ''})
            return jsonify({
                'status': 'success',
                'message': 'Document unapproved'
            }), 200
        else:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404
    except Exception as e:
        return jsonify({
            'error': f'Error unapproving document: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/documents/<int:doc_id>/block', methods=['POST'])
def api_block_document(doc_id: int):
    """Block a document."""
    try:
        success = db.block_document(doc_id)
        if success:
            document = db.get_document(doc_id)
            log_action("block", doc_id=doc_id, details={"filename": document.get('full_filename', '') if document else ''})
            return jsonify({
                'status': 'success',
                'message': 'Document blocked'
            }), 200
        else:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404
    except Exception as e:
        return jsonify({
            'error': f'Error blocking document: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/documents/<int:doc_id>/unblock', methods=['POST'])
def api_unblock_document(doc_id: int):
    """Unblock a document."""
    try:
        success = db.unblock_document(doc_id)
        if success:
            document = db.get_document(doc_id)
            log_action("unblock", doc_id=doc_id, details={"filename": document.get('full_filename', '') if document else ''})
            return jsonify({
                'status': 'success',
                'message': 'Document unblocked'
            }), 200
        else:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404
    except Exception as e:
        return jsonify({
            'error': f'Error unblocking document: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/documents/<int:doc_id>/delete', methods=['DELETE'])
def api_delete_document(doc_id: int):
    """Delete a document."""
    try:
        document = db.get_document(doc_id)
        filename = document.get('full_filename', '') if document else ''
        success = db.delete_document(doc_id)
        if success:
            log_action("delete", doc_id=doc_id, details={"filename": filename})
            return jsonify({
                'status': 'success',
                'message': 'Document deleted'
            }), 200
        else:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404
    except Exception as e:
        return jsonify({
            'error': f'Error deleting document: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/documents/batch-approve', methods=['POST'])
def api_batch_approve_documents():
    """Approve multiple documents."""
    try:
        data = request.get_json()
        if not data or 'doc_ids' not in data:
            return jsonify({
                'error': 'No document IDs provided',
                'status': 'error'
            }), 400
        
        doc_ids = data.get('doc_ids', [])
        if not isinstance(doc_ids, list) or len(doc_ids) == 0:
            return jsonify({
                'error': 'Invalid document IDs',
                'status': 'error'
            }), 400
        
        count = db.batch_approve_documents(doc_ids)
        log_action("batch_approve", details={"count": count, "doc_ids": doc_ids})
        return jsonify({
            'status': 'success',
            'count': count,
            'message': f'Approved {count} document(s)'
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error batch approving documents: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/documents/batch-block', methods=['POST'])
def api_batch_block_documents():
    """Block multiple documents."""
    try:
        data = request.get_json()
        if not data or 'doc_ids' not in data:
            return jsonify({
                'error': 'No document IDs provided',
                'status': 'error'
            }), 400
        
        doc_ids = data.get('doc_ids', [])
        if not isinstance(doc_ids, list) or len(doc_ids) == 0:
            return jsonify({
                'error': 'Invalid document IDs',
                'status': 'error'
            }), 400
        
        count = db.batch_block_documents(doc_ids)
        log_action("batch_block", details={"count": count, "doc_ids": doc_ids})
        return jsonify({
            'status': 'success',
            'count': count,
            'message': f'Blocked {count} document(s)'
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error batch blocking documents: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/documents/batch-unblock', methods=['POST'])
def api_batch_unblock_documents():
    """Unblock multiple documents."""
    try:
        data = request.get_json()
        if not data or 'doc_ids' not in data:
            return jsonify({
                'error': 'No document IDs provided',
                'status': 'error'
            }), 400
        
        doc_ids = data.get('doc_ids', [])
        if not isinstance(doc_ids, list) or len(doc_ids) == 0:
            return jsonify({
                'error': 'Invalid document IDs',
                'status': 'error'
            }), 400
        
        count = db.batch_unblock_documents(doc_ids)
        log_action("batch_unblock", details={"count": count, "doc_ids": doc_ids})
        return jsonify({
            'status': 'success',
            'count': count,
            'message': f'Unblocked {count} document(s)'
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error batch unblocking documents: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/documents/batch-delete', methods=['POST'])
def api_batch_delete_documents():
    """Delete multiple documents."""
    try:
        data = request.get_json()
        if not data or 'doc_ids' not in data:
            return jsonify({
                'error': 'No document IDs provided',
                'status': 'error'
            }), 400
        
        doc_ids = data.get('doc_ids', [])
        if not isinstance(doc_ids, list) or len(doc_ids) == 0:
            return jsonify({
                'error': 'Invalid document IDs',
                'status': 'error'
            }), 400
        
        count = db.batch_delete_documents(doc_ids)
        log_action("batch_delete", details={"count": count, "doc_ids": doc_ids})
        return jsonify({
            'status': 'success',
            'count': count,
            'message': f'Deleted {count} document(s)'
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error batch deleting documents: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/documents/<int:doc_id>/download', methods=['GET'])
def api_download_document(doc_id: int):
    """Download original file."""
    try:
        import os
        from flask import send_file
        
        document = db.get_document(doc_id)
        if not document:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404
        
        file_hash = document.get('file_hash')
        file_type = document.get('type', '')
        
        if not file_hash or not file_type:
            return jsonify({
                'error': 'File information not available',
                'status': 'error'
            }), 404
        
        # Find file in loaded/ directory
        # Files are saved with 5-character hash, but database stores full hash
        short_hash = file_hash[:5]
        filename = f"{short_hash}.{file_type}"
        file_path = os.path.join("loaded", filename)
        
        # If file doesn't exist with 5-char hash, try with full hash (backward compatibility)
        if not os.path.exists(file_path):
            # Try with full hash (for old files)
            filename_full = f"{file_hash}.{file_type}"
            file_path_full = os.path.join("loaded", filename_full)
            if os.path.exists(file_path_full):
                file_path = file_path_full
            else:
                # Try with counter suffixes (in case of hash collisions)
                from utils.file_utils import calculate_file_hash
                counter = 1
                found = False
                while counter <= 100:  # Limit search to prevent infinite loop
                    filename_collision = f"{short_hash}_{counter}.{file_type}"
                    file_path_collision = os.path.join("loaded", filename_collision)
                    if os.path.exists(file_path_collision):
                        # Verify it's the same file by comparing full hash
                        existing_hash = calculate_file_hash(file_path_collision)
                        if existing_hash == file_hash:
                            file_path = file_path_collision
                            found = True
                            break
                    counter += 1
                
                if not found:
                    return jsonify({
                        'error': 'File not found on disk',
                        'status': 'error'
                    }), 404
        
        original_filename = document.get('full_filename', filename)
        return send_file(file_path, as_attachment=True, download_name=original_filename)
    except Exception as e:
        return jsonify({
            'error': f'Error downloading file: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/report/<int:doc_id>/export-pdf', methods=['GET'])
def api_export_report_pdf(doc_id: int):
    """Export report to PDF."""
    try:
        from weasyprint import HTML, CSS
        from io import BytesIO
        
        # Get HTML report
        document = db.get_document(doc_id)
        if not document:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404
        
        # Parse JSON fields
        import json as json_lib
        similarity_ref = {}
        similarity_existing = {}
        cheating_metrics = {}
        
        if document.get('similarity_with_reference'):
            try:
                similarity_ref = json_lib.loads(document['similarity_with_reference']) if isinstance(document['similarity_with_reference'], str) else document['similarity_with_reference']
            except:
                pass
        
        if document.get('similarity_with_existing'):
            try:
                similarity_existing = json_lib.loads(document['similarity_with_existing']) if isinstance(document['similarity_with_existing'], str) else document['similarity_with_existing']
            except:
                pass
        
        if document.get('cheating_score'):
            try:
                cheating_metrics = json_lib.loads(document['cheating_score']) if isinstance(document['cheating_score'], str) else document['cheating_score']
            except:
                pass

        eval_v6_results = None
        task_criteria = {}
        eval_v6_similarity = {}
        criteria_overrides = {}
        raw_overrides = document.get('criteria_overrides')
        if raw_overrides and isinstance(raw_overrides, str) and raw_overrides.strip():
            try:
                criteria_overrides = json_lib.loads(raw_overrides)
            except json_lib.JSONDecodeError:
                pass
        elif isinstance(raw_overrides, dict):
            criteria_overrides = raw_overrides
        raw_eval = document.get('eval_v6_results')
        if raw_eval and isinstance(raw_eval, str) and raw_eval.strip():
            try:
                eval_v6_results = json_lib.loads(raw_eval)
            except json_lib.JSONDecodeError:
                pass
        if eval_v6_results and isinstance(eval_v6_results.get('results'), list):
            for q_row in eval_v6_results['results']:
                qid_str = str(q_row.get('Номер вопроса', ''))
                if not qid_str.isdigit():
                    continue
                task_num = int(qid_str)
                chosen = q_row.get('Эталон выбран')
                cos_hr, cos_ai = q_row.get('Cosine HR'), q_row.get('Cosine AI')
                if chosen == 'hr' and cos_hr is not None:
                    eval_v6_similarity[task_num] = cos_hr
                elif chosen == 'ai' and cos_ai is not None:
                    eval_v6_similarity[task_num] = cos_ai
                criteria_pack = q_row.get('Criteria pack') or {}
                details = criteria_pack.get('criteria_details') or []
                base_list = [{'name': c.get('name', ''), 'passed': bool(c.get('passed'))} for c in details]
                overrides_list = criteria_overrides.get(qid_str)
                if isinstance(overrides_list, list) and overrides_list:
                    override_by_name = {c.get('name', ''): c.get('passed', False) for c in overrides_list if c.get('name')}
                    for item in base_list:
                        if item['name'] in override_by_name:
                            item['passed'] = override_by_name[item['name']]
                task_criteria[task_num] = base_list
        for task_num in range(1, 5):
            if task_num not in task_criteria:
                task_criteria[task_num] = []

        html_content = render_template(
            'document_report.html',
            document=document,
            similarity_ref=similarity_ref,
            similarity_existing=similarity_existing,
            cheating_metrics=cheating_metrics,
            task_images={},
            task_prompts={},
            similar_work_data=None,
            has_any_images=False,
            has_parsing_problems=False,
            eval_v6_results=eval_v6_results,
            task_criteria=task_criteria,
            eval_v6_similarity=eval_v6_similarity
        )
        
        # Generate PDF
        pdf_bytes = BytesIO()
        HTML(string=html_content, base_url=request.url_root).write_pdf(pdf_bytes)
        pdf_bytes.seek(0)
        
        from flask import Response
        filename = f"report_{document.get('filename', doc_id)}.pdf"
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except ImportError:
        # Fallback if weasyprint is not available
        return jsonify({
            'error': 'PDF export requires weasyprint library. Install with: pip install weasyprint',
            'status': 'error'
        }), 500
    except Exception as e:
        return jsonify({
            'error': f'Error exporting PDF: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/export/full-db', methods=['GET'])
def api_export_full_db():
    """Export full database to CSV."""
    try:
        import csv
        import io
        from flask import Response
        
        documents = db.get_all_documents()
        
        if not documents:
            return jsonify({
                'error': 'No documents to export',
                'status': 'error'
            }), 404
        
        # Get all column names
        columns = list(documents[0].keys()) if documents else []
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        
        for doc in documents:
            # Convert dict/list values to JSON strings
            row = {}
            for col in columns:
                val = doc.get(col)
                if isinstance(val, (dict, list)):
                    import json
                    row[col] = json.dumps(val, ensure_ascii=False)
                else:
                    row[col] = val
            writer.writerow(row)
        
        # Create response
        output.seek(0)
        response = Response(
            '\ufeff' + output.getvalue(),
            mimetype='text/csv;charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename=full_database_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        )
        return response
    except Exception as e:
        return jsonify({
            'error': f'Error exporting database: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/reprocess/<int:doc_id>', methods=['POST'])
def api_reprocess(doc_id: int):
    """Reprocess a specific document."""
    try:
        processing_service.reprocess_document(doc_id)
        return jsonify({
            'status': 'success',
            'message': f'Document {doc_id} reprocessing started'
        }), 200
    except FileNotFoundError as e:
        return jsonify({
            'error': f'File not found: {str(e)}',
            'status': 'error'
        }), 404
    except ValueError as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 400
    except Exception as e:
        return jsonify({
            'error': f'Error reprocessing document: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/reprocess-unprocessed', methods=['POST'])
def api_reprocess_unprocessed():
    """Reprocess all unprocessed documents (status='pending' or 'error')."""
    try:
        # Get all documents with pending or error status
        all_docs = db.get_all_documents()
        unprocessed = [doc for doc in all_docs 
                       if doc.get('processing_status') in ['pending', 'error']]
        
        if not unprocessed:
            return jsonify({
                'status': 'success',
                'message': 'No unprocessed documents found',
                'count': 0
            }), 200
        
        reprocessed_count = 0
        errors = []
        
        for doc in unprocessed:
            try:
                doc_id = doc.get('id')
                if doc_id:
                    processing_service.reprocess_document(doc_id)
                    reprocessed_count += 1
            except Exception as e:
                errors.append({
                    'doc_id': doc.get('id'),
                    'filename': doc.get('full_filename'),
                    'error': str(e)
                })
        
        return jsonify({
            'status': 'success',
            'message': f'Reprocessing started for {reprocessed_count} documents',
            'count': reprocessed_count,
            'errors': errors if errors else None
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error reprocessing documents: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/competition/complete', methods=['POST'])
def api_complete_competition():
    """Complete competition by selecting top N winners."""
    try:
        data = request.get_json()
        if not data or 'top_n' not in data:
            return jsonify({
                'error': 'No top_n provided',
                'status': 'error'
            }), 400
        
        top_n = int(data.get('top_n', 10))
        if top_n < 1:
            return jsonify({
                'error': 'top_n must be at least 1',
                'status': 'error'
            }), 400
        
        # Get all documents
        documents = db.get_all_documents()
        
        # Filter only approved documents with scores and sort by average_score_tasks_1_3 descending
        # Exclude blocked documents (processing_status='error')
        scored_docs = []
        for doc in documents:
            # Exclude blocked documents
            if doc.get('processing_status') == 'error':
                continue
            # Only include approved documents
            approved = doc.get('approved', 0)
            if not approved:
                continue
            avg_score = doc.get('average_score_tasks_1_3')
            if avg_score is not None:
                scored_docs.append(doc)
        
        # Sort by average_score_tasks_1_3 descending
        scored_docs.sort(key=lambda x: float(x.get('average_score_tasks_1_3', 0)), reverse=True)
        
        # Select top N as winners (only from approved documents)
        winners = scored_docs[:top_n]
        winner_ids = [doc['id'] for doc in winners]
        
        # Mark winners (only from approved documents)
        for doc_id in winner_ids:
            db.update_document(doc_id, candidate_status='winner')
        
        # Log competition completion
        log_action("competition_complete", 
                  details={"top_n": top_n, "winners_count": len(winner_ids), 
                          "winners": winner_ids, "total_approved": len(scored_docs)})
        
        return jsonify({
            'status': 'success',
            'winners_count': len(winner_ids),
            'winners': winner_ids,
            'message': f'Competition completed. {len(winner_ids)} winners selected.'
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error completing competition: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/competition/start', methods=['POST'])
def api_start_competition():
    """Start a new competition by resetting winner and recommended statuses."""
    try:
        # Get all documents
        documents = db.get_all_documents()
        
        # Reset candidate_status for winners and recommended, and reset messages_sent
        reset_count = 0
        reset_doc_ids = []
        for doc in documents:
            status = doc.get('candidate_status')
            if status in ('winner', 'recommended'):
                doc_id = doc['id']
                db.update_document(doc_id, candidate_status='read', messages_sent=0)
                reset_count += 1
                reset_doc_ids.append(doc_id)
        
        # Log competition start
        log_action("competition_start", 
                  details={"reset_count": reset_count, "reset_doc_ids": reset_doc_ids})
        
        return jsonify({
            'status': 'success',
            'reset_count': reset_count,
            'message': f'Competition started. {reset_count} documents reset.'
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error starting competition: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/winners/send-messages', methods=['POST'])
def api_send_messages():
    """Mark messages as sent to winners."""
    try:
        # Get all winners
        documents = db.get_all_documents()
        winners = [doc for doc in documents if doc.get('candidate_status') == 'winner']
        
        if not winners:
            return jsonify({
                'error': 'No winners found',
                'status': 'error'
            }), 404
        
        # Mark messages as sent for all winners
        winner_ids = [doc['id'] for doc in winners]
        for doc_id in winner_ids:
            db.update_document(doc_id, messages_sent=1)
        
        return jsonify({
            'status': 'success',
            'count': len(winner_ids),
            'message': 'Messages sent to winners'
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error sending messages: {str(e)}',
            'status': 'error'
        }), 500


@app.route('/api/info', methods=['GET'])
def api_info():
    """API information endpoint."""
    return jsonify({
        'service': 'Text Parser Microservice',
        'version': '2.0.0',
        'endpoints': {
            'GET /': 'HTML interface',
            'POST /api/upload': 'Upload and process a file',
            'GET /api/documents': 'Get all documents from database',
            'POST /parser/upload': 'Upload and parse a file (legacy)',
            'POST /cleaner/clean-tasks': 'Clean tasks (detect and redistribute tails)',
            'GET /cleaner/status/<filename>': 'Get cleaning status for a file',
            'POST /embeddings/generate': 'Generate embeddings for a document',
            'GET /embeddings/<filename>': 'Get saved embeddings for a file',
            'POST /analysis/similarity': 'Calculate similarity with reference and existing answers',
            'POST /analysis/cheating-detection': 'Detect cheating and LLM usage',
            'GET /analysis/report/<filename>': 'Get full analysis report for a file',
            'POST /api/reprocess/<doc_id>': 'Reprocess a specific document',
            'POST /api/reprocess-unprocessed': 'Reprocess all unprocessed documents',
            'GET /health': 'Health check'
        },
        'supported_formats': list(ALLOWED_EXTENSIONS)
    }), 200


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
