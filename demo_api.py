#!/usr/bin/env python3
"""
Simple Demo API for TAO20 Local Demo
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import time
import random
from urllib.parse import urlparse, parse_qs
import threading

class TAO20DemoAPI(SimpleHTTPRequestHandler):
    """Simple API for TAO20 demo"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/nav':
            self.send_nav_data()
        elif parsed_path.path == '/api/portfolio':
            self.send_portfolio_data()
        else:
            self.send_error(404, "API endpoint not found")
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/mint':
            self.handle_mint()
        elif parsed_path.path == '/api/redeem':
            self.handle_redeem()
        else:
            self.send_error(404, "API endpoint not found")
    
    def send_nav_data(self):
        """Send NAV data"""
        nav_data = {
            "nav_price": round(42.50 + random.uniform(-2, 2), 2),
            "change_24h": round(random.uniform(-5, 5), 2),
            "last_updated": int(time.time()),
            "status": "active"
        }
        
        self.send_json_response(nav_data)
    
    def send_portfolio_data(self):
        """Send portfolio data"""
        portfolio_data = {
            "tao20_balance": 0.0,
            "tao_balance": 1000.0,
            "usd_value": 0.0,
            "last_updated": int(time.time())
        }
        
        self.send_json_response(portfolio_data)
    
    def handle_mint(self):
        """Handle mint request"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            amount = float(data.get('amount', 0))
            
            if amount <= 0:
                self.send_json_response({"error": "Invalid amount"}, 400)
                return
            
            # Simulate processing delay
            time.sleep(1)
            
            response = {
                "success": True,
                "tao_deposited": amount,
                "tao20_minted": amount,
                "transaction_id": f"mint_{int(time.time())}",
                "timestamp": int(time.time())
            }
            
            self.send_json_response(response)
            
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)
    
    def handle_redeem(self):
        """Handle redeem request"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            amount = float(data.get('amount', 0))
            
            if amount <= 0:
                self.send_json_response({"error": "Invalid amount"}, 400)
                return
            
            # Simulate processing delay
            time.sleep(1)
            
            response = {
                "success": True,
                "tao20_burned": amount,
                "tao_returned": amount,
                "transaction_id": f"redeem_{int(time.time())}",
                "timestamp": int(time.time())
            }
            
            self.send_json_response(response)
            
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)
    
    def send_json_response(self, data, status_code=200):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        response = json.dumps(data, indent=2)
        self.wfile.write(response.encode('utf-8'))

def start_api_server(port=8000):
    """Start the demo API server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, TAO20DemoAPI)
    print(f"🔧 Demo API server running on http://localhost:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    start_api_server()
