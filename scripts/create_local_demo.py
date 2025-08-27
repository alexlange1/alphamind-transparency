#!/usr/bin/env python3
"""
Create Local TAO20 Demo
Creates a real, working local demo that you can actually access
"""

import asyncio
import json
import os
from pathlib import Path

class LocalDemoCreator:
    """Creates a real local demo of TAO20 functionality"""
    
    def __init__(self):
        self.demo_port = 3000
        self.api_port = 8000
        
    async def create_local_demo(self):
        """Create a real, working local demo"""
        
        print("🎮 CREATING REAL LOCAL TAO20 DEMO")
        print("=" * 60)
        print("🎯 Goal: Functional demo you can actually use")
        print("🌐 Access: http://localhost:3000")
        print("🔗 API: http://localhost:8000")
        print("=" * 60)
        
        # Step 1: Create demo HTML interface
        await self._create_demo_website()
        
        # Step 2: Create API endpoints
        await self._create_demo_api()
        
        # Step 3: Create start scripts
        await self._create_start_scripts()
        
        # Step 4: Generate demo data
        await self._generate_demo_data()
        
        print("\n🎉 LOCAL DEMO CREATED SUCCESSFULLY!")
        print("=" * 60)
        print("🌐 Demo URL: http://localhost:3000")
        print("📊 API URL: http://localhost:8000")
        print("🚀 Start: python scripts/start_local_demo.py")
        
    async def _create_demo_website(self):
        """Create demo HTML website"""
        
        print("\n🌐 Creating Demo Website")
        print("-" * 40)
        
        # Create demo directory
        demo_dir = Path("demo")
        demo_dir.mkdir(exist_ok=True)
        
        # Create HTML file
        html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TAO20 Local Demo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: white;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 40px; }
        .header h1 { font-size: 3em; margin-bottom: 10px; }
        .header p { font-size: 1.2em; opacity: 0.9; }
        
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 40px; }
        .card { 
            background: rgba(255,255,255,0.1); 
            backdrop-filter: blur(10px);
            border-radius: 15px; 
            padding: 25px; 
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s ease;
        }
        .card:hover { transform: translateY(-5px); }
        .card h3 { margin-bottom: 15px; color: #ffd700; }
        .card p { margin-bottom: 15px; opacity: 0.9; }
        
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .input-group input { 
            width: 100%; 
            padding: 10px; 
            border-radius: 8px; 
            border: none; 
            background: rgba(255,255,255,0.2);
            color: white;
            font-size: 16px;
        }
        .input-group input::placeholder { color: rgba(255,255,255,0.7); }
        
        .btn {
            background: linear-gradient(45deg, #ffd700, #ffed4e);
            color: #333;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            width: 100%;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(255,215,0,0.4); }
        
        .status { 
            background: rgba(0,0,0,0.3); 
            border-radius: 10px; 
            padding: 20px; 
            margin-top: 20px;
            font-family: monospace;
        }
        .status h4 { color: #ffd700; margin-bottom: 10px; }
        
        .nav-display {
            text-align: center;
            background: rgba(0,0,0,0.3);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
        }
        .nav-price { font-size: 2.5em; color: #ffd700; font-weight: bold; }
        .nav-change { font-size: 1.2em; margin-top: 10px; }
        .positive { color: #4ade80; }
        .negative { color: #f87171; }
        
        .privacy-notice {
            background: rgba(255,0,0,0.1);
            border: 1px solid rgba(255,0,0,0.3);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .demo-limitations {
            background: rgba(255,165,0,0.1);
            border: 1px solid rgba(255,165,0,0.3);
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
            font-size: 0.9em;
        }
        
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
        .loading { animation: pulse 1.5s infinite; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🪙 TAO20 Demo</h1>
            <p>Local demonstration of TAO index token functionality</p>
        </div>
        
        <div class="privacy-notice">
            🔒 <strong>Privacy Protected:</strong> This is a local simulation. No real blockchain transactions occur.
        </div>
        
        <div class="nav-display">
            <h3>Current TAO20 NAV</h3>
            <div class="nav-price" id="navPrice">$42.50</div>
            <div class="nav-change positive" id="navChange">+2.3% (24h)</div>
            <p style="margin-top: 10px; opacity: 0.7;">Last updated: <span id="lastUpdate">Just now</span></p>
        </div>
        
        <div class="cards">
            <div class="card">
                <h3>🔥 Mint TAO20 Tokens</h3>
                <p>Convert your TAO into TAO20 index tokens</p>
                
                <div class="input-group">
                    <label for="taoAmount">TAO Amount:</label>
                    <input type="number" id="taoAmount" placeholder="Enter TAO amount (e.g., 10)" min="0.1" max="1000" step="0.1">
                </div>
                
                <button class="btn" onclick="mintTAO20()">Mint TAO20 Tokens</button>
                
                <div class="status" id="mintStatus" style="display: none;">
                    <h4>Transaction Status:</h4>
                    <div id="mintResult"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>💰 Redeem TAO20 Tokens</h3>
                <p>Convert TAO20 tokens back to underlying TAO</p>
                
                <div class="input-group">
                    <label for="tao20Amount">TAO20 Amount:</label>
                    <input type="number" id="tao20Amount" placeholder="Enter TAO20 amount" min="0.1" max="100" step="0.1">
                </div>
                
                <button class="btn" onclick="redeemTAO20()">Redeem for TAO</button>
                
                <div class="status" id="redeemStatus" style="display: none;">
                    <h4>Redemption Status:</h4>
                    <div id="redeemResult"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>📊 Portfolio Stats</h3>
                <p>View your TAO20 holdings and performance</p>
                
                <div class="status">
                    <h4>Your Holdings:</h4>
                    <div>TAO20 Balance: <span id="tao20Balance">0.00</span></div>
                    <div>TAO Value: <span id="taoValue">0.00</span></div>
                    <div>Total USD Value: <span id="usdValue">$0.00</span></div>
                </div>
                
                <button class="btn" onclick="refreshPortfolio()" style="margin-top: 15px;">Refresh Portfolio</button>
            </div>
        </div>
        
        <div class="demo-limitations">
            <h4>⚠️ Demo Limitations:</h4>
            <ul style="margin-left: 20px; margin-top: 10px;">
                <li>This is a local simulation - no real blockchain interactions</li>
                <li>No real TAO or TAO20 tokens are involved</li>
                <li>Data resets when page is refreshed</li>
                <li>Demonstrates user interface and basic functionality only</li>
                <li>Real implementation would connect to Bittensor network</li>
            </ul>
        </div>
    </div>
    
    <script>
        // Demo state
        let portfolioState = {
            tao20Balance: 0,
            taoBalance: 1000, // Start with 1000 TAO for demo
            navPrice: 42.50
        };
        
        // Update NAV price periodically
        function updateNAV() {
            const change = (Math.random() - 0.5) * 2; // Random price movement
            portfolioState.navPrice += change;
            portfolioState.navPrice = Math.max(portfolioState.navPrice, 30); // Min price
            
            document.getElementById('navPrice').textContent = '$' + portfolioState.navPrice.toFixed(2);
            
            const changePercent = (change / portfolioState.navPrice * 100).toFixed(1);
            const changeElement = document.getElementById('navChange');
            changeElement.textContent = (change >= 0 ? '+' : '') + changePercent + '% (24h)';
            changeElement.className = change >= 0 ? 'positive' : 'negative';
            
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
            
            updatePortfolioDisplay();
        }
        
        function mintTAO20() {
            const taoAmount = parseFloat(document.getElementById('taoAmount').value);
            
            if (!taoAmount || taoAmount <= 0) {
                showStatus('mintStatus', 'mintResult', '❌ Please enter a valid TAO amount', false);
                return;
            }
            
            if (taoAmount > portfolioState.taoBalance) {
                showStatus('mintStatus', 'mintResult', '❌ Insufficient TAO balance', false);
                return;
            }
            
            // Simulate processing
            showStatus('mintStatus', 'mintResult', '⏳ Processing mint transaction...', true);
            
            setTimeout(() => {
                // Calculate TAO20 tokens to mint (simplified 1:1 ratio for demo)
                const tao20ToMint = taoAmount;
                
                portfolioState.taoBalance -= taoAmount;
                portfolioState.tao20Balance += tao20ToMint;
                
                const result = `
                    ✅ Mint successful!<br>
                    📥 TAO Deposited: ${taoAmount}<br>
                    🪙 TAO20 Minted: ${tao20ToMint.toFixed(2)}<br>
                    💰 New TAO20 Balance: ${portfolioState.tao20Balance.toFixed(2)}
                `;
                
                showStatus('mintStatus', 'mintResult', result, false);
                updatePortfolioDisplay();
                document.getElementById('taoAmount').value = '';
            }, 2000);
        }
        
        function redeemTAO20() {
            const tao20Amount = parseFloat(document.getElementById('tao20Amount').value);
            
            if (!tao20Amount || tao20Amount <= 0) {
                showStatus('redeemStatus', 'redeemResult', '❌ Please enter a valid TAO20 amount', false);
                return;
            }
            
            if (tao20Amount > portfolioState.tao20Balance) {
                showStatus('redeemStatus', 'redeemResult', '❌ Insufficient TAO20 balance', false);
                return;
            }
            
            // Simulate processing
            showStatus('redeemStatus', 'redeemResult', '⏳ Processing redemption...', true);
            
            setTimeout(() => {
                // Calculate TAO to return (simplified 1:1 ratio for demo)
                const taoToReturn = tao20Amount;
                
                portfolioState.tao20Balance -= tao20Amount;
                portfolioState.taoBalance += taoToReturn;
                
                const result = `
                    ✅ Redemption successful!<br>
                    🔥 TAO20 Burned: ${tao20Amount}<br>
                    📤 TAO Returned: ${taoToReturn.toFixed(2)}<br>
                    💰 New TAO Balance: ${portfolioState.taoBalance.toFixed(2)}
                `;
                
                showStatus('redeemStatus', 'redeemResult', result, false);
                updatePortfolioDisplay();
                document.getElementById('tao20Amount').value = '';
            }, 2000);
        }
        
        function refreshPortfolio() {
            const btn = event.target;
            btn.textContent = 'Refreshing...';
            btn.disabled = true;
            
            setTimeout(() => {
                updatePortfolioDisplay();
                btn.textContent = 'Refresh Portfolio';
                btn.disabled = false;
            }, 1000);
        }
        
        function updatePortfolioDisplay() {
            document.getElementById('tao20Balance').textContent = portfolioState.tao20Balance.toFixed(2);
            document.getElementById('taoValue').textContent = portfolioState.taoBalance.toFixed(2);
            
            const usdValue = (portfolioState.tao20Balance * portfolioState.navPrice).toFixed(2);
            document.getElementById('usdValue').textContent = '$' + usdValue;
        }
        
        function showStatus(statusId, resultId, message, loading) {
            const statusElement = document.getElementById(statusId);
            const resultElement = document.getElementById(resultId);
            
            statusElement.style.display = 'block';
            resultElement.innerHTML = message;
            
            if (loading) {
                resultElement.classList.add('loading');
            } else {
                resultElement.classList.remove('loading');
            }
        }
        
        // Initialize
        updatePortfolioDisplay();
        
        // Update NAV every 30 seconds
        setInterval(updateNAV, 30000);
        
        // Initial load message
        setTimeout(() => {
            console.log('🪙 TAO20 Demo loaded successfully!');
            console.log('🔒 This is a local simulation - no real transactions occur');
        }, 1000);
    </script>
</body>
</html>'''
        
        with open(demo_dir / "index.html", "w") as f:
            f.write(html_content)
        
        print("   ✅ Demo website created: demo/index.html")
        await asyncio.sleep(0.5)
        
    async def _create_demo_api(self):
        """Create simple demo API"""
        
        print("\n🔧 Creating Demo API")
        print("-" * 40)
        
        api_content = '''#!/usr/bin/env python3
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
'''
        
        with open("demo_api.py", "w") as f:
            f.write(api_content)
        
        print("   ✅ Demo API created: demo_api.py")
        await asyncio.sleep(0.5)
        
    async def _create_start_scripts(self):
        """Create start scripts for the demo"""
        
        print("\n🚀 Creating Start Scripts")
        print("-" * 40)
        
        # Python start script
        start_script = '''#!/usr/bin/env python3
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
    
    print("\\n🎮 TAO20 Demo is running!")
    print("=" * 50)
    print("🌐 Website: http://localhost:3000")
    print("🔧 API: http://localhost:8000")
    print("\\n⏹️  Press Ctrl+C to stop the demo")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\\n🛑 Stopping TAO20 Demo...")
        print("Thanks for trying the demo!")

if __name__ == "__main__":
    main()
'''
        
        with open("scripts/start_local_demo.py", "w") as f:
            f.write(start_script)
        
        # Make script executable
        os.chmod("scripts/start_local_demo.py", 0o755)
        
        print("   ✅ Start script created: scripts/start_local_demo.py")
        await asyncio.sleep(0.5)
        
    async def _generate_demo_data(self):
        """Generate demo data and documentation"""
        
        print("\n📊 Generating Demo Data")
        print("-" * 40)
        
        # Create demo documentation
        readme_content = '''# TAO20 Local Demo

## 🎮 What is this?

This is a **real, working local demonstration** of the TAO20 user interface and basic functionality. 

## 🚀 How to run:

```bash
python scripts/start_local_demo.py
```

This will:
- Start a web server on http://localhost:3000
- Start an API server on http://localhost:8000  
- Open your browser automatically

## 🎯 What you can do:

- **View NAV Price**: See simulated TAO20 token price with real-time updates
- **Mint TAO20**: Convert TAO to TAO20 tokens (simulated)
- **Redeem TAO20**: Convert TAO20 back to TAO (simulated)
- **View Portfolio**: Track your holdings and values

## 🔒 Privacy & Security:

- ✅ **Completely local** - no internet connection required
- ✅ **No real blockchain** - all transactions are simulated
- ✅ **No real money** - demo uses fake balances
- ✅ **Your code protected** - demonstrates UI only

## ⚠️ Demo Limitations:

- This is a **UI demonstration only**
- No real TAO or blockchain interactions
- Data resets when page refreshes
- Simplified functionality for demo purposes

## 🎯 Purpose:

This demo shows what the **user experience** would look like without exposing any of your proprietary:
- Miner/validator algorithms
- Trading strategies  
- Economic models
- Rebalancing logic

**Your intellectual property remains 100% protected!**
'''
        
        with open("demo/README.md", "w") as f:
            f.write(readme_content)
        
        print("   ✅ Demo documentation created: demo/README.md")
        await asyncio.sleep(0.5)

async def main():
    """Create the local demo"""
    
    creator = LocalDemoCreator()
    await creator.create_local_demo()
    
    print("\n🎮 Ready to run your demo!")
    print("=" * 50)
    print("📁 Files created:")
    print("   • demo/index.html - Main demo website")
    print("   • demo_api.py - Demo API server")
    print("   • scripts/start_local_demo.py - Start script")
    print("   • demo/README.md - Documentation")
    
    print("\n🚀 To start the demo:")
    print("   python scripts/start_local_demo.py")
    
    print("\n🌐 Demo URLs:")
    print("   • Website: http://localhost:3000")
    print("   • API: http://localhost:8000")

if __name__ == "__main__":
    asyncio.run(main())
