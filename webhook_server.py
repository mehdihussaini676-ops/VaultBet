from flask import Flask, request, jsonify
import json
import asyncio
import os
import aiohttp
from dotenv import load_dotenv

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
        json.dump(balances, f)

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
        print(f"Raw data: {data}")
        print(f"Request headers: {dict(request.headers)}")

        if not data:
            print("ERROR: No JSON data received")
            return jsonify({'error': 'No data received'}), 400

        # Load address mappings
        try:
            with open('crypto_addresses.json', 'r') as f:
                mappings = json.load(f)
            print(f"Loaded {len(mappings)} address mappings")
        except FileNotFoundError:
            print("ERROR: No address mappings found")
            return jsonify({'error': 'No address mappings found'}), 404

        tx_hash = data['hash']
        event_type = data.get('event')
        outputs = data.get('outputs', [])

        # Process each output to find relevant addresses
        for output in outputs:
            for address in output.get('addresses', []):
                if address in mappings:
                    user_id = mappings[address]['user_id']
                    amount_satoshis = output['value']
                    amount_ltc = amount_satoshis / 100000000

                    print(f"Processing {event_type} transaction: {amount_ltc} LTC for user {user_id}")

                    if event_type == 'unconfirmed-tx':
                        # Handle unconfirmed transaction - notify user but don't credit balance yet
                        print(f"Unconfirmed transaction detected: {tx_hash} - {amount_ltc} LTC")

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

                        # Import and call handler if available
                        try:
                            from crypto_handler import ltc_handler
                            if ltc_handler:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    loop.run_until_complete(
                                        ltc_handler.handle_unconfirmed_transaction(data, user_id, address, amount_ltc)
                                    )
                                finally:
                                    loop.close()
                        except Exception as e:
                            print(f"Error notifying user of unconfirmed transaction: {e}")

                    elif event_type == 'confirmed-tx':
                        # Handle confirmed transaction - credit balance and notify user

                        # Get current LTC price
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            ltc_price = loop.run_until_complete(get_ltc_price())
                        finally:
                            loop.close()

                        # Convert LTC to USD
                        amount_usd = amount_ltc * ltc_price

                        print(f"Processing confirmed deposit: {amount_ltc} LTC (${amount_usd:.2f}) for user {user_id}")

                        # Load and update user balance
                        balances = load_balances()
                        init_user(user_id, balances)
                        balances[user_id]['balance'] += amount_usd
                        balances[user_id]['deposited'] += amount_usd
                        save_balances(balances)

                        print(f"Updated balance for user {user_id}: ${balances[user_id]['balance']:.2f}")

                        # Update pending transactions
                        try:
                            with open('pending_transactions.json', 'r') as f:
                                pending = json.load(f)
                            if tx_hash in pending:
                                pending[tx_hash]['confirmed'] = True
                                with open('pending_transactions.json', 'w') as f:
                                    json.dump(pending, f, indent=2)
                        except FileNotFoundError:
                            pass

                        # Notify user of confirmation
                        try:
                            from crypto_handler import ltc_handler
                            if ltc_handler:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    tx_info = {
                                        'user_id': user_id,
                                        'amount_ltc': amount_ltc
                                    }
                                    loop.run_until_complete(
                                        ltc_handler.handle_confirmed_transaction(tx_hash, data, tx_info)
                                    )
                                finally:
                                    loop.close()
                        except Exception as e:
                            print(f"Error notifying user of confirmed transaction: {e}")

                        # Schedule forwarding to house wallet (don't block webhook)
                        try:
                            from crypto_handler import ltc_handler
                            if ltc_handler:
                                # Run forwarding in background without blocking webhook
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    private_key = mappings[address]["private_key"]
                                    forward_tx = loop.run_until_complete(
                                        ltc_handler.forward_to_house_wallet(address, private_key, amount_ltc)
                                    )
                                    if forward_tx:
                                        print(f"✅ Successfully forwarded {amount_ltc:.6f} LTC to house wallet: {forward_tx}")
                                    else:
                                        print(f"❌ Failed to forward deposit to house wallet")
                                finally:
                                    loop.close()
                        except Exception as e:
                            print(f"❌ Error forwarding to house wallet: {e}")


        return jsonify({'status': 'success'})

    except Exception as e:
        print(f"Webhook error: {e}")
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
    except FileNotFoundError:
        address_count = 0

    return jsonify({
        'status': 'running',
        'addresses_tracked': address_count,
        'webhook_url': 'https://vaultbot-gambling.replit.app/webhook/litecoin'
    })

if __name__ == '__main__':
    print("Starting webhook server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)
