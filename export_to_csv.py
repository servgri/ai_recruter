"""Script to export processed JSON files to CSV format."""

import os
import json
import csv
import sys
from pathlib import Path
from datetime import datetime


def load_json_files_from_dir(input_dir: str) -> list:
    """
    Load all JSON files from a given directory.
    
    Args:
        input_dir: Directory with JSON files
        
    Returns:
        List of loaded JSON data
    """
    if not input_dir or not os.path.exists(input_dir):
        return []
    result = []
    for filename in os.listdir(input_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(input_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    result.append(json.load(f))
            except Exception as e:
                print(f"Warning: Could not load {filename}: {str(e)}")
    return result


def export_to_csv(json_data: list, output_path: str = "exported_data.csv"):
    """
    Export JSON data to CSV format.
    Each file = one row with columns: full_filename, filename, type, task_1, task_2, task_3, task_4, content
    
    Args:
        json_data: List of JSON data dictionaries
        output_path: Path to output CSV file
    """
    if not json_data:
        print("No data to export")
        return
    
    # Clean content for CSV (remove newlines, limit length)
    def clean_text(text, max_length=None):
        if not text:
            return ''
        # Replace newlines with spaces
        cleaned = text.replace('\n', ' ').replace('\r', ' ')
        # Remove extra spaces
        cleaned = ' '.join(cleaned.split())
        # Limit length if specified
        if max_length and len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + '...'
        return cleaned
    
    # Prepare CSV rows
    rows = []
    for item in json_data:
        full_filename = item.get('filename', '')
        # Extract filename without extension
        filename = os.path.splitext(full_filename)[0] if '.' in full_filename else full_filename
        file_type = item.get('file_type', '')
        content = item.get('content', '')
        
        # Extract tasks
        tasks = item.get('tasks', [])
        task_1 = tasks[0].get('content', '') if len(tasks) > 0 else ''
        task_2 = tasks[1].get('content', '') if len(tasks) > 1 else ''
        task_3 = tasks[2].get('content', '') if len(tasks) > 2 else ''
        task_4 = tasks[3].get('content', '') if len(tasks) > 3 else ''
        
        row = {
            'full_filename': full_filename,
            'filename': filename,
            'type': file_type,
            'task_1': clean_text(task_1),
            'task_2': clean_text(task_2),
            'task_3': clean_text(task_3),
            'task_4': clean_text(task_4),
            'content': clean_text(content)
        }
        rows.append(row)
    
    # Write to CSV
    fieldnames = ['full_filename', 'filename', 'type', 'task_1', 'task_2', 'task_3', 'task_4', 'content']
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"Successfully exported {len(rows)} records to {output_path}")
        return output_path
    except Exception as e:
        print(f"Error writing CSV file: {str(e)}")
        return None


def export_detailed_csv(json_data: list, output_path: str = "exported_data_detailed.csv"):
    """
    Export JSON data to detailed CSV format with separate rows for each task.
    
    Args:
        json_data: List of JSON data dictionaries
        output_path: Path to output CSV file
    """
    if not json_data:
        print("No data to export")
        return
    
    rows = []
    for item in json_data:
        filename = item.get('filename', '')
        file_type = item.get('file_type', '')
        parsed_at = item.get('parsed_at', '')
        
        tasks = item.get('tasks', [])
        
        # Create a row for each task
        for task in tasks:
            task_num = task.get('task_number', '')
            task_content = task.get('content', '')
            
            # Clean text
            def clean_text(text, max_length=5000):
                if not text:
                    return ''
                cleaned = text.replace('\n', ' ').replace('\r', ' ')
                cleaned = ' '.join(cleaned.split())
                if len(cleaned) > max_length:
                    cleaned = cleaned[:max_length] + '...'
                return cleaned
            
            row = {
                'filename': filename,
                'file_type': file_type,
                'parsed_at': parsed_at,
                'task_number': task_num,
                'task_content': clean_text(task_content)
            }
            rows.append(row)
    
    # Write to CSV
    fieldnames = ['filename', 'file_type', 'parsed_at', 'task_number', 'task_content']
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"Successfully exported {len(rows)} task records to {output_path}")
        return output_path
    except Exception as e:
        print(f"Error writing CSV file: {str(e)}")
        return None


def main():
    """Main function for command line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Export processed JSON files to CSV')
    parser.add_argument('--input-dir', required=True,
                       help='Directory with JSON files')
    parser.add_argument('--output', default='exported_data.csv',
                       help='Output CSV file path (default: exported_data.csv)')
    parser.add_argument('--detailed', action='store_true',
                       help='Create detailed CSV with separate row for each task')
    
    args = parser.parse_args()
    
    json_data = load_json_files_from_dir(args.input_dir)
    if not json_data:
        print("No JSON files found in the given directory")
        sys.exit(1)
    print(f"Found {len(json_data)} JSON files")
    
    if args.detailed:
        export_detailed_csv(json_data, args.output)
    else:
        export_to_csv(json_data, args.output)


if __name__ == '__main__':
    main()
