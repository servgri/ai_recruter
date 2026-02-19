"""Script to upload files to Flask microservice."""

import os
import requests
import sys
from pathlib import Path


def upload_file(file_path: str, server_url: str = "http://localhost:5000") -> dict:
    """
    Upload a single file to the Flask service.
    
    Args:
        file_path: Path to the file to upload
        server_url: URL of the Flask service
        
    Returns:
        Response from the server as dictionary
    """
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}", "status": "error"}
    
    url = f"{server_url}/upload"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f)}
            response = requests.post(url, files=files)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": f"Server returned status {response.status_code}",
                "details": response.text,
                "status": "error"
            }
    except requests.exceptions.ConnectionError:
        return {
            "error": f"Could not connect to server at {server_url}. Make sure Flask app is running.",
            "status": "error"
        }
    except Exception as e:
        return {
            "error": f"Error uploading file: {str(e)}",
            "status": "error"
        }


def upload_directory(directory_path: str, server_url: str = "http://localhost:5000", 
                     extensions: list = None) -> list:
    """
    Upload all files from a directory to the Flask service.
    
    Args:
        directory_path: Path to directory with files
        server_url: URL of the Flask service
        extensions: List of file extensions to process (None = all supported)
        
    Returns:
        List of upload results
    """
    if extensions is None:
        extensions = ['.txt', '.pdf', '.docx', '.md', '.sql', '.doc', '.xlsx', '.xls']
    
    results = []
    files_processed = 0
    files_success = 0
    files_failed = 0
    
    print(f"Scanning directory: {directory_path}")
    
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            file_ext = os.path.splitext(file)[1].lower()
            if file_ext in extensions:
                file_path = os.path.join(root, file)
                print(f"Uploading: {file}...", end=" ")
                
                result = upload_file(file_path, server_url)
                result['file_path'] = file_path
                result['filename'] = file
                results.append(result)
                
                files_processed += 1
                if result.get('status') == 'success':
                    files_success += 1
                    print("✓ Success")
                else:
                    files_failed += 1
                    print(f"✗ Failed: {result.get('error', 'Unknown error')}")
    
    print(f"\nSummary:")
    print(f"  Total files processed: {files_processed}")
    print(f"  Successful: {files_success}")
    print(f"  Failed: {files_failed}")
    
    return results


def main():
    """Main function for command line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Upload files to Flask text parser service')
    parser.add_argument('path', help='Path to file or directory to upload')
    parser.add_argument('--server', default='http://localhost:5000',
                       help='Flask server URL (default: http://localhost:5000)')
    parser.add_argument('--extensions', nargs='+',
                       default=['.txt', '.pdf', '.docx', '.md', '.sql', '.doc', '.xlsx', '.xls'],
                       help='File extensions to process (default: all supported)')
    
    args = parser.parse_args()
    
    path = Path(args.path)
    
    if not path.exists():
        print(f"Error: Path does not exist: {args.path}")
        sys.exit(1)
    
    if path.is_file():
        # Upload single file
        print(f"Uploading file: {path}")
        result = upload_file(str(path), args.server)
        if result.get('status') == 'success':
            print(f"✓ Success! JSON saved to: {result.get('json_path')}")
        else:
            print(f"✗ Error: {result.get('error')}")
            sys.exit(1)
    elif path.is_dir():
        # Upload directory
        upload_directory(str(path), args.server, args.extensions)
    else:
        print(f"Error: Path is neither a file nor a directory: {args.path}")
        sys.exit(1)


if __name__ == '__main__':
    main()
