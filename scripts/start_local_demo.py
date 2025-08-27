#!/usr/bin/env python3
"""
Start TAO20 Local Demo
"""

import os
import time
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import subprocess
import sys

class DemoHandler(SimpleHTTPRequestHandler):
    """Custom handler for demo files"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="demo", **kwargs)

def start_web_server():
    """Start web server for demo"""
    server_address = ('', 3000)
    httpd = HTTPServer(server_address, DemoHandler)
    print("🌐 Demo website running on http://localhost:3000")
    httpd.serve_forever()

def start_api_server():
    """Start API server"""
    try:
        subprocess.run([sys.executable, "demo_api.py"], check=True)
    except KeyboardInterrupt:
        pass

def main():
    print("🚀 Starting TAO20 Local Demo")
    print("=" * 50)
    
    # Start API server in background
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()
    
    # Give API server time to start
    time.sleep(2)
    
    # Start web server in background
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()
    
    # Give web server time to start
    time.sleep(2)
    
    # Open browser
    print("🌐 Opening demo in browser...")
    webbrowser.open("http://localhost:3000")
    
    print("\n🎮 TAO20 Demo is running!")
    print("=" * 50)
    print("🌐 Website: http://localhost:3000")
    print("🔧 API: http://localhost:8000")
    print("\n⏹️  Press Ctrl+C to stop the demo")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping TAO20 Demo...")
        print("Thanks for trying the demo!")

if __name__ == "__main__":
    main()
