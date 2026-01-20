import http.server
import socketserver
import os
import sys

PORT = 8000
DIRECTORY = "samples_pytc"

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        return super().end_headers()

    def translate_path(self, path):
        # Ensure we serve from the correct directory relative to where the script is run
        # or where the data is located.
        # This script assumes it's run from the project root or we explicitly set the dir.
        return super().translate_path(path)

if __name__ == "__main__":
    # Change to the directory we want to serve
    target_dir = os.path.join(os.getcwd(), DIRECTORY)
    if not os.path.exists(target_dir):
        print(f"Directory {target_dir} not found. Creating it...")
        os.makedirs(target_dir, exist_ok=True)
    
    os.chdir(target_dir)
    
    print(f"Serving directory {target_dir} at http://localhost:{PORT}")
    
    with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
