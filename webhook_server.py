
from flask import Flask, request, jsonify
import json
import asyncio
import discord
from main import balances, save_balances, init_user, log_deposit, bot
from crypto_handler import ltc_handler
import threading

app = Flask(__name__)

@app.route('/webhook/litecoin', methods=['POST'])
def litecoin_webhook():
    try:
        # Verify webhook signature
        signature = request.headers.get('X-BlockCypher-Signature', '')
        if ltc_handler and not ltc_handler.verify_webhook(request.data, signature):
            return jsonify({"error": "Invalid signature"}), 403

        data = request.json
        
        # Process only confirmed transactions (wait for blockchain confirmation)
        if data.get('event') == 'confirmed-tx' and data.get('confirmations', 0) >= 1:
            tx = data.get('transaction', {})
            
            # Check if this is a deposit (incoming transaction)
            for output in tx.get('outputs', []):
                for address in output.get('addresses', []):
                    # Load address mappings
                    try:
                        with open("crypto_addresses.json", "r") as f:
                            mappings = json.load(f)
                        
                        if address in mappings:
                            # This is a deposit to one of our generated addresses
                            user_id = mappings[address]['user_id']
                            
                            # Calculate USD value
                            ltc_amount = output['value'] / 100000000  # Convert satoshis to LTC
                            usd_value = ltc_amount * get_ltc_price_sync()  # Implement sync version
                            
                            # Credit user's balance
                            init_user(user_id)
                            balances[user_id]['balance'] += usd_value
                            balances[user_id]['deposited'] += usd_value
                            save_balances(balances)
                            
                            # Notify user
                            asyncio.create_task(notify_deposit(user_id, usd_value, ltc_amount, tx['hash']))
                            
                            print(f"Processed deposit: {ltc_amount} LTC (${usd_value:.2f}) for user {user_id}")
                    except Exception as e:
                        print(f"Error processing webhook: {e}")
        
        return jsonify({"status": "success"}), 200
    
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

async def notify_deposit(user_id: str, usd_value: float, ltc_amount: float, tx_hash: str):
    """Notify user of successful deposit"""
    try:
        user = bot.get_user(int(user_id))
        if user:
            embed = discord.Embed(
                title="✅ Your deposit of {:.8f} LTC confirmed and credited!".format(ltc_amount),
                color=0x00ff00
            )
            embed.add_field(name="🪙 Litecoin Amount", value=f"{ltc_amount:.8f} LTC", inline=True)
            embed.add_field(name="💵 USD Value", value=f"${usd_value:.2f}", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${balances[user_id]['balance']:.2f} USD", inline=True)
            embed.add_field(name="🧾 Transaction Hash", value=f"`{tx_hash[:16]}...{tx_hash[-16:]}`", inline=False)
            embed.add_field(name="🎮 Ready to Play!", value="Your balance has been updated. You can now use all game commands!", inline=False)
            embed.set_footer(text="⚡ Deposit automatically processed • Transaction confirmed on blockchain")
            
            try:
                await user.send(embed=embed)
            except:
                pass  # User has DMs disabled
                
            # Also log to deposit channel
            member = bot.get_user(int(user_id))
            if member:
                await log_deposit(member, usd_value)
                
    except Exception as e:
        print(f"Error notifying deposit: {e}")

def get_ltc_price_sync():
    """Get current LTC price synchronously"""
    # Implement actual price fetching
    return 75.0  # Placeholder price

def run_webhook_server():
    app.run(host='0.0.0.0', port=5000, debug=False)

# Start webhook server in separate thread
if __name__ == "__main__":
    webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()
