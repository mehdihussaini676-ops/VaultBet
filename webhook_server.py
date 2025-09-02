
from flask import Flask, request, jsonify
import json
import asyncio
import os
import aiohttp
from dotenv import load_dotenv
import threading
import time

load_dotenv()

app = Flask(__name__)

# Load balances function
def load_balances():
    if not os.path.exists("balances.json"):
        return {}
    with open("balances.json", "r") as f:
        return json.load(f)

# Save balances function
def save_balances(balances):
    with open("balances.json", "w") as f:
        json.dump(balances, f, indent=2)

# Initialize user function
def init_user(user_id, balances):
    if user_id not in balances:
        balances[user_id] = {"balance": 0.0, "deposited": 0.0, "withdrawn": 0.0, "wagered": 0.0}

async def get_ltc_price():
    """Get current Litecoin price in USD"""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['litecoin']['usd']
                else:
                    return 75.0  # Fallback price
    except:
        return 75.0  # Fallback price

@app.route('/webhook/litecoin', methods=['POST'])
def litecoin_webhook():
    try:
        data = request.get_json()
        print(f"=== WEBHOOK RECEIVED ===")
        print(f"Raw data: {json.dumps(data, indent=2)}")
        print(f"Request headers: {dict(request.headers)}")
        print(f"Request URL: {request.url}")
        print(f"Request method: {request.method}")
        print(f"Content-Type: {request.headers.get('Content-Type', 'Not specified')}")
        print(f"User-Agent: {request.headers.get('User-Agent', 'Not specified')}")

        if not data:
            print("ERROR: No JSON data received")
            return jsonify({'error': 'No data received'}), 400

        # Load address mappings
        try:
            with open('crypto_addresses.json', 'r') as f:
                mappings = json.load(f)
            print(f"Loaded {len(mappings)} address mappings")
            print(f"Tracked addresses: {list(mappings.keys())}")
        except FileNotFoundError:
            print("ERROR: No address mappings found")
            return jsonify({'error': 'No address mappings found'}), 404

        tx_hash = data.get('hash', 'unknown')
        event_type = data.get('event', 'unknown')
        outputs = data.get('outputs', [])
        
        print(f"Transaction hash: {tx_hash}")
        print(f"Event type: {event_type}")
        print(f"Number of outputs: {len(outputs)}")

        # Process each output to find relevant addresses
        for i, output in enumerate(outputs):
            print(f"Processing output {i}: {output}")
            for address in output.get('addresses', []):
                print(f"Checking address: {address}")
                
                if address in mappings:
                    user_id = mappings[address]['user_id']
                    amount_satoshis = output['value']
                    amount_ltc = amount_satoshis / 100000000

                    print(f"✅ MATCH FOUND!")
                    print(f"   Address: {address}")
                    print(f"   User ID: {user_id}")
                    print(f"   Amount: {amount_ltc} LTC ({amount_satoshis} satoshis)")
                    print(f"   Event: {event_type}")

                    if event_type == 'unconfirmed-tx':
                        print(f"Processing unconfirmed transaction...")
                        
                        # Store transaction for monitoring
                        try:
                            with open('pending_transactions.json', 'r') as f:
                                pending = json.load(f)
                        except FileNotFoundError:
                            pending = {}

                        pending[tx_hash] = {
                            'user_id': user_id,
                            'address': address,
                            'amount_ltc': amount_ltc,
                            'timestamp': data.get('received', ''),
                            'confirmed': False
                        }

                        with open('pending_transactions.json', 'w') as f:
                            json.dump(pending, f, indent=2)

                        print(f"✅ Stored pending transaction: {tx_hash}")

                        # Try to notify user of unconfirmed transaction
                        try:
                            # Import bot and notify user
                            import importlib.util
                            if os.path.exists('main.py'):
                                print("Attempting to notify user of unconfirmed transaction...")
                                # We'll handle this in the main bot file
                        except Exception as e:
                            print(f"Error notifying user of unconfirmed transaction: {e}")

                    elif event_type == 'confirmed-tx':
                        print(f"Processing confirmed transaction...")
                        
                        # Get current LTC price
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            ltc_price = loop.run_until_complete(get_ltc_price())
                            print(f"Current LTC price: ${ltc_price}")
                        finally:
                            loop.close()

                        # Convert LTC to USD
                        amount_usd = amount_ltc * ltc_price

                        print(f"Processing confirmed deposit: {amount_ltc} LTC (${amount_usd:.2f}) for user {user_id}")

                        # Load and update user balance
                        balances = load_balances()
                        init_user(user_id, balances)
                        old_balance = balances[user_id]['balance']
                        balances[user_id]['balance'] += amount_usd
                        balances[user_id]['deposited'] += amount_usd
                        save_balances(balances)

                        print(f"✅ Balance updated!")
                        print(f"   Old balance: ${old_balance:.2f}")
                        print(f"   New balance: ${balances[user_id]['balance']:.2f}")
                        print(f"   Amount added: ${amount_usd:.2f}")

                        # Update pending transactions
                        try:
                            with open('pending_transactions.json', 'r') as f:
                                pending = json.load(f)
                            if tx_hash in pending:
                                pending[tx_hash]['confirmed'] = True
                                with open('pending_transactions.json', 'w') as f:
                                    json.dump(pending, f, indent=2)
                                print(f"✅ Updated pending transaction status")
                        except FileNotFoundError:
                            print("No pending transactions file found")

                        # Create a notification file for the main bot to pick up
                        notification = {
                            'type': 'deposit_confirmed',
                            'user_id': user_id,
                            'amount_ltc': amount_ltc,
                            'amount_usd': amount_usd,
                            'tx_hash': tx_hash,
                            'address': address,
                            'timestamp': time.time()
                        }
                        
                        try:
                            # Load existing notifications
                            try:
                                with open('notifications.json', 'r') as f:
                                    content = f.read().strip()
                                    if content:
                                        notifications = json.loads(content)
                                    else:
                                        notifications = []
                            except (FileNotFoundError, json.JSONDecodeError):
                                notifications = []
                            
                            notifications.append(notification)
                            
                            with open('notifications.json', 'w') as f:
                                json.dump(notifications, f, indent=2)
                            
                            # Force file system sync
                            import os
                            if hasattr(os, 'sync'):
                                os.sync()
                                
                            print(f"✅ Created notification for main bot: {notification}")
                            print(f"✅ Notification written to file successfully")
                            
                            # Also try to directly notify via import if possible
                            try:
                                # Force immediate notification processing
                                notification_file_path = os.path.abspath('notifications.json')
                                print(f"✅ Notification file path: {notification_file_path}")
                                print(f"✅ File exists: {os.path.exists(notification_file_path)}")
                                
                                # Check file size
                                if os.path.exists(notification_file_path):
                                    file_size = os.path.getsize(notification_file_path)
                                    print(f"✅ Notification file size: {file_size} bytes")
                                    
                                    # Read back to verify
                                    with open(notification_file_path, 'r') as verify_f:
                                        verify_content = verify_f.read()
                                        print(f"✅ Notification file content verified: {len(verify_content)} characters")
                                
                            except Exception as verify_error:
                                print(f"❌ Error verifying notification file: {verify_error}")
                            
                        except Exception as e:
                            print(f"❌ Error creating notification: {e}")
                            import traceback
                            traceback.print_exc()

                else:
                    print(f"Address {address} not in mappings (not tracking this address)")

        print("=== WEBHOOK PROCESSING COMPLETE ===")
        return jsonify({'status': 'success', 'processed': True})

    except Exception as e:
        print(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

@app.route('/', methods=['GET'])
def home():
    return jsonify({'message': 'VaultBet Webhook Server', 'status': 'running'})

@app.route('/test-webhook', methods=['POST', 'GET'])
def test_webhook():
    """Test endpoint to verify webhook is working"""
    if request.method == 'POST':
        data = request.get_json()
        print(f"Test webhook received: {data}")
        return jsonify({'status': 'success', 'received': data})
    else:
        return jsonify({'message': 'Send POST request with JSON data to test webhook'})

@app.route('/status', methods=['GET'])
def status():
    """Status endpoint to check server health and mappings"""
    try:
        with open('crypto_addresses.json', 'r') as f:
            mappings = json.load(f)
        address_count = len(mappings)
        addresses = list(mappings.keys())
    except FileNotFoundError:
        address_count = 0
        addresses = []

    return jsonify({
        'status': 'running',
        'addresses_tracked': address_count,
        'addresses': addresses,
        'webhook_url': 'https://vaultbot-gambling.replit.app/webhook/litecoin'
    })

@app.route('/debug/balances', methods=['GET'])
def debug_balances():
    """Debug endpoint to check current balances"""
    try:
        balances = load_balances()
        return jsonify({'balances': balances})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/pending', methods=['GET'])
def debug_pending():
    """Debug endpoint to check pending transactions"""
    try:
        with open('pending_transactions.json', 'r') as f:
            pending = json.load(f)
        return jsonify({'pending_transactions': pending})
    except FileNotFoundError:
        return jsonify({'pending_transactions': {}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def start_webhook_server():
    """Start the webhook server in a separate thread"""
    print("🚀 Starting webhook server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    start_webhook_server()
