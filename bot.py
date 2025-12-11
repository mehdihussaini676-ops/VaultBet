import discord
from discord import app_commands
from discord.ext import commands
import os
import random
import json
import aiohttp
import asyncio
import time
from dotenv import load_dotenv
from game_image_generator import GameImageGenerator
from flask import Flask, request, jsonify
import threading

# Load environment variables from .env file
load_dotenv()

# Initialize game image generator
game_img_gen = GameImageGenerator()

# Initialize card generator
from card_generator import CardImageGenerator
card_generator = CardImageGenerator()

# Load environment variables directly from os.environ (works with Replit Secrets)
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
BLOCKCYPHER_API_KEY = os.getenv("BLOCKCYPHER_API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
DEPOSIT_LOG_CHANNEL_ID = int(os.getenv("DEPOSIT_LOG_CHANNEL_ID", "1412728845500678235"))
WITHDRAW_LOG_CHANNEL_ID = int(os.getenv("WITHDRAW_LOG_CHANNEL_ID", "1412730247987855370"))
CRYPTO_DEPOSIT_LOG_CHANNEL_ID = 1444699126511173662

# Debug: Print if keys are loaded
print(f"Environment check:")
print(f"- Discord token: {'✅' if TOKEN else '❌'}")
print(f"- Admin IDs: {ADMIN_IDS if ADMIN_IDS else '❌ None configured'}")
print(f"- BlockCypher key: {'✅' if BLOCKCYPHER_API_KEY else '❌'}")
print(f"- Webhook secret: {'✅' if WEBHOOK_SECRET else '❌'}")
print(f"- Deposit log channel: {DEPOSIT_LOG_CHANNEL_ID}")
print(f"- Withdraw log channel: {WITHDRAW_LOG_CHANNEL_ID}")

# Set up intents for Discord bot
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

# Create bot instance with proper setup for slash commands
bot = commands.Bot(command_prefix="!", intents=intents)

# Create Flask app for webhook handling
flask_app = Flask(__name__)

# Ensure the command tree is properly initialized
@bot.event
async def setup_hook():
    """This is called when the bot is starting up"""
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Initialize crypto handler to None
ltc_handler = None

# Status route for webview
@flask_app.route('/', methods=['GET'])
def status():
    """Simple status page for the webview"""
    return jsonify({
        "status": "online",
        "service": "VaultBet Discord Bot Webhook Server",
        "endpoints": {
            "webhook": "/webhook/apirone"
        },
        "message": "Webhook server is running and ready to receive callbacks"
    }), 200

# Apirone webhook route
@flask_app.route('/webhook/apirone', methods=['POST'])
def handle_apirone_webhook():
    """Handle incoming Apirone callbacks for deposit detection"""
    try:
        global ltc_handler
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data"}), 400

        # Process the callback asynchronously in the Discord bot's event loop
        if ltc_handler:
            # Create an async task to process the callback
            asyncio.run_coroutine_threadsafe(
                ltc_handler.process_apirone_callback(data),
                bot.loop
            )
            return jsonify({"status": "ok"}), 200
        else:
            return jsonify({"error": "Handler not ready"}), 503
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def start_flask_server():
    """Start Flask webhook server in a separate thread"""
    try:
        flask_app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        print(f"❌ Flask server error: {e}")

# --- Utility Functions ---

def format_number(num):
    """Formats a number with abbreviations (k, M, B, etc.)"""
    if abs(num) < 1000:
        return f"{num:.2f}"
    elif abs(num) < 1000000:
        return f"{num/1000:.2f}k"
    elif abs(num) < 1000000000:
        return f"{num/1000000:.2f}M"
    else:
        return f"{num/1000000000:.2f}B"

def parse_amount(amount_str, user_id=None):
    """Parses a string amount with abbreviations (k, M, B) into a float."""
    amount_str = str(amount_str).lower().strip()

    # Handle special cases first
    if amount_str == "half" and user_id:
        return max(0.0, balances.get(user_id, {}).get("balance", 0.0) / 2)
    elif amount_str == "all" and user_id:
        return max(0.0, balances.get(user_id, {}).get("balance", 0.0))

    # Handle abbreviations
    multiplier = 1
    if amount_str.endswith('k'):
        multiplier = 1000
        amount_str = amount_str[:-1]
    elif amount_str.endswith('m'):
        multiplier = 1000000
        amount_str = amount_str[:-1]
    elif amount_str.endswith('b'):
        multiplier = 1000000000
        amount_str = amount_str[:-1]

    try:
        value = float(amount_str) * multiplier
        return max(0.0, value)
    except ValueError:
        raise ValueError("Invalid amount format")


# Load balances
def load_balances():
    if not os.path.exists("balances.json"):
        return {}
    with open("balances.json", "r") as f:
        return json.load(f)

# Save balances
def save_balances(balances):
    with open("balances.json", "w") as f:
        json.dump(balances, f)

# Load rakeback data
def load_rakeback_data():
    if not os.path.exists("rakeback.json"):
        return {}
    with open("rakeback.json", "r") as f:
        return json.load(f)

# Save rakeback data
def save_rakeback_data(data):
    with open("rakeback.json", "w") as f:
        json.dump(data, f)

# Load affiliation data
def load_affiliation_data():
    if not os.path.exists("affiliations.json"):
        return {}
    with open("affiliations.json", "r") as f:
        return json.load(f)

# Save affiliation data
def save_affiliation_data(data):
    with open("affiliations.json", "w") as f:
        json.dump(data, f)

# Load promo codes
def load_promo_codes():
    if not os.path.exists("promo_codes.json"):
        return {}
    with open("promo_codes.json", "r") as f:
        return json.load(f)

# Save promo codes
def save_promo_codes(data):
    with open("promo_codes.json", "w") as f:
        json.dump(data, f)

# Load promo usage data
def load_promo_usage():
    if not os.path.exists("promo_usage.json"):
        return {}
    with open("promo_usage.json", "r") as f:
        return json.load(f)

# Save promo usage data
def save_promo_usage(data):
    with open("promo_usage.json", "w") as f:
        json.dump(data, f)

# Load message tracking data
def load_message_tracking():
    if not os.path.exists("message_tracking.json"):
        return {}
    with open("message_tracking.json", "r") as f:
        return json.load(f)

# Save message tracking data
def save_message_tracking(data):
    with open("message_tracking.json", "w") as f:
        json.dump(data, f)

# Load house balance
def load_house_balance():
    if not os.path.exists("house_balance.json"):
        return {"balance_ltc": 0.0, "balance_usd": 0.0, "total_deposits": 0.0, "total_withdrawals": 0.0}
    with open("house_balance.json", "r") as f:
        return json.load(f)

# Save house balance
def save_house_balance(data):
    with open("house_balance.json", "w") as f:
        json.dump(data, f)

# Load withdrawal requests queue
def load_withdrawal_requests():
    if not os.path.exists("withdrawal_requests.json"):
        return {}
    with open("withdrawal_requests.json", "r") as f:
        return json.load(f)

# Save withdrawal requests queue
def save_withdrawal_requests(data):
    with open("withdrawal_requests.json", "w") as f:
        json.dump(data, f, indent=2)

# Initialize user
def init_user(user_id):
    if user_id not in balances:
        balances[user_id] = {"balance": 0.0, "deposited": 0.0, "withdrawn": 0.0, "wagered": 0.0}
    if user_id not in rakeback_data:
        rakeback_data[user_id] = {"total_wagered": 0.0, "rakeback_earned": 0.0}
    if user_id not in affiliation_data:
        affiliation_data[user_id] = {"affiliated_to": None, "total_earned": 0.0}

# Check if user is admin
def is_admin(user_id):
    return user_id in ADMIN_IDS

# Cooldown tracking
COOLDOWN_TIME = 1.0  # 1 second cooldown
user_cooldowns = {}

def check_cooldown(user_id):
    current_time = asyncio.get_event_loop().time()
    if user_id in user_cooldowns:
        last_used_time = user_cooldowns[user_id]
        remaining_time = COOLDOWN_TIME - (current_time - last_used_time)
        if remaining_time > 0:
            return False, remaining_time
    user_cooldowns[user_id] = current_time
    return True, 0

balances = load_balances()
rakeback_data = load_rakeback_data()
affiliation_data = load_affiliation_data()
promo_codes = load_promo_codes()
promo_usage = load_promo_usage()
message_tracking = load_message_tracking()
house_balance = load_house_balance()
withdrawal_requests = load_withdrawal_requests()

# Rakeback system constants
RAKEBACK_PERCENTAGE = 0.005  # 0.5%

# Affiliation system constants
AFFILIATION_PERCENTAGE = 0.005  # 0.5%

# Add rakeback to a user's total wagered amount and handle affiliations
def add_rakeback(user_id, wager_amount_usd):
    init_user(user_id)
    rakeback_data[user_id]["total_wagered"] += wager_amount_usd
    rakeback_data[user_id]["rakeback_earned"] += wager_amount_usd * RAKEBACK_PERCENTAGE
    save_rakeback_data(rakeback_data)

    # Handle affiliation payout
    handle_affiliation_payout(user_id, wager_amount_usd)

# Handle affiliation payouts
def handle_affiliation_payout(user_id, wager_amount_usd):
    # Check if user is affiliated to someone
    if user_id in affiliation_data and affiliation_data[user_id]["affiliated_to"]:
        affiliate_id = affiliation_data[user_id]["affiliated_to"]

        # Calculate affiliate commission
        commission_usd = wager_amount_usd * AFFILIATION_PERCENTAGE

        # Initialize affiliate if needed
        init_user(affiliate_id)

        # Add commission to affiliate's balance
        balances[affiliate_id]["balance"] += commission_usd
        affiliation_data[affiliate_id]["total_earned"] += commission_usd

        # Save data
        save_balances(balances)
        save_affiliation_data(affiliation_data)

        print(f"Affiliate payout: ${commission_usd:.4f} USD to user {affiliate_id} from user {user_id}'s wager")

# Logging functions for deposit and withdraw channels
async def log_deposit(member, amount_usd):
    deposit_channel_id = 1403907103944605736
    channel = bot.get_channel(deposit_channel_id)
    if channel:
        embed = discord.Embed(
            title="💸 New Deposit Logged",
            color=0x00ff00
        )
        embed.add_field(name="👤 Depositor", value=member.display_name, inline=True)
        embed.add_field(name="💵 Amount Deposited", value=f"${amount_usd:.2f} USD", inline=True)
        embed.add_field(name="📊 Total Deposited by User", value=f"${balances[str(member.id)]['deposited']:.2f} USD", inline=True)
        await channel.send(embed=embed)

async def log_admin_deposit(admin_member, target_member, amount_usd):
    """Log admin-confirmed deposits to the admin deposit log channel"""
    log_channel = bot.get_channel(DEPOSIT_LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(
            title="🔧 Admin Deposit Confirmation",
            description="An administrator has manually credited a user's account",
            color=0x0099ff
        )
        embed.add_field(name="👑 Admin", value=f"{admin_member.display_name} ({admin_member.id})", inline=True)
        embed.add_field(name="👤 User Credited", value=f"{target_member.display_name} ({target_member.id})", inline=True)
        embed.add_field(name="💵 Amount Credited", value=f"${amount_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 User's New Balance", value=f"${balances[str(target_member.id)]['balance']:.2f} USD", inline=True)
        embed.add_field(name="📊 User's Total Deposited", value=f"${balances[str(target_member.id)]['deposited']:.2f} USD", inline=True)
        embed.add_field(name="⏰ Timestamp", value=f"<t:{int(time.time())}:F>", inline=True)
        embed.set_footer(text="Manual deposit confirmation by administrator")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send admin deposit log: {e}")

async def log_deposit_webhook(member, amount_ltc, amount_usd, tx_hash, input_address):
    """Log crypto deposits from webhook callbacks to dedicated channel"""
    channel = bot.get_channel(CRYPTO_DEPOSIT_LOG_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="💰 Crypto Deposit Confirmed",
            description="Automatic deposit detection via blockchain",
            color=0x00ff00
        )
        embed.add_field(name="👤 Depositor", value=f"{member.mention if hasattr(member, 'mention') else member}", inline=True)
        embed.add_field(name="💵 USD Value", value=f"${amount_usd:.2f} USD", inline=True)
        embed.add_field(name="₿ LTC Amount", value=f"{amount_ltc:.8f} LTC", inline=True)
        embed.add_field(name="📍 Receiving Address", value=f"`{input_address}`", inline=False)
        embed.add_field(name="🔗 Transaction Hash", value=f"`{tx_hash[:32]}...`", inline=False)
        embed.add_field(name="⏰ Timestamp", value=f"<t:{int(time.time())}:F>", inline=False)
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send crypto deposit log: {e}")

async def log_house_balance_webhook(admin_member, house_balance_ltc, house_balance_usd, wallet_address):
    """Log house balance check to dedicated channel"""
    channel = bot.get_channel(CRYPTO_DEPOSIT_LOG_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🏦 House Balance Updated",
            description="Current confirmed balance in house wallet",
            color=0x0099ff
        )
        embed.add_field(name="👑 Admin", value=f"{admin_member.mention}", inline=True)
        embed.add_field(name="₿ LTC Balance", value=f"{house_balance_ltc:.8f} LTC", inline=True)
        embed.add_field(name="💵 USD Value", value=f"${house_balance_usd:.2f} USD", inline=True)
        embed.add_field(name="📍 Wallet Address", value=f"`{wallet_address}`", inline=False)
        embed.add_field(name="⏰ Timestamp", value=f"<t:{int(time.time())}:F>", inline=False)
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send house balance log: {e}")

async def log_withdraw(member, amount_usd, crypto_address):
    withdraw_channel_id = 1403907128023842996
    channel = bot.get_channel(withdraw_channel_id)
    if channel:
        embed = discord.Embed(
            title="💸 New Withdrawal Logged",
            color=0xffaa00
        )
        embed.add_field(name="👤 Withdrawer", value=member.display_name, inline=True)
        embed.add_field(name="💵 Amount Withdrawn", value=f"${amount_usd:.2f} USD", inline=True)
        embed.add_field(name="📍 Crypto Address", value=f"`{crypto_address}`", inline=False)
        await channel.send(embed=embed)

async def log_admin_withdraw(admin_member, target_member, amount_usd, ltc_address, withdrawal_id):
    """Log admin-confirmed withdrawals to the admin withdraw log channel"""
    log_channel = bot.get_channel(WITHDRAW_LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(
            title="🔧 Admin Withdrawal Confirmation",
            description="An administrator has manually processed a withdrawal request",
            color=0xff6600
        )
        embed.add_field(name="👑 Admin", value=f"{admin_member.display_name} ({admin_member.id})", inline=True)
        embed.add_field(name="👤 User", value=f"{target_member.display_name} ({target_member.id})", inline=True)
        embed.add_field(name="💵 Amount Withdrawn", value=f"${amount_usd:.2f} USD", inline=True)
        embed.add_field(name="📍 LTC Address", value=f"`{ltc_address}`", inline=False)
        embed.add_field(name="🆔 Withdrawal ID", value=f"`{withdrawal_id}`", inline=True)
        embed.add_field(name="📊 User's Total Withdrawn", value=f"${balances[str(target_member.id)]['withdrawn']:.2f} USD", inline=True)
        embed.add_field(name="⏰ Timestamp", value=f"<t:{int(time.time())}:F>", inline=True)
        embed.set_footer(text="Manual withdrawal confirmation by administrator")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send admin withdraw log: {e}")

async def log_admin_balance_change(admin_member, target_member, amount_usd, action_type):
    """Log admin balance changes to the specified channel"""
    log_channel = bot.get_channel(1413123452193341450)
    if log_channel:
        embed = discord.Embed(
            title=f"🔧 Admin Balance {action_type.title()}",
            description=f"An administrator has {action_type.lower()} user balance",
            color=0x0099ff if action_type == "Addition" else 0xff6600
        )
        embed.add_field(name="👑 Admin", value=f"{admin_member.display_name} ({admin_member.id})", inline=True)
        embed.add_field(name="👤 Target User", value=f"{target_member.display_name} ({target_member.id})", inline=True)
        embed.add_field(name="💵 Amount", value=f"${amount_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 User's New Balance", value=f"${balances[str(target_member.id)]['balance']:.2f} USD", inline=True)
        embed.add_field(name="⏰ Timestamp", value=f"<t:{int(time.time())}:F>", inline=True)
        embed.set_footer(text=f"Manual balance {action_type.lower()} by administrator")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send admin balance change log: {e}")

async def log_tip_transaction(sender, receiver, amount_usd):
    """Log tip transactions to the specified channel"""
    log_channel = bot.get_channel(1413123467171336273)
    if log_channel:
        embed = discord.Embed(
            title="💝 Tip Transaction",
            description="A user has sent a tip to another player",
            color=0x00ff00
        )
        embed.add_field(name="👤 Sender", value=f"{sender.display_name} ({sender.id})", inline=True)
        embed.add_field(name="👤 Receiver", value=f"{receiver.display_name} ({receiver.id})", inline=True)
        embed.add_field(name="💰 Amount", value=f"${amount_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 Sender's New Balance", value=f"${balances[str(sender.id)]['balance']:.2f} USD", inline=True)
        embed.add_field(name="💳 Receiver's New Balance", value=f"${balances[str(receiver.id)]['balance']:.2f} USD", inline=True)
        embed.add_field(name="⏰ Timestamp", value=f"<t:{int(time.time())}:F>", inline=True)
        embed.set_footer(text="Player tip transaction")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send tip transaction log: {e}")

async def log_affiliation_change(user, affiliate, previous_affiliate=None):
    """Log affiliation changes to the specified channel"""
    log_channel = bot.get_channel(1413123467171336273)
    if log_channel:
        embed = discord.Embed(
            title="🤝 Affiliation Update",
            description="A user has updated their affiliation",
            color=0x9932cc
        )
        embed.add_field(name="👤 User", value=f"{user.display_name} ({user.id})", inline=True)
        embed.add_field(name="👤 New Affiliate", value=f"{affiliate.display_name} ({affiliate.id})", inline=True)

        if previous_affiliate:
            embed.add_field(name="👤 Previous Affiliate", value=f"{previous_affiliate.display_name} ({previous_affiliate.id})", inline=True)
        else:
            embed.add_field(name="👤 Previous Affiliate", value="None", inline=True)

        embed.add_field(name="💰 Commission Rate", value="0.5%", inline=True)
        embed.add_field(name="📊 Affiliate's Total Earned", value=f"${affiliation_data[str(affiliate.id)]['total_earned']:.2f} USD", inline=True)
        embed.add_field(name="⏰ Timestamp", value=f"<t:{int(time.time())}:F>", inline=True)
        embed.set_footer(text="Affiliation system update")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send affiliation change log: {e}")

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

async def check_notifications():
    """Check for notifications from the webhook server"""
    print("🔔 Notification checker started - checking every 5 seconds")

    while True:
        try:

            # Check for notifications from webhook
            notification_file_exists = os.path.exists('notifications.json')

            if notification_file_exists:
                try:
                    with open('notifications.json', 'r') as f:
                        content = f.read().strip()

                    if content:
                        notifications = json.loads(content)
                    else:
                        notifications = []

                except (json.JSONDecodeError, FileNotFoundError) as e:
                    notifications = []

                if notifications:
                    processed_notifications = []
                    for notification in notifications:
                        try:
                            if notification.get('type') == 'deposit_confirmed':
                                user_id = notification['user_id']
                                amount_ltc = notification['amount_ltc']
                                amount_usd = notification['amount_usd']
                                tx_hash = notification['tx_hash']

                                print(f"🔔 Processing deposit confirmation for user {user_id}: {amount_ltc} LTC (${amount_usd:.2f})")

                                user = bot.get_user(int(user_id))
                                if user:
                                    embed = discord.Embed(
                                        title="✅ Deposit Confirmed & Credited!",
                                        description="Your Litecoin deposit has been successfully processed",
                                        color=0x00ff00
                                    )
                                    embed.add_field(name="💰 Amount", value=f"{amount_ltc:.8f} LTC", inline=True)
                                    embed.add_field(name="💵 USD Value", value=f"${amount_usd:.2f} USD", inline=True)
                                    embed.add_field(name="🔗 Transaction", value=f"`{tx_hash[:16]}...`", inline=False)
                                    embed.add_field(name="🎮 Status", value="Balance updated - ready to play!", inline=True)
                                    embed.set_footer(text="Your deposit has been credited")

                                    try:
                                        await user.send(embed=embed)
                                        print(f"✅ Sent deposit confirmation to user {user_id}")
                                        # Log the deposit
                                        await log_deposit(user, amount_usd)
                                    except discord.Forbidden:
                                        print(f"⚠️ Could not send DM to user {user_id} - DMs disabled")
                                    except Exception as dm_error:
                                        print(f"❌ Error sending DM to user {user_id}: {dm_error}")

                                processed_notifications.append(notification)

                        except Exception as e:
                            print(f"❌ Error processing notification: {e}")
                            processed_notifications.append(notification)  # Still mark as processed

                    # Clear processed notifications
                    if processed_notifications:
                        try:
                            remaining_notifications = [n for n in notifications if n not in processed_notifications]
                            with open('notifications.json', 'w') as f:
                                json.dump(remaining_notifications, f, indent=2)
                            if processed_notifications:
                                print(f"✅ Processed {len(processed_notifications)} notification(s)")
                        except Exception as e:
                            print(f"❌ Error clearing notifications: {e}")

        except Exception as e:
            print(f"❌ Error processing notifications file: {e}")

        await asyncio.sleep(5)  # Check every 5 seconds

@bot.event
async def on_message(message):
    # Don't track bot messages
    if message.author.bot:
        return

    # Only track messages in guilds (not DMs)
    if not message.guild:
        return

    user_id = str(message.author.id)

    # Initialize user if not exists
    if user_id not in message_tracking:
        message_tracking[user_id] = {"count": 0, "total_rewarded": 0}

    # Increment message count
    message_tracking[user_id]["count"] += 1

    # Check if user reached 100 messages
    if message_tracking[user_id]["count"] >= 100:
        # Reset count and give reward
        message_tracking[user_id]["count"] = 0
        message_tracking[user_id]["total_rewarded"] += 1

        # Add $0.10 to user's balance
        init_user(user_id)
        balances[user_id]["balance"] += 0.10
        save_balances(balances)
        save_message_tracking(message_tracking)

        # Send reward notification
        try:
            embed = discord.Embed(
                title="💬 Chat Reward! 🎉",
                description="You've been rewarded for being active in the server!",
                color=0x00ff00
            )
            embed.add_field(name="💰 Reward", value="$0.10 USD", inline=True)
            embed.add_field(name="📊 Messages Sent", value="100 messages", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${balances[user_id]['balance']:.2f} USD", inline=True)
            embed.add_field(name="🎯 Total Rewards", value=f"{message_tracking[user_id]['total_rewarded']} times", inline=True)
            embed.set_footer(text="Keep chatting to earn more rewards!")

            await message.author.send(embed=embed)
        except discord.Forbidden:
            # User has DMs disabled, send in channel
            try:
                embed = discord.Embed(
                    title="💬 Chat Reward!",
                    description=f"{message.author.mention} earned $0.10 for 100 messages!",
                    color=0x00ff00
                )
                await message.channel.send(embed=embed, delete_after=10)
            except:
                pass
    else:
        # Save updated count
        save_message_tracking(message_tracking)

@bot.event
async def on_ready():
    global ltc_handler
    print(f"Logged in as {bot.user}")
    print(f"Bot is in {len(bot.guilds)} guilds")

    try:
        # Sync application commands
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

    # Always start the webhook server and notification checker first
    import threading
    import subprocess
    import sys

    def start_webhook_server():
        """Start webhook server in a separate thread"""
        try:
            flask_thread = threading.Thread(target=start_flask_server, daemon=True)
            flask_thread.start()
            print("✅ Webhook server started on port 5000")
        except Exception as e:
            print(f"❌ Failed to start webhook server: {e}")

    # Start webhook server for Apirone callbacks
    start_webhook_server()

    # Start notification checker
    asyncio.create_task(check_notifications())
    print("✅ Notification checker started")

    # Initialize Litecoin handler with bot instance
    if BLOCKCYPHER_API_KEY:
        try:
            print(f"🔄 Initializing crypto handler...")
            print(f"   API Key: {BLOCKCYPHER_API_KEY[:8]}...{BLOCKCYPHER_API_KEY[-4:]}")
            print(f"   Webhook Secret: {'✅ Set' if WEBHOOK_SECRET else '❌ Missing'}")

            from crypto_handler import init_litecoin_handler
            ltc_handler = init_litecoin_handler(BLOCKCYPHER_API_KEY, WEBHOOK_SECRET, bot)

            if ltc_handler and hasattr(ltc_handler, 'api_key') and ltc_handler.api_key:
                print(f"✅ Crypto handler created successfully")

                # Try to initialize house wallet, but don't fail if it doesn't work
                try:
                    house_wallet_initialized = await ltc_handler.initialize_house_wallet()
                    if house_wallet_initialized:
                        print(f"✅ House wallet initialized: {ltc_handler.house_wallet_address}")
                    else:
                        print("⚠️ House wallet initialization failed - address generation will still work")
                        print("   This is expected if you haven't created a house wallet yet")
                        print("   Deposits work via individual user addresses, withdrawals require manual processing")
                except Exception as house_error:
                    print(f"⚠️ House wallet setup failed: {house_error}")
                    print("   Address generation will still work for deposits")
                    import traceback
                    traceback.print_exc()

                print(f"✅ Crypto handler is ready for deposit address generation")
            else:
                print(f"❌ Crypto handler creation failed - handler is invalid")
                ltc_handler = None

        except ImportError as e:
            print(f"❌ Warning: crypto_handler module not available - {e}")
            print("   Deposits will work via webhook server only")
            ltc_handler = None
        except Exception as e:
            print(f"❌ Critical error initializing crypto handler: {e}")
            print("   Deposits will work via webhook server only")
            import traceback
            traceback.print_exc()
            ltc_handler = None
    else:
        print("❌ BLOCKCYPHER_API_KEY not found in environment variables")
        print("   Make sure it's properly set in Replit Secrets")
        ltc_handler = None

# BALANCE
@bot.tree.command(name="balance", description="Check your or another user's USD balance and statistics")
async def balance(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user

    user_id = str(user.id)

    # Reload balances from file to get latest updates
    global balances
    balances = load_balances()
    init_user(user_id)

    user_data = balances[user_id]
    current_balance_usd = user_data["balance"]

    # Get LTC price and calculate LTC equivalent
    ltc_price = await get_ltc_price()
    ltc_balance = current_balance_usd / ltc_price if ltc_price > 0 else 0.0

    # Create balance view with buttons
    class BalanceView(discord.ui.View):
        def __init__(self, user_id: str):
            super().__init__(timeout=300)
            self.user_id = user_id

        @discord.ui.button(label="Deposit", style=discord.ButtonStyle.success, emoji="📥")
        async def deposit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your balance!", ephemeral=True)
                return

            if not ltc_handler:
                await interaction.response.send_message("❌ Crypto system is currently unavailable.", ephemeral=True)
                return

            # Generate or get existing deposit address
            deposit_address = await ltc_handler.generate_deposit_address(self.user_id)

            if not deposit_address:
                await interaction.response.send_message("❌ Failed to generate deposit address.", ephemeral=True)
                return

            ltc_price = await get_ltc_price()

            embed = discord.Embed(
                title="💎 Your Personal Deposit Address",
                description="Send Litecoin (LTC) to this address to add funds",
                color=0x0099ff
            )
            embed.add_field(name="📍 Your LTC Address", value=f"`{deposit_address}`", inline=False)
            embed.add_field(name="💱 Current LTC Price", value=f"${ltc_price:.2f} USD", inline=True)
            embed.add_field(name="⚡ Network", value="Litecoin Mainnet", inline=True)
            embed.add_field(name="✅ Confirmations", value="1 confirmation", inline=True)
            embed.set_footer(text="Deposits are credited automatically after confirmation")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        @discord.ui.button(label="Withdraw", style=discord.ButtonStyle.danger, emoji="💸")
        async def withdraw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your balance!", ephemeral=True)
                return

            # Create modal for withdrawal
            class WithdrawModal(discord.ui.Modal, title="Withdraw LTC"):
                amount_input = discord.ui.TextInput(
                    label="Amount (USD)",
                    placeholder="Enter amount in USD (min $1.00)",
                    required=True
                )

                address_input = discord.ui.TextInput(
                    label="LTC Address",
                    placeholder="Enter your LTC address (starts with L)",
                    required=True
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    try:
                        amount_usd = float(self.amount_input.value)
                        ltc_address = self.address_input.value.strip()

                        if amount_usd < 1.0:
                            await modal_interaction.response.send_message("❌ Minimum withdrawal is $1.00 USD!", ephemeral=True)
                            return

                        user_balance = balances[str(modal_interaction.user.id)]["balance"]
                        if user_balance < amount_usd:
                            await modal_interaction.response.send_message(
                                f"❌ Insufficient balance! You have ${user_balance:.2f} USD",
                                ephemeral=True
                            )
                            return

                        if not ltc_address.startswith('L') or len(ltc_address) < 26:
                            await modal_interaction.response.send_message("❌ Invalid Litecoin address!", ephemeral=True)
                            return

                        await modal_interaction.response.defer(ephemeral=True)

                        # Process withdrawal
                        ltc_price = await get_ltc_price()
                        amount_ltc = amount_usd / ltc_price

                        if not ltc_handler:
                            await modal_interaction.followup.send("❌ Crypto system unavailable", ephemeral=True)
                            return

                        house_balance_ltc = await ltc_handler.get_house_balance()
                        if house_balance_ltc < amount_ltc:
                            await modal_interaction.followup.send("❌ Insufficient house wallet balance", ephemeral=True)
                            return

                        tx_hash = await ltc_handler.withdraw_from_house_wallet(ltc_address, amount_ltc)

                        if tx_hash:
                            balances[str(modal_interaction.user.id)]["balance"] -= amount_usd
                            balances[str(modal_interaction.user.id)]["withdrawn"] += amount_usd
                            save_balances(balances)

                            house_stats = load_house_balance()
                            house_stats['total_withdrawals'] += amount_usd
                            save_house_balance(house_stats)

                            withdrawal_id = f"WD-{int(time.time())}-{str(modal_interaction.user.id)[-6:]}"

                            embed = discord.Embed(
                                title="✅ Withdrawal Processed!",
                                color=0x00ff00
                            )
                            embed.add_field(name="💰 Amount", value=f"{amount_ltc:.8f} LTC", inline=True)
                            embed.add_field(name="💵 USD Value", value=f"${amount_usd:.2f} USD", inline=True)
                            embed.add_field(name="📍 To", value=f"`{ltc_address[:16]}...`", inline=False)
                            embed.add_field(name="🔗 TX Hash", value=f"`{tx_hash[:16]}...`", inline=False)
                            embed.set_footer(text=f"ID: {withdrawal_id}")

                            await modal_interaction.followup.send(embed=embed, ephemeral=True)
                            await log_withdraw(modal_interaction.user, amount_usd, ltc_address)
                        else:
                            await modal_interaction.followup.send("❌ Withdrawal failed", ephemeral=True)

                    except ValueError:
                        await modal_interaction.response.send_message("❌ Invalid amount!", ephemeral=True)
                    except Exception as e:
                        print(f"Withdrawal error: {e}")
                        await modal_interaction.response.send_message("❌ An error occurred", ephemeral=True)

            await interaction.response.send_modal(WithdrawModal())

    # Create enhanced balance display matching the image
    embed = discord.Embed(
        title="",
        description=f"Your balance: **${current_balance_usd:.2f}** ({ltc_balance:.8f} LTC)",
        color=0x5865F2
    )

    view = BalanceView(user_id)
    await interaction.response.send_message(embed=embed, view=view)

# CLAIM RAKEBACK
@bot.tree.command(name="claimrakeback", description="Claim your accumulated rakeback (0.5% of total wagered)")
async def claimrakeback(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    init_user(user_id)

    rakeback_earned_usd = rakeback_data[user_id]["rakeback_earned"]

    if rakeback_earned_usd <= 0:
        await interaction.response.send_message("❌ You don't have any rakeback to claim! Start gambling to earn rakeback.", ephemeral=True)
        return

    # Add rakeback to balance and reset earned rakeback
    balances[user_id]["balance"] += rakeback_earned_usd
    total_wagered_usd = rakeback_data[user_id]["total_wagered"]
    rakeback_data[user_id]["rakeback_earned"] = 0.0

    save_balances(balances)
    save_rakeback_data(rakeback_data)

    new_balance_usd = balances[user_id]["balance"]

    embed = discord.Embed(
        title="💰 Rakeback Claimed Successfully! 🎉",
        color=0x00ff00
    )
    embed.add_field(name="💸 Rakeback Claimed", value=f"${format_number(rakeback_earned_usd)} USD", inline=True)
    embed.add_field(name="🎲 Total Wagered", value=f"${format_number(total_wagered_usd)} USD", inline=True)
    embed.add_field(name="📊 Rakeback Rate", value="0.5%", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
    embed.set_footer(text="Keep gambling to earn more rakeback!")

    await interaction.response.send_message(embed=embed)

# TIP PLAYER
@bot.tree.command(name="tip", description="Tip another player some of your balance (in USD)")
async def tip(interaction: discord.Interaction, member: discord.Member, amount_str: str):
    user_id = str(interaction.user.id)
    target_id = str(member.id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse wager amount with abbreviation support
    try:
        amount_usd = parse_amount(amount_str, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers or abbreviations like 1k, 1.5M, etc.", ephemeral=True)
        return

    # Security checks
    if user_id == target_id:
        await interaction.response.send_message("❌ You cannot tip yourself!", ephemeral=True)
        return

    if member.bot:
        await interaction.response.send_message("❌ You cannot tip bots!", ephemeral=True)
        return

    if amount_usd <= 0:
        await interaction.response.send_message("❌ Tip amount must be positive!", ephemeral=True)
        return

    if amount_usd < 0.10:
        await interaction.response.send_message("❌ Minimum tip amount is $0.10 USD!", ephemeral=True)
        return

    if amount_usd > 1000:
        await interaction.response.send_message("❌ Maximum tip amount is $1000 USD!", ephemeral=True)
        return

    init_user(user_id)
    init_user(target_id)

    if balances[user_id]["balance"] < amount_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but tried to tip ${format_number(amount_usd)} USD.")
        return

    # Process the tip
    balances[user_id]["balance"] -= amount_usd
    balances[target_id]["balance"] += amount_usd
    save_balances(balances)

    # Update balances in USD for display
    sender_new_balance_usd = balances[user_id]["balance"]
    receiver_new_balance_usd = balances[target_id]["balance"]

    embed = discord.Embed(
        title="💝 Tip Sent Successfully! 🎉",
        color=0x00ff00
    )
    embed.add_field(name="👤 From", value=interaction.user.display_name, inline=True)
    embed.add_field(name="👤 To", value=member.display_name, inline=True)
    embed.add_field(name="💰 Amount", value=f"${format_number(amount_usd)} USD", inline=True)
    embed.add_field(name="💳 Your New Balance", value=f"${format_number(sender_new_balance_usd)} USD", inline=True)
    embed.add_field(name="💳 Their New Balance", value=f"${format_number(receiver_new_balance_usd)} USD", inline=True)
    embed.set_footer(text="Spread the love!")

    await interaction.response.send_message(embed=embed)

    # Log the tip transaction
    await log_tip_transaction(interaction.user, member, amount_usd)

# ADMIN: ADD BALANCE
@bot.tree.command(name="addbalance", description="Admin command to add balance to a user (in USD)")
async def addbalance(interaction: discord.Interaction, member: discord.Member, amount_str: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse amount with abbreviation support
    try:
        amount_usd = parse_amount(amount_str)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers or abbreviations like 1k, 1.5M, etc.", ephemeral=True)
        return

    if amount_usd <= 0:
        await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
        return

    user_id = str(member.id)
    init_user(user_id)
    balances[user_id]["balance"] += amount_usd
    save_balances(balances)

    embed = discord.Embed(
        title="💰 Balance Added Successfully",
        color=0x00ff00
    )
    embed.add_field(name="👤 User", value=member.display_name, inline=True)
    embed.add_field(name="💵 Amount Added", value=f"${format_number(amount_usd)} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(balances[user_id]['balance'])} USD", inline=True)

    await interaction.response.send_message(embed=embed)

    # Log the admin balance addition
    await log_admin_balance_change(interaction.user, member, amount_usd, "Addition")

# ADMIN: REMOVE BALANCE
@bot.tree.command(name="removebalance", description="Admin command to remove balance from a user (in USD)")
async def removebalance(interaction: discord.Interaction, member: discord.Member, amount_str: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse amount with abbreviation support
    try:
        amount_usd = parse_amount(amount_str)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers or abbreviations like 1k, 1.5M, etc.", ephemeral=True)
        return

    if amount_usd <= 0:
        await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
        return

    user_id = str(member.id)
    init_user(user_id)

    if balances[user_id]["balance"] < amount_usd:
        await interaction.response.send_message(f"❌ User does not have enough balance to remove ${format_number(amount_usd)} USD.", ephemeral=True)
        return

    balances[user_id]["balance"] -= amount_usd
    save_balances(balances)

    embed = discord.Embed(
        title="💰 Balance Removed Successfully",
        color=0xff6600
    )
    embed.add_field(name="👤 User", value=member.display_name, inline=True)
    embed.add_field(name="💵 Amount Removed", value=f"${format_number(amount_usd)} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(balances[user_id]['balance'])} USD", inline=True)

    await interaction.response.send_message(embed=embed)

    # Log the admin balance removal
    await log_admin_balance_change(interaction.user, member, amount_usd, "Removal")


# ADMIN: RESET STATS
@bot.tree.command(name="resetstats", description="Admin command to reset user stats or entire server stats")
async def resetstats(interaction: discord.Interaction, member: discord.Member = None, reset_all: bool = False):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if reset_all:
        # Reset all server stats
        balances.clear()
        save_balances(balances)

        # Also clear rakeback data
        rakeback_data.clear()
        save_rakeback_data(rakeback_data)

        # Also clear affiliation data
        affiliation_data.clear()
        save_affiliation_data(affiliation_data)

        embed = discord.Embed(
            title="🔄 COMPLETE SERVER RESET",
            color=0xff0000
        )
        embed.add_field(name="⚠️ Action", value="**ALL SERVER DATA WIPED**", inline=False)
        embed.add_field(name="📊 Reset", value="• All user balances\n• All user statistics\n• All rakeback data", inline=False)
        embed.set_footer(text="ENTIRE SERVER DATA HAS BEEN RESET!")

        await interaction.response.send_message(embed=embed)
        return

    if member is None:
        await interaction.response.send_message("❌ You must specify either a member or set reset_all to True!", ephemeral=True)
        return

    user_id = str(member.id)

    # Check if user exists
    if user_id not in balances:
        await interaction.response.send_message("❌ User not found in the system!", ephemeral=True)
        return

    # Reset EVERYTHING including balance
    balances[user_id] = {
        "balance": 0.0,
        "deposited": 0.0,
        "withdrawn": 0.0,
        "wagered": 0.0
    }

    # Also reset their rakeback data
    if user_id in rakeback_data:
        rakeback_data[user_id] = {"total_wagered": 0.0, "rakeback_earned": 0.0}

    # Also reset their affiliation data
    if user_id in affiliation_data:
        affiliation_data[user_id] = {"affiliated_to": None, "total_earned": 0.0}

    save_balances(balances)
    save_rakeback_data(rakeback_data)
    save_affiliation_data(affiliation_data)

    embed = discord.Embed(
        title="🔄 Complete Account Reset",
        color=0xff6600
    )
    embed.add_field(name="👤 User", value=member.display_name, inline=True)
    embed.add_field(name="💳 New Balance", value="$0.00 USD", inline=True)
    embed.add_field(name="📊 Statistics", value="All reset to 0", inline=True)
    embed.add_field(name="⚠️ Action", value="**COMPLETE ACCOUNT WIPE**", inline=False)
    embed.set_footer(text="Balance and statistics have been completely reset.")

    await interaction.response.send_message(embed=embed)

# COINFLIP
@bot.tree.command(name="coinflip", description="Flip a coin to win or lose your wager (in USD)")
async def coinflip(interaction: discord.Interaction, wager_amount: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse wager amount with abbreviation support
    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers, abbreviations like 1k, 1.5M, or 'half'/'all' for balance amounts.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but tried to wager ${format_number(wager_usd)} USD.")
        return

    # Show choice selection
    class CoinflipChoiceView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=60)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="Heads", style=discord.ButtonStyle.primary, emoji="🪙")
        async def heads_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_coinflip(interaction, "heads", self.wager_usd, self.user_id)

        @discord.ui.button(label="Tails", style=discord.ButtonStyle.primary, emoji="🟡")
        async def tails_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_coinflip(interaction, "tails", self.wager_usd, self.user_id)

    embed = discord.Embed(title="🪙 Coinflip - Choose Your Side", color=0xffaa00)
    embed.add_field(name="💰 Wager", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="🎯 Choose", value="Heads or Tails?", inline=True)
    embed.set_footer(text="Click a button to make your choice!")

    view = CoinflipChoiceView(wager_usd, user_id)
    await interaction.response.send_message(embed=embed, view=view)
    return

# Define play again view at module level
class CoinflipPlayAgainView(discord.ui.View):
    def __init__(self, wager_usd, user_id):
        super().__init__(timeout=300)
        self.wager_usd = wager_usd
        self.user_id = user_id

    @discord.ui.button(label="🪙 Play Again", style=discord.ButtonStyle.primary)
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.user_id):
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        if balances[self.user_id]["balance"] < self.wager_usd:
            current_balance_usd = balances[self.user_id]["balance"]
            await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
            return

        await start_new_coinflip_game(interaction, self.wager_usd, self.user_id)

async def start_coinflip(interaction, choice, wager_usd, user_id):

    # Generate coin flip result first
    coin_flip = random.choice(["heads", "tails"])

    # Start with animation
    embed = discord.Embed(title="🪙 Coinflip - Flipping...", color=0xffaa00)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="🎯 Your Call", value=choice.title(), inline=True)
    embed.add_field(name="⏳ Status", value="🪙 Coin is spinning...", inline=False)

    # Add the coin flip image
    coin_flip_file = None
    files = []
    if os.path.exists("attached_assets"):
        # Look for the coin flip image/gif in attached_assets
        for filename in os.listdir("attached_assets"):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                coin_flip_file = discord.File(f"attached_assets/{filename}", filename="coinflip.gif")
                embed.set_image(url="attachment://coinflip.gif")
                files.append(coin_flip_file)
                break

    try:
        await interaction.response.send_message(embed=embed, files=files)
    except discord.errors.NotFound: # Handle case where the initial response might fail due to interaction expiry
        await interaction.followup.send(embed=embed, files=files)

    # Animation frames
    frames = [
        "🪙 FLIPPING...",
        "🔄 SPINNING...",
        "🪙 TUMBLING...",
        "✨ LANDING..."
    ]

    for i, frame in enumerate(frames):
        embed.set_field_at(2, name="⏳ Status", value=f"{frame}", inline=False)
        # Keep the image during animation but remove it on the last frame
        if i == len(frames) - 1:
            # Remove image for final result to prevent loop
            embed.set_image(url=None)
        try:
            await interaction.edit_original_response(embed=embed, attachments=[]) # Remove attachments on subsequent edits
        except:
            pass # Ignore if edit fails
        await asyncio.sleep(0.8)

    # Game logic
    won = coin_flip == choice.lower()

    if won:
        winnings_usd = wager_usd * 0.80
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0x00ff00
        title = "🪙 Coinflip - YOU WON! 🎉"
        result_text = f"The coin landed on **{coin_flip}** and you called **{choice}**!"
    else:
        balances[user_id]["balance"] -= wager_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0xff0000
        title = "🪙 Coinflip - You Lost 😔"
        result_text = f"The coin landed on **{coin_flip}** but you called **{choice}**."

    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    # Create coin flip result image
    coinflip_img_path = f"coinflip_{user_id}_{time.time()}.png"
    game_img_gen.create_coinflip_image(coin_flip, choice, coinflip_img_path)

    # Final result
    coin_visual = "🪙" if coin_flip == "heads" else "🟡"
    choice_visual = "🪙" if choice.lower() == "heads" else "🟡"

    embed = discord.Embed(title=title, color=color)
    visual_text = f"""
**Your Call:** {choice.title()} {choice_visual}
**Result:** {coin_flip.title()} {coin_visual}

{coin_visual} ← **The coin landed here!**
    """
    embed.add_field(name="🃏 Coinflip Visual", value=visual_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

    files = []
    if os.path.exists(coinflip_img_path):
        files.append(discord.File(coinflip_img_path, filename="coinflip.png"))
        embed.set_image(url="attachment://coinflip.png")

    play_again_view = CoinflipPlayAgainView(wager_usd, user_id)
    await interaction.edit_original_response(embed=embed, view=play_again_view, attachments=files)

    if os.path.exists(coinflip_img_path):
        try:
            os.remove(coinflip_img_path)
        except:
            pass

async def start_new_coinflip_game(interaction, wager_usd, user_id):
    # Show choice selection again
    class CoinflipChoiceView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=60)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="Heads", style=discord.ButtonStyle.primary, emoji="🪙")
        async def heads_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_coinflip(interaction, "heads", self.wager_usd, self.user_id)

        @discord.ui.button(label="Tails", style=discord.ButtonStyle.primary, emoji="🟡")
        async def tails_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_coinflip(interaction, "tails", self.wager_usd, self.user_id)

    embed = discord.Embed(title="🪙 Coinflip - Choose Your Side", color=0xffaa00)
    embed.add_field(name="💰 Wager", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="🎯 Choose", value="Heads or Tails?", inline=True)
    embed.set_footer(text="Click a button to make your choice!")

    view = CoinflipChoiceView(wager_usd, user_id)
    await interaction.response.edit_message(embed=embed, view=view)


# DICE
@bot.tree.command(name="dice", description="Roll dice against the bot - highest roll wins! (in USD)")
async def dice(interaction: discord.Interaction, wager_amount: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse wager amount with abbreviation support
    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers, abbreviations like 1k, 1.5M, or 'half'/'all' for balance amounts.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but tried to wager ${format_number(wager_usd)} USD.")
        return

    # Roll dice for both player and bot
    player_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)

    # Start with rolling animation
    initial_embed = discord.Embed(title="🎲 Dice Battle - Rolling...", color=0xffaa00)
    initial_embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    initial_embed.add_field(name="⏳ Status", value="🎲 Rolling dice...", inline=False)

    await interaction.response.send_message(embed=initial_embed)

    # Animation frames
    roll_frames = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
    for _ in range(2):
        for frame in roll_frames:
            initial_embed.set_field_at(1, name="⏳ Status", value=f"🎲 {frame} Rolling...", inline=False)
            await interaction.edit_original_response(embed=initial_embed)
            await asyncio.sleep(0.2)

    # Determine winner
    if player_roll > bot_roll:
        # Player wins - 80% RTP
        winnings_usd = wager_usd * 0.80
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0x00ff00
        title = "🎲 Dice Battle - YOU WON! 🎉"
        result_text = f"You rolled **{player_roll}** and beat the bot's **{bot_roll}**!"
    elif player_roll < bot_roll:
        # Player loses
        balances[user_id]["balance"] -= wager_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0xff0000
        title = "🎲 Dice Battle - You Lost 😔"
        result_text = f"You rolled **{player_roll}** but bot rolled **{bot_roll}**."
    else:
        # Tie - return wager
        new_balance_usd = balances[user_id]["balance"]
        color = 0xffff00
        title = "🎲 Dice Battle - It's a Tie! 🤝"
        result_text = f"Both rolled **{player_roll}**! Wager returned."

    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    # Create dice battle image
    dice_img_path = f"dice_{user_id}_{time.time()}.png"
    try:
        game_img_gen.create_dice_battle_image(player_roll, bot_roll, dice_img_path)
    except Exception as e:
        print(f"Error creating dice image: {e}")

    # Show final result
    embed = discord.Embed(title=title, color=color)
    dice_visuals = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

    visual_text = f"""
**Your Roll:** {dice_visuals[player_roll]} **{player_roll}**
**Bot Roll:** {dice_visuals[bot_roll]} **{bot_roll}**

{result_text}
    """

    embed.add_field(name="🎲 Battle Results", value=visual_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

    # Attach image if it exists
    files = []
    if os.path.exists(dice_img_path):
        files.append(discord.File(dice_img_path, filename="dice.png"))
        embed.set_image(url="attachment://dice.png")

    # Create play again view
    class DicePlayAgainView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=300)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="🎲 Play Again", style=discord.ButtonStyle.primary)
        async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            await start_new_dice_game(interaction, self.wager_usd, self.user_id)

    async def start_new_dice_game(interaction, wager_usd, user_id):
        player_roll = random.randint(1, 6)
        bot_roll = random.randint(1, 6)

        if player_roll > bot_roll:
            winnings_usd = wager_usd * 0.80
            balances[user_id]["balance"] += winnings_usd
            new_balance_usd = balances[user_id]["balance"]
            color = 0x00ff00
            title = "🎲 Dice Battle - YOU WON! 🎉"
            result_text = f"You rolled **{player_roll}** and beat the bot's **{bot_roll}**!"
        elif player_roll < bot_roll:
            balances[user_id]["balance"] -= wager_usd
            new_balance_usd = balances[user_id]["balance"]
            color = 0xff0000
            title = "🎲 Dice Battle - You Lost 😔"
            result_text = f"You rolled **{player_roll}** but bot rolled **{bot_roll}**."
        else:
            new_balance_usd = balances[user_id]["balance"]
            color = 0xffff00
            title = "🎲 Dice Battle - It's a Tie! 🤝"
            result_text = f"Both rolled **{player_roll}**! Wager returned."

        balances[user_id]["wagered"] += wager_usd
        add_rakeback(user_id, wager_usd)
        save_balances(balances)

        dice_img_path = f"dice_{user_id}_{time.time()}.png"
        try:
            game_img_gen.create_dice_battle_image(player_roll, bot_roll, dice_img_path)
        except Exception as e:
            print(f"Error creating dice image: {e}")

        embed = discord.Embed(title=title, color=color)
        dice_visuals = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

        visual_text = f"""
**Your Roll:** {dice_visuals[player_roll]} **{player_roll}**
**Bot Roll:** {dice_visuals[bot_roll]} **{bot_roll}**

{result_text}
        """
        embed.add_field(name="🎲 Battle Results", value=visual_text, inline=False)
        embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

        files = []
        if os.path.exists(dice_img_path):
            files.append(discord.File(dice_img_path, filename="dice.png"))
            embed.set_image(url="attachment://dice.png")

        play_again_view = DicePlayAgainView(wager_usd, user_id)
        await interaction.edit_original_response(embed=embed, view=play_again_view, attachments=files)

        if os.path.exists(dice_img_path):
            try:
                os.remove(dice_img_path)
            except:
                pass

    play_again_view = DicePlayAgainView(wager_usd, user_id)
    await interaction.edit_original_response(embed=embed, view=play_again_view, attachments=files)
    if os.path.exists(dice_img_path):
        try:
            os.remove(dice_img_path)
        except:
            pass

# ROCK PAPER SCISSORS
@bot.tree.command(name="rps", description="Play Rock Paper Scissors (in USD)")
async def rps(interaction: discord.Interaction, wager_amount: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse wager amount with abbreviation support
    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers, abbreviations like 1k, 1.5M, or 'half'/'all' for balance amounts.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but tried to wager ${format_number(wager_usd)} USD.")
        return

    # Show choice selection
    class RPSChoiceView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=60)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="Rock", style=discord.ButtonStyle.secondary, emoji="🪨")
        async def rock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_rps_game(interaction, "rock", self.wager_usd, self.user_id)

        @discord.ui.button(label="Paper", style=discord.ButtonStyle.secondary, emoji="📄")
        async def paper_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_rps_game(interaction, "paper", self.wager_usd, self.user_id)

        @discord.ui.button(label="Scissors", style=discord.ButtonStyle.secondary, emoji="✂️")
        async def scissors_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_rps_game(interaction, "scissors", self.wager_usd, self.user_id)

    embed = discord.Embed(title="🤜 Rock Paper Scissors - Choose Your Move", color=0xffaa00)
    embed.add_field(name="💰 Wager", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="🎯 Choose", value="Rock, Paper, or Scissors?", inline=True)
    embed.set_footer(text="Click a button to make your choice!")

    view = RPSChoiceView(wager_usd, user_id)
    await interaction.response.send_message(embed=embed, view=view)
    return

async def start_rps_game(interaction, user_choice, wager_usd, user_id):
    choices = ["rock", "paper", "scissors"]
    bot_choice = random.choice(choices)

    # Emojis for choices
    choice_emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

    win_map = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

    if bot_choice == user_choice:
        # Tie - no money changes hands
        new_balance_usd = balances[user_id]["balance"]
        color = 0xffff00
        title = "🤝 Rock Paper Scissors - It's a Tie!"
        result_text = f"You both chose **{user_choice}** {choice_emojis[user_choice]}!"
    elif win_map[user_choice] == bot_choice:
        # Player wins - 78% RTP (22% house edge)
        winnings_usd = wager_usd * 1.78
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0x00ff00
        title = "🤜 Rock Paper Scissors - YOU WON! 🎉"
        result_text = f"Your **{user_choice}** {choice_emojis[user_choice]} beats **{bot_choice}** {choice_emojis[bot_choice]}!"
    else:
        # Player loses
        balances[user_id]["balance"] -= wager_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0xff0000
        title = "🤛 Rock Paper Scissors - You Lost 😔"
        result_text = f"**{bot_choice}** {choice_emojis[bot_choice]} beats your **{user_choice}** {choice_emojis[user_choice]}."

    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

    # Create and attach RPS image
    rps_img_path = f"rps_{user_id}_{time.time()}.png"
    files = []
    try:
        game_img_gen.create_rps_image(user_choice, bot_choice, rps_img_path)
        if os.path.exists(rps_img_path) and os.path.getsize(rps_img_path) > 0:
            files.append(discord.File(rps_img_path, filename="rps.png"))
            embed.set_image(url="attachment://rps.png")
    except Exception as e:
        print(f"Error creating RPS image: {e}")

    # Create play again view
    class RPSPlayAgainView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=300)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="🤜 Play Again", style=discord.ButtonStyle.primary)
        async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            await start_new_rps_game(interaction, self.wager_usd, self.user_id)

    async def start_new_rps_game(interaction, wager_usd, user_id):
        # Show choice selection again
        class RPSChoiceView(discord.ui.View):
            def __init__(self, wager_usd, user_id):
                super().__init__(timeout=60)
                self.wager_usd = wager_usd
                self.user_id = user_id

            @discord.ui.button(label="Rock", style=discord.ButtonStyle.secondary, emoji="🪨")
            async def rock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != int(self.user_id):
                    await interaction.response.send_message("This is not your game!", ephemeral=True)
                    return
                await start_rps_game(interaction, "rock", self.wager_usd, self.user_id)

            @discord.ui.button(label="Paper", style=discord.ButtonStyle.secondary, emoji="📄")
            async def paper_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != int(self.user_id):
                    await interaction.response.send_message("This is not your game!", ephemeral=True)
                    return
                await start_rps_game(interaction, "paper", self.wager_usd, self.user_id)

            @discord.ui.button(label="Scissors", style=discord.ButtonStyle.secondary, emoji="✂️")
            async def scissors_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != int(self.user_id):
                    await interaction.response.send_message("This is not your game!", ephemeral=True)
                    return
                await start_rps_game(interaction, "scissors", self.wager_usd, self.user_id)

        embed = discord.Embed(title="🤜 Rock Paper Scissors - Choose Your Move", color=0xffaa00)
        embed.add_field(name="💰 Wager", value=f"${format_number(wager_usd)} USD", inline=True)
        embed.add_field(name="🎯 Choose", value="Rock, Paper, or Scissors?", inline=True)
        embed.set_footer(text="Click a button to make your choice!")

        view = RPSChoiceView(wager_usd, user_id)
        await interaction.response.edit_message(embed=embed, view=view)

    play_again_view = RPSPlayAgainView(wager_usd, user_id)
    await interaction.response.send_message(embed=embed, view=play_again_view, files=files)
    if os.path.exists(rps_img_path): # Clean up image file
        try:
            os.remove(rps_img_path)
        except:
            pass

# WITHDRAW COMMAND - Manual queue-based system
@bot.tree.command(name="withdraw", description="Request a withdrawal in Litecoin (admin approval required)")
async def withdraw(interaction: discord.Interaction, amount_usd: float, ltc_address: str):
    global withdrawal_requests
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Validate amount
    if amount_usd < 1.0:
        await interaction.response.send_message("❌ Minimum withdrawal is $1.00 USD!", ephemeral=True)
        return

    # Check user balance
    user_balance = balances[user_id]["balance"]
    if user_balance < amount_usd:
        await interaction.response.send_message(f"❌ Insufficient balance! You have ${format_number(user_balance)} USD but tried to withdraw ${format_number(amount_usd)} USD.", ephemeral=True)
        return

    # Validate LTC address format (basic check - supports L, M, and ltc1 addresses)
    if not (ltc_address.startswith('L') or ltc_address.startswith('M') or ltc_address.startswith('ltc1')) or len(ltc_address) < 26:
        await interaction.response.send_message("❌ Invalid Litecoin address! Please check and try again.", ephemeral=True)
        return

    # Check if user already has a pending withdrawal
    for wd_id, wd_data in withdrawal_requests.items():
        if wd_data.get("user_id") == user_id and wd_data.get("status") == "pending":
            await interaction.response.send_message(f"❌ You already have a pending withdrawal request (ID: `{wd_id}`). Please wait for it to be processed.", ephemeral=True)
            return

    # Get current LTC price
    ltc_price = await get_ltc_price()
    amount_ltc = amount_usd / ltc_price

    # Create unique withdrawal ID
    withdrawal_id = f"WD-{int(time.time())}-{user_id[-6:]}"

    # Deduct from user balance immediately (reserve the funds)
    balances[user_id]["balance"] -= amount_usd
    save_balances(balances)

    # Add to withdrawal queue
    withdrawal_requests[withdrawal_id] = {
        "user_id": user_id,
        "username": str(interaction.user),
        "amount_usd": amount_usd,
        "amount_ltc": amount_ltc,
        "ltc_address": ltc_address,
        "status": "pending",
        "created_at": int(time.time()),
        "ltc_price_at_request": ltc_price
    }
    save_withdrawal_requests(withdrawal_requests)

    # Send confirmation to user
    embed = discord.Embed(
        title="📤 Withdrawal Request Submitted",
        description="Your withdrawal request has been added to the queue for admin approval.",
        color=0xffaa00
    )
    embed.add_field(name="🆔 Request ID", value=f"`{withdrawal_id}`", inline=True)
    embed.add_field(name="💵 Amount", value=f"${amount_usd:.2f} USD", inline=True)
    embed.add_field(name="💰 LTC Estimate", value=f"~{amount_ltc:.8f} LTC", inline=True)
    embed.add_field(name="📍 Destination", value=f"`{ltc_address}`", inline=False)
    embed.add_field(name="💳 New Balance", value=f"${format_number(balances[user_id]['balance'])} USD", inline=True)
    embed.add_field(name="⏳ Status", value="Pending Admin Approval", inline=True)
    embed.set_footer(text="An admin will process your withdrawal shortly. You will be notified when complete.")

    await interaction.response.send_message(embed=embed)

    # Log the withdrawal request
    await log_withdraw(interaction.user, amount_usd, ltc_address)



# DEPOSIT COMMAND
@bot.tree.command(name="deposit", description="Get your personal Litecoin deposit address")
async def deposit(interaction: discord.Interaction):
    global ltc_handler
    user_id = str(interaction.user.id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if not ltc_handler:
        await interaction.response.send_message("❌ Crypto system is currently unavailable. Please use manual deposits with an admin.", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        # Generate or get existing deposit address
        deposit_address = await ltc_handler.generate_deposit_address(user_id)

        if not deposit_address:
            await interaction.followup.send("❌ Failed to generate deposit address. Please try again later.", ephemeral=True)
            return

        # Get current LTC price
        ltc_price = await get_ltc_price()

        embed = discord.Embed(
            title="💎 Your Personal Deposit Address",
            description="Send Litecoin (LTC) to this address to add funds to your account",
            color=0x0099ff
        )

        embed.add_field(name="📍 Your LTC Address", value=f"`{deposit_address}`", inline=False)
        embed.add_field(name="💱 Current LTC Price", value=f"${ltc_price:.2f} USD", inline=True)
        embed.add_field(name="⚡ Network", value="Litecoin Mainnet", inline=True)
        embed.add_field(name="✅ Confirmations Required", value="1 confirmation", inline=True)

        embed.add_field(
            name="⚠️ Important Information",
            value="• Send **ONLY** Litecoin (LTC) to this address\n• Minimum deposit: $1.00 USD worth of LTC\n• Funds will be credited automatically after 1 confirmation\n• This address is unique to your account",
            inline=False
        )

        embed.add_field(
            name="🔄 Processing Time",
            value="• Unconfirmed: Detected instantly\n• Confirmed: ~2.5 minutes average\n• Credited: Automatic after confirmation",
            inline=False
        )

        embed.set_footer(text="Your deposits are monitored 24/7 and credited automatically")

        # Send to user's DM instead of server
        user = await bot.fetch_user(int(user_id))
        await user.send(embed=embed)
        await interaction.followup.send("✅ Deposit address sent to your DM!", ephemeral=True)

    except Exception as e:
        print(f"Error in deposit command: {e}")
        await interaction.followup.send("❌ An error occurred. Please try again later.", ephemeral=True)



# SLOTS
@bot.tree.command(name="slots", description="Spin the slot machine! (in USD)")
async def slots(interaction: discord.Interaction, wager_amount: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse wager amount with abbreviation support
    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers, abbreviations like 1k, 1.5M, or 'half'/'all' for balance amounts.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but tried to wager ${format_number(wager_usd)} USD.")
        return

    symbols = ["🍒", "🍋", "🍊", "🔔", "⭐"]
    result = [random.choice(symbols) for _ in range(3)]
    result_display = " ".join(result)

    if len(set(result)) == 1:
        # JACKPOT - all 3 match (reduced to 2x for higher house edge)
        multiplier = 2.0
        winnings_usd = wager_usd * multiplier
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0xffd700  # Gold
        title = "🎰 JACKPOT! 💰🎉"
        result_text = f"**{result_display}**\n\nAll three match! You won **${format_number(winnings_usd)} USD** (2x multiplier)!"
    elif len(set(result)) == 2:
        # Two symbols match (reduced to 1.0x for higher house edge)
        multiplier = 1.0
        winnings_usd = wager_usd * multiplier
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0x00ff00
        title = "🎰 Nice Win! 🎉"
        result_text = f"**{result_display}**\n\nTwo symbols match! You won **${format_number(winnings_usd)} USD** (1.0x multiplier)!"
    else:
        # No match - player loses
        balances[user_id]["balance"] -= wager_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0xff0000
        title = "🎰 No Match 😔"
        result_text = f"**{result_display}**\n\nNo symbols match. You lost **${format_number(wager_usd)} USD**."

    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)  # Add rakeback
    save_balances(balances)

    # Start with spinning animation
    embed = discord.Embed(title="🎰 Slots - Spinning...", color=0xffaa00)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="🎯 Status", value="🎰 Reels are spinning...", inline=True)
    embed.add_field(name="🎪 Reels", value="🔄 🔄 🔄", inline=False)

    await interaction.response.send_message(embed=embed)

    # Animation frames
    spin_frames = [
        "🔄 🔄 🔄",
        "🍒 🔄 🔄",
        "🍋 🍒 🔄",
        "🍊 🍋 🍒",
        "🔔 🍊 🍋",
        "⭐ 🔔 🍊",
        "🍒 ⭐ 🔔",
        "🍋 🍒 ⭐"
    ]

    for frame in spin_frames:
        embed.set_field_at(2, name="🎪 Reels", value=frame, inline=False)
        await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(0.4)

    # Show final result
    embed.set_field_at(2, name="🎪 Final Result", value=result_display, inline=False)
    await interaction.edit_original_response(embed=embed)
    await asyncio.sleep(1)

    # Create slots image
    slots_img_path = f"slots_{user_id}_{time.time()}.png"
    game_img_gen.create_slots_image(result, slots_img_path)

    # Final result embed
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
    embed.set_footer(text="Jackpot: 2x | Two Match: 1.0x")

    # Attach image
    files = []
    if os.path.exists(slots_img_path):
        files.append(discord.File(slots_img_path, filename="slots.png"))
        embed.set_image(url="attachment://slots.png")

    # Create play again view
    class SlotsPlayAgainView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=300)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="🎰 Play Again", style=discord.ButtonStyle.primary)
        async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            await start_new_slots_game(interaction, self.wager_usd, self.user_id)

    async def start_new_slots_game(interaction, wager_usd, user_id):
        symbols = ["🍒", "🍋", "🍊", "🔔", "⭐"]
        result = [random.choice(symbols) for _ in range(3)]
        result_display = " ".join(result)

        if len(set(result)) == 1:
            multiplier = 2.0
            winnings_usd = wager_usd * multiplier
            balances[user_id]["balance"] += winnings_usd
            new_balance_usd = balances[user_id]["balance"]
            color = 0xffd700
            title = "🎰 JACKPOT! 💰🎉"
            result_text = f"**{result_display}**\n\nAll three match! You won **${format_number(winnings_usd)} USD** (2x multiplier)!"
        elif len(set(result)) == 2:
            multiplier = 1.0
            winnings_usd = wager_usd * multiplier
            balances[user_id]["balance"] += winnings_usd
            new_balance_usd = balances[user_id]["balance"]
            color = 0x00ff00
            title = "🎰 Nice Win! 🎉"
            result_text = f"**{result_display}**\n\nTwo symbols match! You won **${format_number(winnings_usd)} USD** (1.0x multiplier)!"
        else:
            balances[user_id]["balance"] -= wager_usd
            new_balance_usd = balances[user_id]["balance"]
            color = 0xff0000
            title = "🎰 No Match 😔"
            result_text = f"**{result_display}**\n\nNo symbols match. You lost **${format_number(wager_usd)} USD**."

        balances[user_id]["wagered"] += wager_usd
        add_rakeback(user_id, wager_usd)
        save_balances(balances)

        embed = discord.Embed(title=title, color=color)
        embed.add_field(name="🎯 Result", value=result_text, inline=False)
        embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
        embed.set_footer(text="Jackpot: 2x | Two Match: 1.0x")

        play_again_view = SlotsPlayAgainView(wager_usd, user_id)
        await interaction.response.edit_message(embed=embed, view=play_again_view, attachments=files if files else [])

    # Clean up image
    if os.path.exists(slots_img_path):
        try:
            os.remove(slots_img_path)
        except:
            pass

# BLACKJACK SIDE BET MODAL
class SideBetModal(discord.ui.Modal, title="Side Bets"):
    perfect_pairs = discord.ui.TextInput(
        label="Perfect Pairs (pays 30:1)",
        placeholder="Enter amount (0 to skip)",
        required=False,
        default="0"
    )
    
    twentyone_plus_three = discord.ui.TextInput(
        label="21+3 (pays 100:1)",
        placeholder="Enter amount (0 to skip)",
        required=False,
        default="0"
    )

    def __init__(self, confirm_view):
        super().__init__()
        self.confirm_view = confirm_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            pp_amount = float(self.perfect_pairs.value or "0")
            tp3_amount = float(self.twentyone_plus_three.value or "0")
            
            if pp_amount < 0 or tp3_amount < 0:
                await interaction.response.send_message("❌ Side bet amounts must be positive!", ephemeral=True)
                return
            
            total_side_bets = pp_amount + tp3_amount
            user_id = self.confirm_view.user_id
            
            if balances[user_id]["balance"] < total_side_bets:
                await interaction.response.send_message(f"❌ Not enough balance for side bets! Need ${total_side_bets:.2f}", ephemeral=True)
                return
            
            self.confirm_view.side_bets = {
                "perfect_pairs": pp_amount,
                "21+3": tp3_amount
            }
            
            # Update the confirm embed to show side bets
            embed = interaction.message.embeds[0]
            side_bet_text = ""
            if pp_amount > 0:
                side_bet_text += f"Perfect Pairs: ${pp_amount:.2f}\n"
            if tp3_amount > 0:
                side_bet_text += f"21+3: ${tp3_amount:.2f}\n"
            
            if side_bet_text:
                embed.add_field(name="💎 Side Bets", value=side_bet_text, inline=False)
            
            await interaction.response.edit_message(embed=embed)
            
        except ValueError:
            await interaction.response.send_message("❌ Invalid amount format!", ephemeral=True)

# BLACKJACK CONFIRM BET VIEW
class BlackjackConfirmView(discord.ui.View):
    def __init__(self, wager_usd, user_id, deck, player_hand, dealer_hand):
        super().__init__(timeout=60)
        self.wager_usd = wager_usd
        self.user_id = user_id
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.side_bets = {"perfect_pairs": 0, "21+3": 0}

    @discord.ui.button(label="✅ Confirm Bet", style=discord.ButtonStyle.success, row=0)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.user_id):
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        
        await self.start_game(interaction)

    @discord.ui.button(label="💎 Side Bets", style=discord.ButtonStyle.primary, row=0)
    async def side_bet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.user_id):
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        
        await interaction.response.send_modal(SideBetModal(self))

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.user_id):
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        
        # Refund the wager
        balances[self.user_id]["balance"] += self.wager_usd
        balances[self.user_id]["wagered"] -= self.wager_usd
        save_balances(balances)
        
        await interaction.response.edit_message(
            content="❌ Bet cancelled. Wager refunded.",
            embed=None,
            view=None
        )

    async def start_game(self, interaction: discord.Interaction):
        # Deduct side bets
        total_side_bets = self.side_bets["perfect_pairs"] + self.side_bets["21+3"]
        if total_side_bets > 0:
            balances[self.user_id]["balance"] -= total_side_bets
            balances[self.user_id]["wagered"] += total_side_bets
            add_rakeback(self.user_id, total_side_bets)
            save_balances(balances)

        # Check for immediate blackjacks
        player_blackjack = card_generator.hand_value(self.player_hand) == 21
        dealer_blackjack = card_generator.hand_value(self.dealer_hand) == 21

        # Calculate side bet payouts
        side_bet_winnings = 0
        side_bet_results = ""
        
        # Perfect Pairs check
        if self.side_bets["perfect_pairs"] > 0:
            if self.player_hand[0][0] == self.player_hand[1][0]:
                if self.player_hand[0][1] == self.player_hand[1][1]:
                    # Perfect pair (same rank and suit)
                    payout = self.side_bets["perfect_pairs"] * 30
                    side_bet_winnings += payout
                    side_bet_results += f"🎉 Perfect Pair! Won ${payout:.2f}\n"
                else:
                    # Colored pair (same rank and color)
                    payout = self.side_bets["perfect_pairs"] * 12
                    side_bet_winnings += payout
                    side_bet_results += f"✅ Colored Pair! Won ${payout:.2f}\n"
            else:
                side_bet_results += f"❌ No pair\n"
        
        # 21+3 check (three card poker with first 2 player cards + dealer up card)
        if self.side_bets["21+3"] > 0:
            three_cards = [self.player_hand[0], self.player_hand[1], self.dealer_hand[0]]
            ranks = [c[0] for c in three_cards]
            suits = [c[1] for c in three_cards]
            
            # Check for suited trips (3 of same rank and suit)
            if len(set(ranks)) == 1 and len(set(suits)) == 1:
                payout = self.side_bets["21+3"] * 100
                side_bet_winnings += payout
                side_bet_results += f"🎉 Suited Trips! Won ${payout:.2f}\n"
            # Check for straight flush
            elif len(set(suits)) == 1:
                payout = self.side_bets["21+3"] * 40
                side_bet_winnings += payout
                side_bet_results += f"🎉 Straight Flush! Won ${payout:.2f}\n"
            # Check for three of a kind
            elif len(set(ranks)) == 1:
                payout = self.side_bets["21+3"] * 30
                side_bet_winnings += payout
                side_bet_results += f"🎉 Three of a Kind! Won ${payout:.2f}\n"
            else:
                side_bet_results += f"❌ No 21+3 win\n"
        
        if side_bet_winnings > 0:
            balances[self.user_id]["balance"] += side_bet_winnings
            save_balances(balances)

        if player_blackjack or dealer_blackjack:
            # Handle blackjack scenarios immediately
            if player_blackjack and dealer_blackjack:
                balances[self.user_id]["balance"] += self.wager_usd
                new_balance_usd = balances[self.user_id]["balance"]
                color = 0xffff00
                title = "🃏 Blackjack - Push! 🤝"
                result_text = "Both you and the dealer have Blackjack!"
            elif player_blackjack:
                winnings_usd = self.wager_usd * 2.5
                balances[self.user_id]["balance"] += winnings_usd
                new_balance_usd = balances[self.user_id]["balance"]
                color = 0x00ff00
                title = "🃏 BLACKJACK! 🎉"
                result_text = f"You got Blackjack! Won ${winnings_usd:.2f} USD (1.5x payout)!"
            else:
                new_balance_usd = balances[self.user_id]["balance"]
                color = 0xff0000
                title = "🃏 Blackjack - Dealer Wins 😔"
                result_text = "Dealer has Blackjack!"

            save_balances(balances)

            embed = discord.Embed(title=title, color=color)
            embed.add_field(name="🃏 Your Hand", value=f"{card_generator.format_hand(self.player_hand)} = {card_generator.hand_value(self.player_hand)}", inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand)} = {card_generator.hand_value(self.dealer_hand)}", inline=True)
            embed.add_field(name="🎯 Result", value=result_text, inline=False)
            if side_bet_results:
                embed.add_field(name="💎 Side Bets", value=side_bet_results, inline=False)
            embed.add_field(name="💰 Wagered", value=f"${self.wager_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

            await interaction.response.edit_message(embed=embed, view=None)
            return

        # Create game image
        initial_img = f"initial_blackjack_{self.user_id}.png"
        try:
            card_generator.save_blackjack_game_image([self.player_hand], self.dealer_hand, initial_img, 0, hide_dealer_first=True)
        except Exception as e:
            print(f"Error creating initial blackjack image: {e}")

        # Create game embed
        embed = discord.Embed(title="🃏 Blackjack - Your Turn", color=0x0099ff)
        embed.add_field(name="🃏 Your Hand", value=f"{card_generator.format_hand(self.player_hand)} = **{card_generator.hand_value(self.player_hand)}**", inline=True)
        embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand, hide_first=True)} = **?**", inline=True)
        embed.add_field(name="💰 Wager", value=f"${self.wager_usd:.2f} USD", inline=True)
        if side_bet_results:
            embed.add_field(name="💎 Side Bets", value=side_bet_results, inline=False)
        embed.set_footer(text="Hit: take card | Stand: keep hand | Double: double bet + 1 card | Split: split pairs")

        files = []
        if os.path.exists(initial_img):
            files.append(discord.File(initial_img, filename="blackjack_start.png"))
            embed.set_image(url="attachment://blackjack_start.png")

        view = BlackjackView([self.player_hand], self.dealer_hand, self.deck, self.wager_usd, self.user_id, 0)

        try:
            await interaction.response.edit_message(embed=embed, view=view, attachments=files)
            if os.path.exists(initial_img):
                try:
                    os.remove(initial_img)
                except:
                    pass
        except Exception as e:
            await interaction.response.edit_message(embed=embed, view=view)

# BLACKJACK VIEW CLASS
class BlackjackView(discord.ui.View):
    def __init__(self, player_hands, dealer_hand, deck, wager_usd, user_id, current_hand_index=0):
        super().__init__(timeout=300)
        self.player_hands = player_hands  # List of hands for split support
        self.dealer_hand = dealer_hand
        self.deck = deck
        self.wager_usd = wager_usd
        self.user_id = user_id
        self.current_hand_index = current_hand_index
        self.game_over = False
        self.split_count = len(player_hands) - 1
        
        # Disable split button if already split or can't split
        if len(player_hands) > 1 or len(player_hands[0]) != 2 or player_hands[0][0][0] != player_hands[0][1][0]:
            for item in self.children:
                if hasattr(item, 'label') and item.label == "✂️ Split":
                    item.disabled = True

    @discord.ui.button(label="🃏 Hit", style=discord.ButtonStyle.primary)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.user_id) or self.game_over:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        current_hand = self.player_hands[self.current_hand_index]
        current_hand.append(self.deck.pop())
        player_value = card_generator.hand_value(current_hand)

        # Create updated image
        game_img = f"blackjack_{self.user_id}_{time.time()}.png"
        try:
            card_generator.save_blackjack_game_image(self.player_hands, self.dealer_hand, game_img, self.current_hand_index, hide_dealer_first=True)
        except Exception as e:
            print(f"Error creating blackjack image: {e}")

        if player_value > 21:
            # Busted this hand
            if self.current_hand_index < len(self.player_hands) - 1:
                # Move to next hand
                self.current_hand_index += 1
                embed = discord.Embed(title=f"🃏 Blackjack - Hand {self.current_hand_index} Busted!", color=0xff6600)
                embed.add_field(name=f"🃏 Hand {self.current_hand_index}", value=f"{card_generator.format_hand(current_hand)} = **{player_value}** (BUST)", inline=True)
                embed.add_field(name=f"🃏 Next Hand", value=f"{card_generator.format_hand(self.player_hands[self.current_hand_index])} = **{card_generator.hand_value(self.player_hands[self.current_hand_index])}**", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand, hide_first=True)} = **?**", inline=True)
                embed.set_footer(text=f"Playing hand {self.current_hand_index + 1} of {len(self.player_hands)}")
                
                files = []
                if os.path.exists(game_img):
                    files.append(discord.File(game_img, filename="blackjack.png"))
                    embed.set_image(url="attachment://blackjack.png")
                
                await interaction.response.edit_message(embed=embed, view=self, attachments=files)
                if os.path.exists(game_img):
                    try:
                        os.remove(game_img)
                    except:
                        pass
            else:
                # All hands done
                await self.finish_game(interaction)
        elif player_value == 21:
            # Auto-stand on 21
            if self.current_hand_index < len(self.player_hands) - 1:
                self.current_hand_index += 1
                embed = discord.Embed(title=f"🃏 Blackjack - Hand {self.current_hand_index} stands at 21!", color=0x00ff00)
                embed.add_field(name=f"🃏 Previous Hand", value=f"{card_generator.format_hand(current_hand)} = **21**", inline=True)
                embed.add_field(name=f"🃏 Current Hand", value=f"{card_generator.format_hand(self.player_hands[self.current_hand_index])} = **{card_generator.hand_value(self.player_hands[self.current_hand_index])}**", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand, hide_first=True)} = **?**", inline=True)
                
                files = []
                if os.path.exists(game_img):
                    files.append(discord.File(game_img, filename="blackjack.png"))
                    embed.set_image(url="attachment://blackjack.png")
                
                await interaction.response.edit_message(embed=embed, view=self, attachments=files)
                if os.path.exists(game_img):
                    try:
                        os.remove(game_img)
                    except:
                        pass
            else:
                await self.finish_game(interaction)
        else:
            embed = discord.Embed(title=f"🃏 Blackjack - Hand {self.current_hand_index + 1}", color=0x0099ff)
            embed.add_field(name=f"🃏 Your Hand {self.current_hand_index + 1}", value=f"{card_generator.format_hand(current_hand)} = **{player_value}**", inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand, hide_first=True)} = **?**", inline=True)
            embed.add_field(name="💰 Wager", value=f"${self.wager_usd:.2f} USD", inline=True)
            if len(self.player_hands) > 1:
                embed.set_footer(text=f"Playing hand {self.current_hand_index + 1} of {len(self.player_hands)}")

            files = []
            if os.path.exists(game_img):
                files.append(discord.File(game_img, filename="blackjack.png"))
                embed.set_image(url="attachment://blackjack.png")

            await interaction.response.edit_message(embed=embed, view=self, attachments=files)
            if os.path.exists(game_img):
                try:
                    os.remove(game_img)
                except:
                    pass

    @discord.ui.button(label="✋ Stand", style=discord.ButtonStyle.secondary)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.user_id) or self.game_over:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        if self.current_hand_index < len(self.player_hands) - 1:
            # Move to next hand
            self.current_hand_index += 1
            
            game_img = f"blackjack_{self.user_id}_{time.time()}.png"
            try:
                card_generator.save_blackjack_game_image(self.player_hands, self.dealer_hand, game_img, self.current_hand_index, hide_dealer_first=True)
            except Exception as e:
                print(f"Error creating blackjack image: {e}")
            
            embed = discord.Embed(title=f"🃏 Blackjack - Hand {self.current_hand_index + 1}", color=0x0099ff)
            embed.add_field(name=f"🃏 Your Hand {self.current_hand_index + 1}", value=f"{card_generator.format_hand(self.player_hands[self.current_hand_index])} = **{card_generator.hand_value(self.player_hands[self.current_hand_index])}**", inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand, hide_first=True)} = **?**", inline=True)
            embed.set_footer(text=f"Playing hand {self.current_hand_index + 1} of {len(self.player_hands)}")
            
            files = []
            if os.path.exists(game_img):
                files.append(discord.File(game_img, filename="blackjack.png"))
                embed.set_image(url="attachment://blackjack.png")
            
            await interaction.response.edit_message(embed=embed, view=self, attachments=files)
            if os.path.exists(game_img):
                try:
                    os.remove(game_img)
                except:
                    pass
        else:
            await self.finish_game(interaction)

    @discord.ui.button(label="⬆️ Double Down", style=discord.ButtonStyle.success)
    async def double_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.user_id) or self.game_over:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        if balances[self.user_id]["balance"] < self.wager_usd:
            await interaction.response.send_message(f"❌ Not enough balance to double down! You need ${self.wager_usd:.2f} more.", ephemeral=True)
            return

        balances[self.user_id]["balance"] -= self.wager_usd
        balances[self.user_id]["wagered"] += self.wager_usd
        add_rakeback(self.user_id, self.wager_usd)
        self.wager_usd *= 2
        save_balances(balances)

        current_hand = self.player_hands[self.current_hand_index]
        current_hand.append(self.deck.pop())

        if self.current_hand_index < len(self.player_hands) - 1:
            self.current_hand_index += 1
            
            game_img = f"blackjack_{self.user_id}_{time.time()}.png"
            try:
                card_generator.save_blackjack_game_image(self.player_hands, self.dealer_hand, game_img, self.current_hand_index, hide_dealer_first=True)
            except Exception as e:
                print(f"Error creating blackjack image: {e}")
            
            embed = discord.Embed(title=f"🃏 Blackjack - Doubled Down! Next Hand", color=0x0099ff)
            embed.add_field(name=f"🃏 Your Hand {self.current_hand_index + 1}", value=f"{card_generator.format_hand(self.player_hands[self.current_hand_index])} = **{card_generator.hand_value(self.player_hands[self.current_hand_index])}**", inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand, hide_first=True)} = **?**", inline=True)
            
            files = []
            if os.path.exists(game_img):
                files.append(discord.File(game_img, filename="blackjack.png"))
                embed.set_image(url="attachment://blackjack.png")
            
            await interaction.response.edit_message(embed=embed, view=self, attachments=files)
            if os.path.exists(game_img):
                try:
                    os.remove(game_img)
                except:
                    pass
        else:
            await self.finish_game(interaction)

    @discord.ui.button(label="✂️ Split", style=discord.ButtonStyle.primary)
    async def split_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.user_id) or self.game_over:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        current_hand = self.player_hands[self.current_hand_index]
        
        # Check if can split
        if len(current_hand) != 2 or current_hand[0][0] != current_hand[1][0]:
            await interaction.response.send_message("❌ You can only split pairs!", ephemeral=True)
            return

        if balances[self.user_id]["balance"] < self.wager_usd:
            await interaction.response.send_message(f"❌ Not enough balance to split! You need ${self.wager_usd:.2f} more.", ephemeral=True)
            return

        # Deduct additional wager for split
        balances[self.user_id]["balance"] -= self.wager_usd
        balances[self.user_id]["wagered"] += self.wager_usd
        add_rakeback(self.user_id, self.wager_usd)
        save_balances(balances)

        # Split the hand
        new_hand = [current_hand.pop()]
        current_hand.append(self.deck.pop())
        new_hand.append(self.deck.pop())
        
        self.player_hands.insert(self.current_hand_index + 1, new_hand)
        
        # Disable split button
        for item in self.children:
            if hasattr(item, 'label') and item.label == "✂️ Split":
                item.disabled = True

        game_img = f"blackjack_{self.user_id}_{time.time()}.png"
        try:
            card_generator.save_blackjack_game_image(self.player_hands, self.dealer_hand, game_img, self.current_hand_index, hide_dealer_first=True)
        except Exception as e:
            print(f"Error creating blackjack image: {e}")

        embed = discord.Embed(title="🃏 Blackjack - Hand Split! ✂️", color=0x0099ff)
        embed.add_field(name=f"🃏 Hand 1", value=f"{card_generator.format_hand(current_hand)} = **{card_generator.hand_value(current_hand)}**", inline=True)
        embed.add_field(name=f"🃏 Hand 2", value=f"{card_generator.format_hand(new_hand)} = **{card_generator.hand_value(new_hand)}**", inline=True)
        embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand, hide_first=True)} = **?**", inline=True)
        embed.add_field(name="💰 Total Wager", value=f"${self.wager_usd * 2:.2f} USD", inline=True)
        embed.set_footer(text=f"Playing hand 1 of {len(self.player_hands)}")

        files = []
        if os.path.exists(game_img):
            files.append(discord.File(game_img, filename="blackjack.png"))
            embed.set_image(url="attachment://blackjack.png")

        await interaction.response.edit_message(embed=embed, view=self, attachments=files)
        if os.path.exists(game_img):
            try:
                os.remove(game_img)
            except:
                pass

    async def finish_game(self, interaction: discord.Interaction):
        self.game_over = True
        for item in self.children:
            item.disabled = True

        # Dealer draws
        while card_generator.hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

        dealer_value = card_generator.hand_value(self.dealer_hand)

        # Calculate results for each hand
        total_winnings = 0
        results_text = ""
        
        for i, hand in enumerate(self.player_hands):
            player_value = card_generator.hand_value(hand)
            
            if player_value > 21:
                results_text += f"Hand {i+1}: **{player_value}** - BUST 💥\n"
            elif dealer_value > 21:
                winnings = self.wager_usd * 2
                total_winnings += winnings
                results_text += f"Hand {i+1}: **{player_value}** - WIN (Dealer bust) 🎉\n"
            elif player_value > dealer_value:
                winnings = self.wager_usd * 2
                total_winnings += winnings
                results_text += f"Hand {i+1}: **{player_value}** - WIN 🎉\n"
            elif player_value < dealer_value:
                results_text += f"Hand {i+1}: **{player_value}** - LOSE 😔\n"
            else:
                balances[self.user_id]["balance"] += self.wager_usd
                results_text += f"Hand {i+1}: **{player_value}** - PUSH 🤝\n"

        if total_winnings > 0:
            balances[self.user_id]["balance"] += total_winnings
            color = 0x00ff00
            title = "🃏 Blackjack - YOU WIN! 🎉"
        elif total_winnings == 0 and "PUSH" in results_text:
            color = 0xffff00
            title = "🃏 Blackjack - Push! 🤝"
        else:
            color = 0xff0000
            title = "🃏 Blackjack - Dealer Wins 😔"

        save_balances(balances)
        new_balance_usd = balances[self.user_id]["balance"]

        # Create final image with dealer cards revealed
        final_img = f"blackjack_final_{self.user_id}_{time.time()}.png"
        try:
            card_generator.save_blackjack_game_image(self.player_hands, self.dealer_hand, final_img, 0, hide_dealer_first=False)
        except Exception as e:
            print(f"Error creating final blackjack image: {e}")

        embed = discord.Embed(title=title, color=color)
        embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand)} = **{dealer_value}**", inline=False)
        embed.add_field(name="🎯 Results", value=results_text, inline=False)
        embed.add_field(name="💰 Total Wagered", value=f"${self.wager_usd * len(self.player_hands):.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

        files = []
        if os.path.exists(final_img):
            files.append(discord.File(final_img, filename="blackjack_final.png"))
            embed.set_image(url="attachment://blackjack_final.png")

        try:
            await interaction.response.edit_message(embed=embed, view=self, attachments=files)
        except:
            await interaction.response.defer()
            await interaction.followup.send(embed=embed, view=self, files=files)
        
        if os.path.exists(final_img):
            try:
                os.remove(final_img)
            except:
                pass

# BLACKJACK
@bot.tree.command(name="blackjack", description="Play Blackjack against the dealer (in USD)")
async def blackjack(interaction: discord.Interaction, wager_amount: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse wager amount with abbreviation support
    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers, abbreviations like 1k, 1.5M, or 'half'/'all' for balance amounts.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but tried to wager ${format_number(wager_usd)} USD.")
        return

    # Deduct wager at the start
    balances[user_id]["balance"] -= wager_usd
    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    # Create deck
    suits = ['♠️', '♥️', '♦️', '♣️']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    deck = [(rank, suit) for suit in suits for rank in ranks]
    random.shuffle(deck)

    # Deal initial cards
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    # Show confirm bet screen (without revealing cards)
    embed = discord.Embed(title="🃏 Blackjack - Confirm Your Bet", color=0x0099ff)
    embed.add_field(name="💰 Main Bet", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 Current Balance", value=f"${format_number(balances[user_id]['balance'])} USD", inline=True)
    embed.add_field(name="🎲 Game Ready", value="Cards will be dealt after confirmation", inline=True)
    embed.add_field(name="ℹ️ Game Rules", value="• Blackjack pays 3:2\n• Dealer stands on 17\n• Can split pairs\n• Can double down", inline=False)
    embed.add_field(name="💎 Side Bets Available", value="• Perfect Pairs (30:1)\n• 21+3 (100:1)", inline=False)
    embed.set_footer(text="Click 'Side Bets' to add side bets or 'Confirm Bet' to start!")

    view = BlackjackConfirmView(wager_usd, user_id, deck, player_hand, dealer_hand)
    await interaction.response.send_message(embed=embed, view=view)

# MINES
@bot.tree.command(name="mines", description="Play Mines - find diamonds while avoiding mines! (in USD)")
async def mines(interaction: discord.Interaction, wager_amount: str, mine_count: int):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse wager amount with abbreviation support
    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers, abbreviations like 1k, 1.5M, or 'half'/'all' for balance amounts.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if mine_count < 1 or mine_count > 24:
        await interaction.response.send_message("❌ Mine count must be between 1-24!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but tried to wager ${format_number(wager_usd)} USD.")
        return

    # Deduct the wager when starting the game
    balances[user_id]["balance"] -= wager_usd
    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    # Generate mine positions (0-24 for a 5x5 grid)
    mine_positions = set(random.sample(range(25), min(mine_count, 24)))

    def get_multiplier(diamonds_found, total_mines):
        if diamonds_found == 0:
            return 0

        safe_tiles = 25 - total_mines
        multiplier = 1.0
        for i in range(diamonds_found):
            remaining_safe = safe_tiles - i
            remaining_total = 25 - i
            multiplier *= remaining_total / remaining_safe

        # Apply house edge (reduce by ~20%)
        multiplier *= 0.80
        return round(multiplier, 2)

    def get_difficulty_name(paths_count):
        if paths_count == 2:
            return "Easy"
        elif paths_count == 3 and correct_count == 2:
            return "Medium"
        else:
            return "Hard"

    class MinesView(discord.ui.View):
        def __init__(self, mine_positions, wager_usd, user_id, mine_count):
            super().__init__(timeout=300)
            self.mine_positions = mine_positions
            self.wager_usd = wager_usd
            self.user_id = user_id
            self.mine_count = mine_count
            self.revealed_tiles = set()
            self.diamonds_found = 0
            self.game_over = False
            self.current_multiplier = 1.0

            for i in range(25):
                button = discord.ui.Button(
                    label="⬜",
                    style=discord.ButtonStyle.secondary,
                    row=i // 5,
                    custom_id=f"tile_{i}"
                )
                button.callback = self.tile_callback
                self.add_item(button)

        async def tile_callback(self, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            tile_pos = int(interaction.data['custom_id'].split('_')[1])

            if tile_pos in self.revealed_tiles:
                if tile_pos not in self.mine_positions and self.diamonds_found > 0:
                    await self.cashout_callback(interaction)
                    return
                else:
                    await interaction.response.send_message("You've already revealed this tile!", ephemeral=True)
                    return

            self.revealed_tiles.add(tile_pos)

            for item in self.children:
                if hasattr(item, 'custom_id') and item.custom_id == f"tile_{tile_pos}":
                    if tile_pos in self.mine_positions:
                        # Hit a mine - game over
                        item.label = "💣"
                        item.style = discord.ButtonStyle.danger
                        item.disabled = True

                        # Reveal all mines
                        for mine_pos in self.mine_positions:
                            for mine_item in self.children:
                                if hasattr(mine_item, 'custom_id') and mine_item.custom_id == f"tile_{mine_pos}":
                                    mine_item.label = "💣"
                                    mine_item.style = discord.ButtonStyle.danger
                                    mine_item.disabled = True

                        for child in self.children:
                            child.disabled = True

                        self.game_over = True
                        new_balance_usd = balances[self.user_id]["balance"]

                        embed = discord.Embed(title="💣 Mines - BOOM! 💥", color=0xff0000)
                        embed.add_field(name="💎 Diamonds Found", value=str(self.diamonds_found), inline=True)
                        embed.add_field(name="💣 Mines", value=str(self.mine_count), inline=True)
                        embed.add_field(name="💸 Result", value=f"You hit a mine! Lost ${self.wager_usd:.2f} USD", inline=True)
                        embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

                        await interaction.response.edit_message(embed=embed, view=self)
                        return
                    else:
                        # Found a diamond
                        item.label = "💎"
                        item.style = discord.ButtonStyle.success
                        item.disabled = False
                        self.diamonds_found += 1
                        self.current_multiplier = get_multiplier(self.diamonds_found, self.mine_count)
                    break

            # Check if all safe tiles are revealed
            safe_tiles = 25 - self.mine_count
            if self.diamonds_found == safe_tiles:
                self.game_over = True
                for child in self.children:
                    child.disabled = True

                winnings_usd = self.wager_usd * self.current_multiplier
                balances[self.user_id]["balance"] += winnings_usd
                save_balances(balances)

                new_balance_usd = balances[self.user_id]["balance"]

                embed = discord.Embed(title="💎 Mines - PERFECT GAME! 🎉", color=0xffd700)
                embed.add_field(name="💎 Diamonds Found", value=f"{self.diamonds_found}/{safe_tiles}", inline=True)
                embed.add_field(name="💣 Mines", value=str(self.mine_count), inline=True)
                embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
                embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
                embed.set_footer(text="Perfect Game Bonus!")

                self.clear_items()
                await interaction.response.edit_message(embed=embed)
                return

            current_winnings_usd = self.wager_usd * self.current_multiplier

            embed = discord.Embed(title="💎 Minesweeper", color=0x0099ff)
            embed.add_field(name="💰 Bet", value=f"${self.wager_usd:.2f} USD", inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
            embed.add_field(name="💎 Current winnings", value=f"${format_number(current_winnings_usd)} USD", inline=True)
            embed.add_field(name="💎 Diamonds Found", value=str(self.diamonds_found), inline=True)
            embed.add_field(name="💣 Mines Hidden", value=str(self.mine_count), inline=True)
            embed.add_field(name="⬜ Tiles Left", value=str(25 - len(self.revealed_tiles)), inline=True)
            embed.set_footer(text="Click tiles to find diamonds! Click any revealed diamond to cash out.")

            await interaction.response.edit_message(embed=embed, view=self)

        async def cashout_callback(self, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if self.diamonds_found == 0:
                await interaction.response.send_message("You need to find at least one diamond before cashing out!", ephemeral=True)
                return

            self.game_over = True
            for child in self.children:
                child.disabled = True

            winnings_usd = self.wager_usd * self.current_multiplier
            balances[self.user_id]["balance"] += winnings_usd
            save_balances(balances)

            new_balance_usd = balances[self.user_id]["balance"]

            embed = discord.Embed(title="💰 Mines - Cashed Out! 🎉", color=0x00ff00)
            embed.add_field(name="💎 Diamonds Found", value=str(self.diamonds_found), inline=True)
            embed.add_field(name="💣 Mines", value=str(self.mine_count), inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
            embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
            embed.set_footer(text="Smart move!")

            # Create play again view
            class MinesPlayAgainView(discord.ui.View):
                def __init__(self, wager_usd, mine_count, user_id):
                    super().__init__(timeout=300)
                    self.wager_usd = wager_usd
                    self.mine_count = mine_count
                    self.user_id = user_id

                @discord.ui.button(label="💎 Play Again", style=discord.ButtonStyle.primary)
                async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != int(self.user_id):
                        await interaction.response.send_message("This is not your game!", ephemeral=True)
                        return

                    if balances[self.user_id]["balance"] < self.wager_usd:
                        current_balance_usd = balances[self.user_id]["balance"]
                        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                        return

                    await start_new_mines_game(interaction, self.wager_usd, self.mine_count, self.user_id)

            async def start_new_mines_game(interaction, wager_usd, mine_count, user_id):
                # Deduct the wager when starting the game
                balances[user_id]["balance"] -= wager_usd
                balances[user_id]["wagered"] += wager_usd
                add_rakeback(user_id, wager_usd)
                save_balances(balances)

                # Generate mine positions
                mine_positions = set(random.sample(range(25), min(mine_count, 24)))

                # Create initial embed
                embed = discord.Embed(title="💎 Minesweeper", color=0x0099ff)
                embed.add_field(name="💰 Bet", value=f"${wager_usd:.2f} USD", inline=True)
                embed.add_field(name="📈 Multiplier", value="1.00x", inline=True)
                embed.add_field(name="💎 Current winnings", value="NONE", inline=True)
                embed.add_field(name="💎 Diamonds Found", value="0", inline=True)
                embed.add_field(name="💣 Mines Hidden", value=str(mine_count), inline=True)
                embed.add_field(name="⬜ Tiles Left", value="25", inline=True)
                embed.set_footer(text="Click tiles to find diamonds! Click any revealed diamond to cash out.")

                view = MinesView(mine_positions, wager_usd, user_id, mine_count)
                await interaction.response.edit_message(embed=embed, view=view)

            play_again_view = MinesPlayAgainView(self.wager_usd, self.mine_count, self.user_id)
            await interaction.response.edit_message(embed=embed, view=play_again_view)

    # Initial embed
    embed = discord.Embed(title="💎 Minesweeper", color=0x0099ff)
    embed.add_field(name="💰 Bet", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="📈 Multiplier", value="1.00x", inline=True)
    embed.add_field(name="💎 Current winnings", value="NONE", inline=True)
    embed.add_field(name="💎 Diamonds Found", value="0", inline=True)
    embed.add_field(name="💣 Mines Hidden", value=str(mine_count), inline=True)
    embed.add_field(name="⬜ Tiles Left", value="25", inline=True)
    embed.set_footer(text="Click tiles to find diamonds! Click any revealed diamond to cash out.")

    view = MinesView(mine_positions, wager_usd, user_id, mine_count)
    await interaction.response.send_message(embed=embed, view=view)

# TOWERS
@bot.tree.command(name="towers", description="Climb towers by choosing the correct path! (in USD)")
async def towers(interaction: discord.Interaction, wager_amount: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse wager amount with abbreviation support
    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers, abbreviations like 1k, 1.5M, or 'half'/'all' for balance amounts.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but tried to wager ${format_number(wager_usd)} USD.")
        return

    # Show choice selection
    class TowersDifficultyView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=60)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="Easy (4 paths, 3 correct)", style=discord.ButtonStyle.success, emoji="🟢")
        async def easy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_towers_game(interaction, "easy", self.wager_usd, self.user_id)

        @discord.ui.button(label="Medium (3 paths, 2 correct)", style=discord.ButtonStyle.primary, emoji="🟡")
        async def medium_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_towers_game(interaction, "medium", self.wager_usd, self.user_id)

        @discord.ui.button(label="Hard (2 paths, 1 correct)", style=discord.ButtonStyle.danger, emoji="🔴")
        async def hard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_towers_game(interaction, "hard", self.wager_usd, self.user_id)

    embed = discord.Embed(title="🏗️ Towers - Choose Difficulty", color=0x0099ff)
    embed.add_field(name="💰 Wager", value=f"${format_number(wager_usd)} USD", inline=False)
    embed.add_field(name="🟢 Easy", value="4 paths, 3 correct", inline=True)
    embed.add_field(name="🟡 Medium", value="3 paths, 2 correct", inline=True)
    embed.add_field(name="🔴 Hard", value="2 paths, 1 correct", inline=True)
    embed.set_footer(text="Select your difficulty level!")

    view = TowersDifficultyView(wager_usd, user_id)
    await interaction.response.send_message(embed=embed, view=view)
    return

async def start_towers_game(interaction, difficulty, wager_usd, user_id):
    # Deduct the wager when starting the game
    balances[user_id]["balance"] -= wager_usd
    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    # Set difficulty parameters based on selection
    if difficulty.lower() == "easy":
        paths_count = 4
        correct_count = 3
    elif difficulty.lower() == "medium":
        paths_count = 3
        correct_count = 2
    else:  # hard
        paths_count = 2
        correct_count = 1

    # Generate tower structure - 9 levels, each with 'paths_count' number of paths
    tower_structure = []
    for level in range(9):
        correct_paths = random.sample(range(paths_count), correct_count)
        tower_structure.append(correct_paths)

    def get_tower_multiplier(level, paths_count, correct_count):
        base_multiplier = 1.0
        # Adjust multiplier based on difficulty (more paths/fewer correct = higher potential multiplier)
        difficulty_factor = (paths_count / correct_count) * 0.1
        level_bonus = level * (0.10 + difficulty_factor)
        return round(base_multiplier + level_bonus, 2)

    def get_difficulty_name(paths_count):
        if paths_count == 2:
            return "Easy"
        elif paths_count == 3 and correct_count == 2:
            return "Medium"
        else:
            return "Hard"

    # Create initial embed with emoji rows
    difficulty_name = get_difficulty_name(paths_count)

    # Build the tower display
    tower_display = ""
    for row in range(9, 0, -1):
        row_index = row - 1

        if row_index < len(tower_structure): # Check if this row is already played
            if row_index < len(path_history): # Check if the player has made a choice for this row
                chosen_path = path_history[row_index]
                correct_paths = tower_structure[row_index]

                row_str = f"**Row {row}:** "
                for path in range(paths_count):
                    if path == chosen_path and path in correct_paths:
                        row_str += "✅"  # Correct choice
                    elif path == chosen_path:
                        row_str += "❌"  # Wrong choice (this is where player failed)
                    elif path in correct_paths:
                        row_str += "🟩"  # Was correct path but not chosen
                    else:
                        row_str += "⬛"  # Was wrong path and not chosen
                tower_display += row_str + "\n"
            else:
                # Not yet played, show black squares
                row_str = f"**Row {row}:** " + ("⬛" * paths_count)
                tower_display += row_str + "\n"
        else:
            # Uncompleted row - show black squares only
            row_str = f"**Row {row}:** " + ("⬛" * paths_count)
            tower_display += row_str + "\n"


    embed = discord.Embed(title="🏗️ Towers - Failed!", color=0x0099ff) # Default color, will be changed on win/loss
    embed.add_field(name="Tower Progress", value=tower_display, inline=False)
    embed.add_field(name="💰 Bet", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="⚡ Difficulty", value=difficulty_name, inline=True)
    embed.add_field(name="🏢 Rows Cleared", value="0/9", inline=True)
    embed.add_field(name="💸 Lost", value=f"${wager_usd:.2f} USD", inline=True) # This field should update on win/loss
    embed.add_field(name="💳 Balance", value=f"${format_number(balances[user_id]['balance'])} USD", inline=True)
    embed.set_footer(text="Choose the correct path to climb!")

    class TowersView(discord.ui.View):
        def __init__(self, tower_structure, wager_usd, user_id, paths_count, correct_count):
            super().__init__(timeout=300)
            self.tower_structure = tower_structure
            self.wager_usd = wager_usd
            self.user_id = user_id
            self.paths_count = paths_count
            self.correct_count = correct_count
            self.current_level = 0
            self.game_over = False
            self.current_multiplier = 1.0
            self.current_winnings = 0.0
            self.path_history = []  # Track which paths were chosen

            self.setup_level()

        def get_difficulty_name(self):
            if self.paths_count == 2:
                return "Easy"
            elif self.paths_count == 3 and self.correct_count == 2:
                return "Medium"
            else:
                return "Hard"

        def build_tower_display(self):
            """Build the emoji tower display showing progress"""
            tower_display = ""
            for row in range(9, 0, -1):
                row_index = row - 1

                if row_index < len(self.path_history):
                    # This row has been played - show results
                    chosen_path = self.path_history[row_index]
                    correct_paths = self.tower_structure[row_index]

                    row_str = f"**Row {row}:** "
                    for path in range(self.paths_count):
                        if path == chosen_path and path in correct_paths:
                            row_str += "✅"  # Correct choice
                        elif path == chosen_path:
                            row_str += "❌"  # Wrong choice (this is where player failed)
                        elif path in correct_paths:
                            row_str += "🟩"  # Was correct path but not chosen
                        else:
                            row_str += "⬛"  # Was wrong path and not chosen
                    tower_display += row_str + "\n"
                else:
                    # Uncompleted row - show black squares only
                    row_str = f"**Row {row}:** " + ("⬛" * self.paths_count)
                    tower_display += row_str + "\n"

            return tower_display

        def setup_level(self):
            self.clear_items()

            if self.current_level >= 9:
                return

            # Add path buttons up to paths_count
            for path in range(min(self.paths_count, 4)): # Max 4 buttons per row
                button = discord.ui.Button(
                    label=f"Path {path + 1}",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"path_{path}",
                    emoji="🚪",
                    row=0
                )
                button.callback = self.path_callback
                self.add_item(button)

            if self.current_level > 0:
                cashout_button = discord.ui.Button(
                    label="💰 Cash Out",
                    style=discord.ButtonStyle.green,
                    custom_id="cashout",
                    row=1
                )
                cashout_button.callback = self.cashout_callback
                self.add_item(cashout_button)


        async def path_callback(self, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            chosen_path = int(interaction.data['custom_id'].split('_')[1])
            correct_paths = self.tower_structure[self.current_level]

            # Record the chosen path
            self.path_history.append(chosen_path)

            if chosen_path in correct_paths:
                self.current_level += 1
                self.current_multiplier = get_tower_multiplier(self.current_level, self.paths_count, self.correct_count)
                self.current_winnings = self.wager_usd * self.current_multiplier

                if self.current_level >= 9:
                    self.game_over = True
                    for child in self.children:
                        child.disabled = True

                    final_multiplier = get_tower_multiplier(9, self.paths_count, self.correct_count)
                    winnings_usd = self.wager_usd * final_multiplier
                    balances[self.user_id]["balance"] += winnings_usd
                    save_balances(balances)

                    new_balance_usd = balances[self.user_id]["balance"]

                    tower_display = self.build_tower_display()

                    embed = discord.Embed(title="🏗️ Towers - COMPLETED! 🎉", color=0xffd700)
                    embed.add_field(name="Tower Progress", value=tower_display, inline=False)
                    embed.add_field(name="💰 Bet", value=f"${self.wager_usd:.2f} USD", inline=True)
                    embed.add_field(name="⚡ Difficulty", value=self.get_difficulty_name(), inline=True)
                    embed.add_field(name="🏢 Rows Cleared", value="9/9", inline=True)
                    embed.add_field(name="📈 Multiplier", value=f"{final_multiplier:.2f}x", inline=True)
                    embed.add_field(name="💰 Won", value=f"${winnings_usd:.2f} USD", inline=True)
                    embed.add_field(name="💳 Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
                    embed.set_footer(text="Congratulations!")

                    self.clear_items()
                    await interaction.response.edit_message(embed=embed, view=self)
                    return
                else:
                    self.setup_level()

                    tower_display = self.build_tower_display()

                    embed = discord.Embed(title="🏗️ Towers - Correct! ✅", color=0x00ff00)
                    embed.add_field(name="Tower Progress", value=tower_display, inline=False)
                    embed.add_field(name="💰 Bet", value=f"${self.wager_usd:.2f} USD", inline=True)
                    embed.add_field(name="⚡ Difficulty", value=self.get_difficulty_name(), inline=True)
                    embed.add_field(name="🏢 Rows Cleared", value=f"{self.current_level}/9", inline=True)
                    embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
                    embed.add_field(name="💎 Current Win", value=f"${format_number(self.current_winnings)} USD", inline=True)
                    embed.add_field(name="💳 Balance", value=f"${format_number(balances[self.user_id]['balance'])} USD", inline=True)
                    embed.set_footer(text="Choose the correct path to continue climbing!")

                    await interaction.response.edit_message(embed=embed, view=self)
            else:
                self.game_over = True
                new_balance_usd = balances[self.user_id]["balance"]

                tower_display = self.build_tower_display()

                embed = discord.Embed(title="🏗️ Towers - Failed! ❌", color=0xff0000)
                embed.add_field(name="Tower Progress", value=tower_display, inline=False)
                embed.add_field(name="💰 Bet", value=f"${self.wager_usd:.2f} USD", inline=True)
                embed.add_field(name="⚡ Difficulty", value=self.get_difficulty_name(), inline=True)
                embed.add_field(name="🏢 Rows Cleared", value=f"{self.current_level}/9", inline=True)
                embed.add_field(name="💸 Lost", value=f"${self.wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
                embed.set_footer(text="Better luck next time!")

                self.clear_items()
                await interaction.response.edit_message(embed=embed, view=self)

        async def cashout_callback(self, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if self.current_level == 0:
                await interaction.response.send_message("You need to climb at least one level before cashing out!", ephemeral=True)
                return

            self.game_over = True
            for child in self.children:
                child.disabled = True

            winnings_usd = self.current_winnings
            balances[self.user_id]["balance"] += winnings_usd
            save_balances(balances)

            new_balance_usd = balances[self.user_id]["balance"]

            tower_display = self.build_tower_display()

            embed = discord.Embed(title="💰 Towers - Cashed Out! 🎉", color=0x00ff00)
            embed.add_field(name="Tower Progress", value=tower_display, inline=False)
            embed.add_field(name="💰 Bet", value=f"${self.wager_usd:.2f} USD", inline=True)
            embed.add_field(name="⚡ Difficulty", value=self.get_difficulty_name(), inline=True)
            embed.add_field(name="🏢 Rows Cleared", value=f"{self.current_level}/9", inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
            embed.add_field(name="💰 Won", value=f"${winnings_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
            embed.set_footer(text="Smart move!")

            await interaction.response.edit_message(embed=embed, view=self)

    view = TowersView(tower_structure, wager_usd, user_id, paths_count, correct_count)
    await interaction.response.send_message(embed=embed, view=view)

# LIMBO
@bot.tree.command(name="limbo", description="Choose your target multiplier and bet in the cosmic void! (in USD)")
async def limbo(interaction: discord.Interaction, wager_amount: str, target_multiplier: float):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse wager amount with abbreviation support
    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers, abbreviations like 1k, 1.5M, or 'half'/'all' for balance amounts.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if target_multiplier < 1.01 or target_multiplier > 1000:
        await interaction.response.send_message("❌ Target multiplier must be between 1.01x and 1000x!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but tried to wager ${format_number(wager_usd)} USD.")
        return

    # Start animation
    embed = discord.Embed(title="🌌 Limbo - Calculating...", color=0x9932cc)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="🎯 Target", value=f"{target_multiplier:.2f}x", inline=True)
    embed.add_field(name="⏳ Status", value="🔮 Rolling the cosmic dice...", inline=False)

    await interaction.response.send_message(embed=embed)

    # Animation frames
    frames = [
        "🌌 Entering the void...",
        "⭐ Stars are aligning...",
        "🌠 Cosmic forces at work...",
        "🔮 Reality is bending...",
        "✨ The universe decides..."
    ]

    for frame in frames:
        embed.set_field_at(2, name="⏳ Status", value=frame, inline=False)
        await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(0.6)

    # Generate result (house edge based on target multiplier)
    # Higher targets have lower win probability
    win_chance = (1 / target_multiplier) * 0.95  # 5% house edge
    won = random.random() < win_chance

    if won:
        # Player wins - add back wager plus winnings
        winnings_usd = wager_usd * target_multiplier
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]

        embed = discord.Embed(title="🌌 Limbo - TRANSCENDED! 🎉", color=0x00ff00)
        embed.add_field(name="🎯 Target Hit", value=f"{target_multiplier:.2f}x", inline=True)
        embed.add_field(name="🎲 Win Chance", value=f"{win_chance*100:.1f}%", inline=True)
        embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
        embed.add_field(name="✨ Result", value="🌟 The cosmos favor you! 🌟", inline=False)
    else:
        # Player loses - balance already deducted
        new_balance_usd = balances[user_id]["balance"]

        embed = discord.Embed(title="🌌 Limbo - LOST IN THE VOID 😔", color=0xff0000)
        embed.add_field(name="🎯 Target Missed", value=f"{target_multiplier:.2f}x", inline=True)
        embed.add_field(name="🎲 Win Chance", value=f"{win_chance*100:.1f}%", inline=True)
        embed.add_field(name="💸 Lost", value=f"${wager_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
        embed.add_field(name="🌑 Result", value="The void claims another soul...", inline=False)

    # Deduct wager at the start of the game
    balances[user_id]["balance"] -= wager_usd
    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    # Create play again view
    class LimboPlayAgainView(discord.ui.View):
        def __init__(self, wager_usd, target_multiplier, user_id):
            super().__init__(timeout=300)
            self.wager_usd = wager_usd
            self.target_multiplier = target_multiplier
            self.user_id = user_id

        @discord.ui.button(label="🌌 Play Again", style=discord.ButtonStyle.primary)
        async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            await start_new_limbo_game(interaction, self.wager_usd, self.target_multiplier, self.user_id)

    async def start_new_limbo_game(interaction, wager_usd, target_multiplier, user_id):
        # Deduct wager at the start of the game
        balances[user_id]["balance"] -= wager_usd
        balances[user_id]["wagered"] += wager_usd
        add_rakeback(user_id, wager_usd)
        save_balances(balances)

        # Start animation
        embed = discord.Embed(title="🌌 Limbo - Calculating...", color=0x9932cc)
        embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
        embed.add_field(name="🎯 Target", value=f"{target_multiplier:.2f}x", inline=True)
        embed.add_field(name="⏳ Status", value="🔮 Rolling the cosmic dice...", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)

        # Animation frames
        frames = [
            "🌌 Entering the void...", "⭐ Stars are aligning...", "🌠 Cosmic forces at work...",
            "🔮 Reality is bending...", "✨ The universe decides..."
        ]

        for frame in frames:
            embed.set_field_at(2, name="⏳ Status", value=frame, inline=False)
            await interaction.edit_original_response(embed=embed)
            await asyncio.sleep(0.6)

        # Generate result
        win_chance = (1 / target_multiplier) * 0.95
        won = random.random() < win_chance

        if won:
            # Player wins - add back wager plus winnings
            winnings_usd = wager_usd * target_multiplier
            balances[user_id]["balance"] += winnings_usd
            new_balance_usd = balances[user_id]["balance"]

            embed = discord.Embed(title="🌌 Limbo - TRANSCENDED! 🎉", color=0x00ff00)
            embed.add_field(name="🎯 Target Hit", value=f"{target_multiplier:.2f}x", inline=True)
            embed.add_field(name="🎲 Win Chance", value=f"{win_chance*100:.1f}%", inline=True)
            embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
            embed.add_field(name="✨ Result", value="🌟 The cosmos favor you! 🌟", inline=False)
        else:
            # Player loses - balance already deducted
            new_balance_usd = balances[user_id]["balance"]

            embed = discord.Embed(title="🌌 Limbo - LOST IN THE VOID 😔", color=0xff0000)
            embed.add_field(name="🎯 Target Missed", value=f"{target_multiplier:.2f}x", inline=True)
            embed.add_field(name="🎲 Win Chance", value=f"{win_chance*100:.1f}%", inline=True)
            embed.add_field(name="💸 Lost", value=f"${wager_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
            embed.add_field(name="🌑 Result", value="The void claims another soul...", inline=False)

        save_balances(balances)

        play_again_view = LimboPlayAgainView(wager_usd, target_multiplier, user_id)
        await interaction.edit_original_response(embed=embed, view=play_again_view)

    play_again_view = LimboPlayAgainView(wager_usd, target_multiplier, user_id)
    await interaction.edit_original_response(embed=embed, view=play_again_view)

# PLINKO
@bot.tree.command(name="plinko", description="Drop a ball down the Plinko board with customizable rows and difficulty! (in USD)")
async def plinko(interaction: discord.Interaction, wager_amount: str, rows: int = 8, difficulty: str = "medium"):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse wager amount with abbreviation support
    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format! Use numbers, abbreviations like 1k, 1.5M, or 'half'/'all' for balance amounts.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if rows < 8 or rows > 16:
        await interaction.response.send_message("❌ Rows must be between 8-16!", ephemeral=True)
        return

    if difficulty.lower() not in ["low", "medium", "high"]:
        await interaction.response.send_message("❌ Difficulty must be 'low', 'medium', or 'high'!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but tried to wager ${format_number(wager_usd)} USD.")
        return

    # Calculate number of buckets (always rows + 1)
    num_buckets = rows + 1

    # Generate multipliers based on difficulty
    if difficulty.lower() == "low":
        # Lower risk, lower reward
        edge_multiplier = 10
        mid_multiplier = 1.5
        center_multiplier = 0.9
    elif difficulty.lower() == "medium":
        # Medium risk, medium reward
        edge_multiplier = 50
        mid_multiplier = 2
        center_multiplier = 0.5
    else:  # high
        # High risk, high reward
        edge_multiplier = 100
        mid_multiplier = 5
        center_multiplier = 0.2

    # Generate symmetric multiplier pattern
    multipliers = []
    for i in range(num_buckets):
        distance_from_center = abs(i - (num_buckets - 1) / 2)
        max_distance = (num_buckets - 1) / 2

        if distance_from_center == max_distance:
            # Edge buckets
            multipliers.append(edge_multiplier)
        elif distance_from_center >= max_distance * 0.7:
            # Near edge buckets
            multipliers.append(mid_multiplier)
        else:
            # Center buckets
            multipliers.append(center_multiplier)

    # Start animation
    embed = discord.Embed(title=f"🏀 Plinko - {rows} Rows ({difficulty.title()} Risk)", color=0xff6600)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="📊 Rows", value=f"{rows} rows", inline=True)
    embed.add_field(name="⚡ Difficulty", value=difficulty.title(), inline=True)
    embed.add_field(name="🏀 Ball", value="Starting at top!", inline=False)

    await interaction.response.send_message(embed=embed)

    # Simulate ball path
    position = num_buckets // 2  # Start at center

    # Ball bounces down the specified number of rows
    for level in range(rows):
        # Random bounce left or right (influenced by difficulty)
        if difficulty.lower() == "low":
            # More predictable bounces
            bounce = random.choice([-1, 0, 1])
        elif difficulty.lower() == "medium":
            # Normal bounces
            bounce = random.choice([-1, 1])
        else:  # high
            # More chaotic bounces
            bounce = random.choice([-2, -1, 1, 2])

        position = max(0, min(num_buckets - 1, position + bounce))

        # Create ball visualization
        ball_visual = ""
        for i in range(num_buckets):
            if i == position:
                ball_visual += "🏀"
            else:
                ball_visual += "⚫"

        embed.set_field_at(3, name="🏀 Ball", value=f"Row {level + 1}/{rows}: {ball_visual}", inline=False)

        await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(0.5)

    # Final position determines multiplier
    final_position = position
    multiplier = multipliers[final_position]

    # Calculate winnings (apply house edge)
    if multiplier >= 1:
        winnings_usd = wager_usd * multiplier * 0.85  # 15% house edge on wins
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]

        embed = discord.Embed(title="🏀 Plinko - WINNER! 🎉", color=0x00ff00)
        embed.add_field(name="📍 Final Bucket", value=f"Position {final_position + 1}/{num_buckets}", inline=True)
        embed.add_field(name="📈 Multiplier", value=f"{multiplier}x", inline=True)
        embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
        embed.add_field(name="🏀 Result", value="🎊 Ball landed in a winning bucket! 🎊", inline=False)
    else:
        # Small loss (less than 1x multiplier)
        loss_amount = wager_usd * (1 - multiplier)
        balances[user_id]["balance"] -= loss_amount
        new_balance_usd = balances[user_id]["balance"]

        embed = discord.Embed(title="🏀 Plinko - Small Loss 😔", color=0xff0000)
        embed.add_field(name="📍 Final Bucket", value=f"Position {final_position + 1}/{num_buckets}", inline=True)
        embed.add_field(name="📈 Multiplier", value=f"{multiplier}x", inline=True)
        embed.add_field(name="💸 Lost", value=f"${loss_amount:.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
        embed.add_field(name="🏀 Result", value="🎯 Ball landed in a low bucket", inline=False)

    # Show final position and all multipliers
    final_visual = ""
    multiplier_text = ""
    for i in range(num_buckets):
        if i == final_position:
            final_visual += "🏀"
        else:
            final_visual += "⚫"
        multiplier_text += f"{multipliers[i]}x "

    embed.add_field(name="🎯 Final Position", value=final_visual, inline=False)
    embed.add_field(name="📊 All Multipliers", value=multiplier_text.strip(), inline=False)

    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    # Create play again view
    class PlinkoPlayAgainView(discord.ui.View):
        def __init__(self, wager_usd, rows, difficulty, user_id):
            super().__init__(timeout=300)
            self.wager_usd = wager_usd
            self.rows = rows
            self.difficulty = difficulty
            self.user_id = user_id

        @discord.ui.button(label="🏀 Play Again", style=discord.ButtonStyle.primary)
        async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            await start_new_plinko_game(interaction, self.wager_usd, self.rows, self.difficulty, self.user_id)

    async def start_new_plinko_game(interaction, wager_usd, rows, difficulty, user_id):
        # Calculate multipliers
        num_buckets = rows + 1

        if difficulty.lower() == "low":
            edge_multiplier = 10
            mid_multiplier = 1.5
            center_multiplier = 0.9
        elif difficulty.lower() == "medium":
            edge_multiplier = 50
            mid_multiplier = 2
            center_multiplier = 0.5
        else:  # high
            edge_multiplier = 100
            mid_multiplier = 5
            center_multiplier = 0.2

        multipliers = []
        for i in range(num_buckets):
            distance_from_center = abs(i - (num_buckets - 1) / 2)
            max_distance = (num_buckets - 1) / 2

            if distance_from_center == max_distance:
                multipliers.append(edge_multiplier)
            elif distance_from_center >= max_distance * 0.7:
                multipliers.append(mid_multiplier)
            else:
                multipliers.append(center_multiplier)

        # Start animation
        embed = discord.Embed(title=f"🏀 Plinko - {rows} Rows ({difficulty.title()} Risk)", color=0xff6600)
        embed.add_field(name="💰 Bet", value=f"${wager_usd:.2f} USD", inline=True)
        embed.add_field(name="📊 Rows", value=f"{rows} rows", inline=True)
        embed.add_field(name="⚡ Difficulty", value=difficulty.title(), inline=True)
        embed.add_field(name="🏀 Ball", value="Starting at top!", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)

        # Simulate ball path
        position = num_buckets // 2

        for level in range(rows):
            if difficulty.lower() == "low":
                bounce = random.choice([-1, 0, 1])
            elif difficulty.lower() == "medium":
                bounce = random.choice([-1, 1])
            else:  # high
                bounce = random.choice([-2, -1, 1, 2])

            position = max(0, min(num_buckets - 1, position + bounce))

            ball_visual = ""
            for i in range(num_buckets):
                if i == position:
                    ball_visual += "🏀"
                else:
                    ball_visual += "⚫"

            embed.set_field_at(3, name="🏀 Ball", value=f"Row {level + 1}/{rows}: {ball_visual}", inline=False)
            await interaction.edit_original_response(embed=embed)
            await asyncio.sleep(0.5)

        # Final result
        final_position = position
        multiplier = multipliers[final_position]

        if multiplier >= 1:
            winnings_usd = wager_usd * multiplier * 0.85  # 15% house edge on wins
            balances[user_id]["balance"] += winnings_usd
            new_balance_usd = balances[user_id]["balance"]

            embed = discord.Embed(title="🏀 Plinko - WINNER! 🎉", color=0x00ff00)
            embed.add_field(name="📍 Final Bucket", value=f"Position {final_position + 1}/{num_buckets}", inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{multiplier}x", inline=True)
            embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
            embed.add_field(name="🏀 Result", value="🎊 Ball landed in a winning bucket! 🎊", inline=False)
        else:
            # Small loss (less than 1x multiplier)
            loss_amount = wager_usd * (1 - multiplier)
            balances[user_id]["balance"] -= loss_amount
            new_balance_usd = balances[user_id]["balance"]

            embed = discord.Embed(title="🏀 Plinko - Small Loss 😔", color=0xff0000)
            embed.add_field(name="📍 Final Bucket", value=f"Position {final_position + 1}/{num_buckets}", inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{multiplier}x", inline=True)
            embed.add_field(name="💸 Lost", value=f"${loss_amount:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
            embed.add_field(name="🏀 Result", value="🎯 Ball landed in a low bucket", inline=False)

        # Show final position and all multipliers
        final_visual = ""
        multiplier_text = ""
        for i in range(num_buckets):
            if i == final_position:
                final_visual += "🏀"
            else:
                final_visual += "⚫"
            multiplier_text += f"{multipliers[i]}x "

        embed.add_field(name="🎯 Final Position", value=final_visual, inline=False)
        embed.add_field(name="📊 All Multipliers", value=multiplier_text.strip(), inline=False)

        balances[user_id]["wagered"] += wager_usd
        add_rakeback(user_id, wager_usd)
        save_balances(balances)

        play_again_view = PlinkoPlayAgainView(wager_usd, rows, difficulty, user_id)
        await interaction.edit_original_response(embed=embed, view=play_again_view)

    play_again_view = PlinkoPlayAgainView(wager_usd, rows, difficulty, user_id)
    await interaction.edit_original_response(embed=embed, view=play_again_view)

# HOUSE BALANCE
@bot.tree.command(name="housebalance", description="Admin command to check house wallet balance")
async def housebalance(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if not ltc_handler or not ltc_handler.house_wallet_address:
        await interaction.response.send_message("❌ House wallet not initialized!", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        # Reload house stats to get latest data
        global house_balance
        house_balance = load_house_balance()

        # Get house balance from blockchain (checks actual wallet address)
        house_balance_ltc = await ltc_handler.get_house_balance()
        ltc_price = await get_ltc_price()
        house_balance_usd = house_balance_ltc * ltc_price

        # Load house balance stats
        house_stats = load_house_balance()

        # Send house balance as embed
        embed = discord.Embed(
            title="🏦 House Wallet Balance",
            color=0x00ff00
        )
        embed.add_field(name="💰 LTC Balance", value=f"{house_balance_ltc:.8f} LTC", inline=True)
        embed.add_field(name="💵 USD Value", value=f"${house_balance_usd:.2f} USD", inline=True)
        embed.add_field(name="📥 Total Deposits", value=f"${house_stats['total_deposits']:.2f} USD", inline=True)
        embed.add_field(name="📤 Total Withdrawals", value=f"${house_stats['total_withdrawals']:.2f} USD", inline=True)
        embed.add_field(name="📍 Wallet Address", value=f"`{ltc_handler.house_wallet_address}`", inline=False)
        embed.set_footer(text="House wallet manages all user deposits")

        # Log house balance update to webhook
        await log_house_balance_webhook(interaction.user, house_balance_ltc, house_balance_usd, ltc_handler.house_wallet_address)

        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"Error in housebalance command: {e}")
        await interaction.followup.send("❌ Failed to retrieve house balance. Please try again later.", ephemeral=True)

# HOUSE WITHDRAW
@bot.tree.command(name="housewithdraw", description="Admin command to withdraw from house wallet")
async def housewithdraw(interaction: discord.Interaction, amount_ltc: float, ltc_address: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if not ltc_handler:
        await interaction.response.send_message("❌ Crypto handler not initialized!", ephemeral=True)
        return

    if amount_ltc <= 0:
        await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    # Check house balance
    house_balance_ltc = await ltc_handler.get_house_balance()
    if house_balance_ltc < amount_ltc:
        await interaction.followup.send(f"❌ Insufficient house balance! Available: {house_balance_ltc:.8f} LTC", ephemeral=True)
        return

    # Withdraw from house wallet
    tx_hash = await ltc_handler.withdraw_from_house_wallet(ltc_address, amount_ltc)

    if tx_hash:
        # Update house balance stats
        house_stats = load_house_balance()
        ltc_price = await get_ltc_price()
        amount_usd = amount_ltc * ltc_price
        house_stats['total_withdrawals'] += amount_usd
        save_house_balance(house_stats)

        embed = discord.Embed(
            title="✅ House Withdrawal Successful",
            color=0x00ff00
        )
        embed.add_field(name="💰 Amount", value=f"{amount_ltc:.8f} LTC", inline=True)
        embed.add_field(name="💵 USD Value", value=f"${amount_usd:.2f} USD", inline=True)
        embed.add_field(name="📍 To Address", value=f"`{ltc_address}`", inline=False)
        embed.add_field(name="🔗 Transaction", value=f"`{tx_hash}`", inline=False)
        embed.set_footer(text="House wallet withdrawal completed")

        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.followup.send("❌ Failed to process withdrawal. Please try again.", ephemeral=True)

# WITHDRAWAL QUEUE - Admin command to view pending withdrawals
@bot.tree.command(name="queue", description="Admin command to view all pending withdrawal requests")
async def queue(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return

    global withdrawal_requests
    withdrawal_requests = load_withdrawal_requests()

    # Filter pending withdrawals
    pending = {wd_id: wd for wd_id, wd in withdrawal_requests.items() if wd.get("status") == "pending"}

    if not pending:
        embed = discord.Embed(
            title="📋 Withdrawal Queue",
            description="No pending withdrawal requests.",
            color=0x00ff00
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Create embed with pending withdrawals
    embed = discord.Embed(
        title="📋 Pending Withdrawal Requests",
        description=f"**{len(pending)}** pending request(s) awaiting approval",
        color=0xffaa00
    )

    for wd_id, wd in list(pending.items())[:10]:
        created_time = f"<t:{wd['created_at']}:R>"
        embed.add_field(
            name=f"🆔 {wd_id}",
            value=f"**User:** {wd['username']}\n"
                  f"**Amount:** ${wd['amount_usd']:.2f} USD (~{wd['amount_ltc']:.8f} LTC)\n"
                  f"**Address:** `{wd['ltc_address'][:20]}...`\n"
                  f"**Requested:** {created_time}",
            inline=False
        )

    if len(pending) > 10:
        embed.set_footer(text="Showing 10 of {len(pending)} pending requests. Use /confirmwithdraw <id> to process.")
    else:
        embed.set_footer(text="Use /confirmwithdraw <id> to process a withdrawal.")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# CONFIRM WITHDRAW - Admin command to process a withdrawal
@bot.tree.command(name="confirmwithdraw", description="Admin command to confirm and complete a withdrawal request")
async def confirmwithdraw(interaction: discord.Interaction, withdrawal_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return

    global withdrawal_requests
    withdrawal_requests = load_withdrawal_requests()

    # Check if withdrawal exists
    if withdrawal_id not in withdrawal_requests:
        await interaction.response.send_message(f"❌ Withdrawal request `{withdrawal_id}` not found.", ephemeral=True)
        return

    wd = withdrawal_requests[withdrawal_id]

    # Check if already processed
    if wd.get("status") != "pending":
        await interaction.response.send_message(f"❌ Withdrawal `{withdrawal_id}` has already been {wd.get('status')}.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        # Mark as completed
        withdrawal_requests[withdrawal_id]["status"] = "completed"
        withdrawal_requests[withdrawal_id]["completed_at"] = int(time.time())
        withdrawal_requests[withdrawal_id]["completed_by"] = str(interaction.user.id)
        save_withdrawal_requests(withdrawal_requests)

        # Update user's withdrawn stats
        user_id = wd["user_id"]
        if user_id in balances:
            balances[user_id]["withdrawn"] += wd["amount_usd"]
            save_balances(balances)

        # Update house balance stats
        house_stats = load_house_balance()
        house_stats['total_withdrawals'] += wd["amount_usd"]
        save_house_balance(house_stats)

        # Send confirmation to admin
        embed = discord.Embed(
            title="✅ Withdrawal Confirmed",
            description=f"Withdrawal `{withdrawal_id}` has been marked as complete.",
            color=0x00ff00
        )
        embed.add_field(name="👤 User", value=wd["username"], inline=True)
        embed.add_field(name="💵 Amount", value=f"${wd['amount_usd']:.2f} USD", inline=True)
        embed.add_field(name="💰 LTC", value=f"~{wd['amount_ltc']:.8f} LTC", inline=True)
        embed.add_field(name="📍 Address", value=f"`{wd['ltc_address']}`", inline=False)
        embed.set_footer(text="Please send the LTC manually to the address above.")

        await interaction.followup.send(embed=embed, ephemeral=True)

        # Try to notify the user
        try:
            user = await bot.fetch_user(int(user_id))
            if user:
                user_embed = discord.Embed(
                    title="✅ Withdrawal Approved!",
                    description="Your withdrawal request has been approved and is being processed.",
                    color=0x00ff00
                )
                user_embed.add_field(name="🆔 Request ID", value=f"`{withdrawal_id}`", inline=True)
                user_embed.add_field(name="💵 Amount", value=f"${wd['amount_usd']:.2f} USD", inline=True)
                user_embed.add_field(name="💰 LTC", value=f"~{wd['amount_ltc']:.8f} LTC", inline=True)
                user_embed.add_field(name="📍 Destination", value=f"`{wd['ltc_address']}`", inline=False)
                user_embed.set_footer(text="LTC will be sent to your address shortly.")
                await user.send(embed=user_embed)
        except Exception as e:
            print(f"Could not notify user {user_id}: {e}")

        # Log the admin withdrawal confirmation
        try:
            target_user = await bot.fetch_user(int(user_id))
            await log_admin_withdraw(interaction.user, target_user, wd["amount_usd"], wd["ltc_address"], withdrawal_id)
        except Exception as e:
            print(f"Failed to log admin withdraw: {e}")

    except Exception as e:
        print(f"Error confirming withdrawal: {e}")
        await interaction.followup.send(f"❌ Error processing withdrawal: {e}", ephemeral=True)

# CANCEL WITHDRAW - Admin command to cancel/reject a withdrawal
@bot.tree.command(name="cancelwithdraw", description="Admin command to cancel/reject a withdrawal request")
async def cancelwithdraw(interaction: discord.Interaction, withdrawal_id: str, reason: str = "No reason provided"):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return

    global withdrawal_requests
    withdrawal_requests = load_withdrawal_requests()

    # Check if withdrawal exists
    if withdrawal_id not in withdrawal_requests:
        await interaction.response.send_message(f"❌ Withdrawal request `{withdrawal_id}` not found.", ephemeral=True)
        return

    wd = withdrawal_requests[withdrawal_id]

    # Check if already processed
    if wd.get("status") != "pending":
        await interaction.response.send_message(f"❌ Withdrawal `{withdrawal_id}` has already been {wd.get('status')}.", ephemeral=True)
        return

    # Mark as cancelled and refund the user
    withdrawal_requests[withdrawal_id]["status"] = "cancelled"
    withdrawal_requests[withdrawal_id]["cancelled_at"] = int(time.time())
    withdrawal_requests[withdrawal_id]["cancelled_by"] = str(interaction.user.id)
    withdrawal_requests[withdrawal_id]["cancel_reason"] = reason
    save_withdrawal_requests(withdrawal_requests)

    # Refund the user's balance
    user_id = wd["user_id"]
    if user_id in balances:
        balances[user_id]["balance"] += wd["amount_usd"]
        save_balances(balances)

    # Send confirmation to admin
    embed = discord.Embed(
        title="❌ Withdrawal Cancelled",
        description=f"Withdrawal `{withdrawal_id}` has been cancelled and funds refunded.",
        color=0xff0000
    )
    embed.add_field(name="👤 User", value=wd["username"], inline=True)
    embed.add_field(name="💵 Amount Refunded", value=f"${wd['amount_usd']:.2f} USD", inline=True)
    embed.add_field(name="📝 Reason", value=reason, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

    # Try to notify the user
    try:
        user = await bot.fetch_user(int(user_id))
        if user:
            user_embed = discord.Embed(
                title="❌ Withdrawal Request Cancelled",
                description="Your withdrawal request has been cancelled by an administrator.",
                color=0xff0000
            )
            user_embed.add_field(name="🆔 Request ID", value=f"`{withdrawal_id}`", inline=True)
            user_embed.add_field(name="💵 Amount Refunded", value=f"${wd['amount_usd']:.2f} USD", inline=True)
            user_embed.add_field(name="📝 Reason", value=reason, inline=False)
            user_embed.set_footer(text="Your funds have been returned to your balance.")
            await user.send(embed=user_embed)
    except Exception as e:
        print(f"Could not notify user {user_id}: {e}")

# HOUSE DEPOSIT
@bot.tree.command(name="housedosit", description="Admin command to get house wallet deposit address")
async def housedosit(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if not ltc_handler or not ltc_handler.house_wallet_address:
        await interaction.response.send_message("❌ House wallet not initialized!", ephemeral=True)
        return

    # Get current house balance
    house_balance_ltc = await ltc_handler.get_house_balance()
    ltc_price = await get_ltc_price()
    house_balance_usd = house_balance_ltc * ltc_price

    embed = discord.Embed(
        title="🏦 House Wallet Deposit Address",
        description="Send Litecoin to this address to top up the house wallet",
        color=0x0099ff
    )
    embed.add_field(name="📍 House Wallet Address", value=f"`{ltc_handler.house_wallet_address}`", inline=False)
    embed.add_field(name="💰 Current Balance", value=f"{house_balance_ltc:.8f} LTC", inline=True)
    embed.add_field(name="💵 USD Value", value=f"${house_balance_usd:.2f} USD", inline=True)
    embed.add_field(name="⚠️ Important", value="Only send Litecoin (LTC) to this address", inline=False)
    embed.set_footer(text="House wallet for managing user deposits")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# BACCARAT
@bot.tree.command(name="baccarat", description="Classic Baccarat - bet on Player, Banker, or Tie (in USD)")
async def baccarat(interaction: discord.Interaction, wager_amount: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Parse wager amount
    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        await interaction.response.send_message(f"❌ Insufficient balance!", ephemeral=True)
        return

    # Show choice selection
    class BaccaratChoiceView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=60)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="Player", style=discord.ButtonStyle.blurple, emoji="👤")
        async def player_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_baccarat_game(interaction, "player", self.wager_usd, self.user_id)

        @discord.ui.button(label="Banker", style=discord.ButtonStyle.danger, emoji="🏦")
        async def banker_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_baccarat_game(interaction, "banker", self.wager_usd, self.user_id)

        @discord.ui.button(label="Tie", style=discord.ButtonStyle.secondary, emoji="🤝")
        async def tie_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_baccarat_game(interaction, "tie", self.wager_usd, self.user_id)

    embed = discord.Embed(title="🎴 Baccarat - Place Your Bet", color=0x8a2be2)
    embed.add_field(name="💰 Wager", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="👇 Choose", value="Select your bet:", inline=False)
    embed.add_field(name="👤 Player", value="1:1 payout", inline=True)
    embed.add_field(name="🏦 Banker", value="0.95:1 payout", inline=True)
    embed.add_field(name="🤝 Tie", value="8:1 payout", inline=True)
    embed.set_footer(text="Click a button to place your bet!")

    view = BaccaratChoiceView(wager_usd, user_id)
    await interaction.response.send_message(embed=embed, view=view)
    return

async def start_baccarat_game(interaction, bet_on, wager_usd, user_id):
    # Deduct wager
    balances[user_id]["balance"] -= wager_usd
    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    # Deal cards
    deck = list(range(1, 14)) * 4  # A-K, 4 suits
    random.shuffle(deck)

    player_cards = [deck.pop(), deck.pop()]
    banker_cards = [deck.pop(), deck.pop()]

    def card_value(card):
        return min(card, 10)

    def hand_total(cards):
        return sum(card_value(c) for c in cards) % 10

    player_total = hand_total(player_cards)
    banker_total = hand_total(banker_cards)

    # Third card rules
    player_drew = False
    banker_drew = False

    if player_total <= 5 and banker_total < 8:
        player_cards.append(deck.pop())
        player_drew = True
        player_total = hand_total(player_cards)

    if not player_drew and banker_total <= 5:
        banker_cards.append(deck.pop())
        banker_drew = True
        banker_total = hand_total(banker_cards)
    elif player_drew:
        third_card = player_cards[2]
        if (banker_total <= 2) or \
           (banker_total == 3 and third_card != 8) or \
           (banker_total == 4 and 2 <= third_card <= 7) or \
           (banker_total == 5 and 4 <= third_card <= 7) or \
           (banker_total == 6 and 6 <= third_card <= 7):
            banker_cards.append(deck.pop())
            banker_drew = True
            banker_total = hand_total(banker_cards)

    # Determine winner
    bet = bet_on.lower()
    if player_total > banker_total:
        winner = "player"
    elif banker_total > player_total:
        winner = "banker"
    else:
        winner = "tie"

    # Calculate payout
    if bet == winner:
        if winner == "tie":
            winnings_usd = wager_usd * 8  # 8:1 for tie
        elif winner == "banker":
            winnings_usd = wager_usd * 1.95  # 0.95:1 for banker (5% commission)
        else:  # player
            winnings_usd = wager_usd * 2  # 1:1 for player

        balances[user_id]["balance"] += winnings_usd
        color = 0x00ff00
        title = "🎴 Baccarat - YOU WON! 🎉"
    else:
        winnings_usd = 0
        color = 0xff0000
        title = "🎴 Baccarat - You Lost 😔"

    save_balances(balances)
    new_balance_usd = balances[user_id]["balance"]

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="👤 Player Hand", value=f"{player_cards} = **{player_total}**", inline=True)
    embed.add_field(name="🏦 Banker Hand", value=f"{banker_cards} = **{banker_total}**", inline=True)
    embed.add_field(name="🏆 Winner", value=winner.title(), inline=True)
    embed.add_field(name="🎯 Your Bet", value=bet_on.title(), inline=True)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

    # Create baccarat image using game image generator
    baccarat_img_path = f"baccarat_{user_id}_{time.time()}.png"
    files = []
    try:
        game_img_gen.create_baccarat_image(player_cards, banker_cards, player_total, banker_total, baccarat_img_path)

        files.append(discord.File(baccarat_img_path, filename="baccarat.png"))
        embed.set_image(url="attachment://baccarat.png")
        await interaction.response.send_message(embed=embed, files=files)

        # Clean up
        try:
            os.remove(baccarat_img_path)
        except:
            pass
    except Exception as e:
        print(f"Error creating baccarat image: {e}")
        await interaction.response.send_message(embed=embed)

# BALLOON PUMP
@bot.tree.command(name="balloon", description="Pump the balloon without popping it! (in USD)")
async def balloon(interaction: discord.Interaction, wager_amount: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        await interaction.response.send_message(f"❌ Insufficient balance!", ephemeral=True)
        return

    # Set difficulty parameters (Stake-style)
    # We'll use a 'difficulty' parameter to control these values
    # For now, let's hardcode them. Later, we can make it a command argument.
    difficulty = "medium" # Default to medium
    if difficulty == "easy":
        pop_chance_per_pump = 0.01  # 1% chance per pump
        multiplier_increase = 0.08  # 8% increase per pump
    elif difficulty == "medium":
        pop_chance_per_pump = 0.03  # 3% chance per pump
        multiplier_increase = 0.15  # 15% increase per pump
    else:  # hard
        pop_chance_per_pump = 0.05  # 5% chance per pump
        multiplier_increase = 0.25  # 25% increase per pump

    # Deduct wager
    balances[user_id]["balance"] -= wager_usd
    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    class BalloonView(discord.ui.View):
        def __init__(self, wager_usd, user_id, pop_chance_per_pump, multiplier_increase):
            super().__init__(timeout=120)
            self.wager_usd = wager_usd
            self.user_id = user_id
            self.pop_chance_per_pump = pop_chance_per_pump
            self.multiplier_increase = multiplier_increase
            self.current_multiplier = 1.0
            self.pumps = 0
            self.game_over = False
            self.current_winnings = 0.0

        @discord.ui.button(label="🎈 Pump", style=discord.ButtonStyle.primary)
        async def pump_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            self.pumps += 1
            self.current_multiplier = round(self.current_multiplier * (1 + self.multiplier_increase), 2)
            self.current_winnings = round(self.wager_usd * self.current_multiplier, 2)

            # Calculate pop chance based on pumps
            cumulative_pop_chance = self.pop_chance_per_pump * self.pumps
            if random.random() < cumulative_pop_chance:
                # Balloon popped!
                self.game_over = True
                self.clear_items()

                new_balance_usd = balances[self.user_id]["balance"]

                embed = discord.Embed(title="💥 BALLOON POPPED! 💥", color=0xff0000)
                embed.add_field(name="🎈 Pumps", value=str(self.pumps), inline=True)
                embed.add_field(name="📈 Reached", value=f"{self.current_multiplier:.2f}x", inline=True)
                embed.add_field(name="💸 Lost", value=f"${self.wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

                # Create balloon popped image
                balloon_img_path = f"balloon_{self.user_id}_{time.time()}.png"
                files = []
                try:
                    game_img_gen.create_balloon_image(self.pumps, True, balloon_img_path)
                    files.append(discord.File(balloon_img_path, filename="balloon.png"))
                    embed.set_image(url="attachment://balloon.png")
                except Exception as e:
                    print(f"Error creating balloon image: {e}")

                await interaction.response.edit_message(embed=embed, view=self, attachments=files)

                if os.path.exists(balloon_img_path):
                    try:
                        os.remove(balloon_img_path)
                    except:
                        pass
            else:
                balloon_size = "🎈" * min(self.pumps, 10)

                embed = discord.Embed(title="🎈 Balloon Pump", color=0x0099ff)
                embed.add_field(name="🎈 Pumps", value=str(self.pumps), inline=True)
                embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
                embed.add_field(name="💰 Current Win", value=f"${self.current_winnings:.2f} USD", inline=True)
                embed.add_field(name="🎈 Balloon", value=balloon_size, inline=False)
                embed.set_footer(text="Keep pumping or cash out before it pops!")

                # Create balloon image
                balloon_img_path = f"balloon_{self.user_id}_{time.time()}.png"
                files = []
                try:
                    game_img_gen.create_balloon_image(self.pumps, False, balloon_img_path)
                    files.append(discord.File(balloon_img_path, filename="balloon.png"))
                    embed.set_image(url="attachment://balloon.png")
                except Exception as e:
                    print(f"Error creating balloon image: {e}")

                await interaction.response.edit_message(embed=embed, view=self, attachments=files)

                # Clean up
                if os.path.exists(balloon_img_path):
                    try:
                        os.remove(balloon_img_path)
                    except:
                        pass

        @discord.ui.button(label="💰 Cash Out", style=discord.ButtonStyle.green)
        async def cashout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if self.pumps == 0:
                await interaction.response.send_message("You need to pump at least once before cashing out!", ephemeral=True)
                return

            self.game_over = True
            self.clear_items()

            winnings_usd = self.current_winnings
            balances[self.user_id]["balance"] += winnings_usd
            save_balances(balances)
            new_balance_usd = balances[self.user_id]["balance"]

            balloon_size = "🎈" * min(self.pumps, 10)

            embed = discord.Embed(title="💰 Cashed Out! 🎉", color=0x00ff00)
            embed.add_field(name="🎈 Pumps", value=str(self.pumps), inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
            embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
            embed.add_field(name="🎈 Final Balloon", value=balloon_size, inline=False)

            # Create balloon cashout image
            balloon_img_path = f"balloon_{self.user_id}_{time.time()}.png"
            files = []
            try:
                game_img_gen.create_balloon_image(self.pumps, False, balloon_img_path)
                files.append(discord.File(balloon_img_path, filename="balloon.png"))
                embed.set_image(url="attachment://balloon.png")
            except Exception as e:
                print(f"Error creating balloon image: {e}")

            await interaction.response.edit_message(embed=embed, view=self, attachments=files)

            if os.path.exists(balloon_img_path):
                try:
                    os.remove(balloon_img_path)
                except:
                    pass

    embed = discord.Embed(title="🎈 Balloon Pump", color=0xff6600)
    embed.add_field(name="💰 Wager", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="🎈 Pumps", value="0", inline=True)
    embed.add_field(name="📈 Multiplier", value="1.00x", inline=True)
    embed.set_footer(text="Keep pumping or cash out before it pops!")

    view = BalloonView(wager_usd, user_id, pop_chance_per_pump, multiplier_increase)
    await interaction.response.send_message(embed=embed, view=view)

# CHICKEN CROSSING (REMOVED)

# KENO
@bot.tree.command(name="keno", description="Play Keno - select numbers on a 5x5 grid! (in USD)")
async def keno(interaction: discord.Interaction, wager_amount: str, num_picks: int):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    try:
        wager_usd = parse_amount(wager_amount, user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format!", ephemeral=True)
        return

    if wager_usd < 0.10:
        await interaction.response.send_message("❌ Minimum wager is $0.10 USD!", ephemeral=True)
        return

    if num_picks < 1 or num_picks > 10:
        await interaction.response.send_message("❌ You must pick between 1-10 numbers!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        await interaction.response.send_message(f"❌ Insufficient balance!", ephemeral=True)
        return

    class KenoView(discord.ui.View):
        def __init__(self, wager_usd, user_id, num_picks, message):
            super().__init__(timeout=180)
            self.wager_usd = wager_usd
            self.user_id = user_id
            self.num_picks = num_picks
            self.selected = set()
            self.game_started = False
            self.message = message

            # Create 5x5 grid of buttons (25 total - at Discord's limit)
            for i in range(25):
                button = discord.ui.Button(
                    label=str(i + 1),
                    style=discord.ButtonStyle.secondary,
                    row=i // 5,
                    custom_id=f"tile_{i}"
                )
                button.callback = self.tile_callback
                self.add_item(button)

        async def tile_callback(self, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_started:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            tile_pos = int(interaction.data['custom_id'].split('_')[1])

            if tile_pos in self.selected:
                # Deselect
                self.selected.remove(tile_pos)
            else:
                # Select if not at limit
                if len(self.selected) >= self.num_picks:
                    await interaction.response.send_message(f"You can only select {self.num_picks} numbers!", ephemeral=True)
                    return
                self.selected.add(tile_pos)

            # Update button styles
            for item in self.children:
                if hasattr(item, 'custom_id') and item.custom_id.startswith('tile_'):
                    tile_id = int(item.custom_id.split('_')[1])
                    if tile_id in self.selected:
                        item.style = discord.ButtonStyle.primary
                    else:
                        item.style = discord.ButtonStyle.secondary

            # Check if user has selected all their picks - auto start the game
            if len(self.selected) == self.num_picks:
                await interaction.response.defer()
                await self.start_game(interaction)
                return
            else:
                remaining = self.num_picks - len(self.selected)
                embed = discord.Embed(title="🎰 Keno - Select Your Numbers", color=0xff6600)
                embed.add_field(name="💰 Wager", value=f"${self.wager_usd:.2f} USD", inline=True)
                embed.add_field(name="🎯 Selected", value=f"{len(self.selected)}/{self.num_picks}", inline=True)
                embed.add_field(name="📋 Numbers", value=", ".join(str(i+1) for i in sorted(self.selected)) if self.selected else "None", inline=False)
                embed.set_footer(text=f"Select {remaining} more number{'s' if remaining > 1 else ''} to start!")
                await interaction.response.edit_message(embed=embed, view=self)

        async def start_game(self, interaction: discord.Interaction):
            if self.game_started:
                return

            if len(self.selected) != self.num_picks:
                return

            self.game_started = True

            # Disable all buttons to prevent further clicks
            for item in self.children:
                item.disabled = True

            # Deduct wager
            balances[self.user_id]["balance"] -= self.wager_usd
            balances[self.user_id]["wagered"] += self.wager_usd
            add_rakeback(self.user_id, self.wager_usd)
            save_balances(balances)

            # Draw 10 random numbers (winning numbers)
            winning_numbers = set(random.sample(range(25), 10))

            # Calculate matches
            matches = len(self.selected & winning_numbers)

            # Calculate payout based on matches and picks
            multipliers = {
                1: {1: 3.0},
                2: {1: 0, 2: 9.0},
                3: {1: 0, 2: 2.0, 3: 15.0},
                4: {1: 0, 2: 1.0, 3: 4.0, 4: 25.0},
                5: {2: 0.5, 3: 2.0, 4: 8.0, 5: 50.0},
                6: {2: 0.5, 3: 1.5, 4: 5.0, 5: 15.0, 6: 75.0},
                7: {3: 1.0, 4: 3.0, 5: 10.0, 6: 25.0, 7: 100.0},
                8: {4: 2.0, 5: 7.0, 6: 20.0, 7: 50.0, 8: 200.0},
                9: {5: 5.0, 6: 15.0, 7: 35.0, 8: 100.0, 9: 500.0},
                10: {5: 3.0, 6: 10.0, 7: 25.0, 8: 75.0, 9: 250.0, 10: 1000.0}
            }

            multiplier = multipliers.get(self.num_picks, {}).get(matches, 0)
            winnings_usd = self.wager_usd * multiplier

            if winnings_usd > 0:
                balances[self.user_id]["balance"] += winnings_usd
                color = 0x00ff00
                title = "🎰 Keno - WINNER! 🎉"
            else:
                color = 0xff0000
                title = "🎰 Keno - Try Again 😔"

            save_balances(balances)
            new_balance_usd = balances[self.user_id]["balance"]

            # Update grid to show results
            for item in self.children:
                if hasattr(item, 'custom_id') and item.custom_id.startswith('tile_'):
                    tile_id = int(item.custom_id.split('_')[1])
                    if tile_id in self.selected and tile_id in winning_numbers:
                        # Match!
                        item.style = discord.ButtonStyle.success
                        item.label = f"✓ {tile_id + 1}"
                    elif tile_id in winning_numbers:
                        # Winning number not selected
                        item.style = discord.ButtonStyle.danger
                        item.label = f"⭐ {tile_id + 1}"
                    elif tile_id in self.selected:
                        # Selected but not winning
                        item.style = discord.ButtonStyle.secondary
                        item.label = f"✗ {tile_id + 1}"
                    item.disabled = True

            embed = discord.Embed(title=title, color=color)
            embed.add_field(name="🎯 Matches", value=f"{matches}/{self.num_picks}", inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{multiplier:.1f}x", inline=True)
            embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD" if winnings_usd > 0 else "None", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
            embed.add_field(name="📋 Your Picks", value=", ".join(str(i+1) for i in sorted(self.selected)), inline=False)
            embed.add_field(name="⭐ Winning Numbers", value=", ".join(str(i+1) for i in sorted(winning_numbers)), inline=False)
            embed.set_footer(text="✓ = Match | ⭐ = Winning number | ✗ = Miss")

            await interaction.edit_original_response(embed=embed, view=self)

    # Initial display
    embed = discord.Embed(title="🎰 Keno - Select Your Numbers", color=0xff6600)
    embed.add_field(name="💰 Wager", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="🎯 Picks Required", value=f"{num_picks} numbers", inline=True)
    embed.add_field(name="📋 Selected", value="0 numbers", inline=True)
    embed.set_footer(text=f"Select {num_picks} number{'s' if num_picks > 1 else ''} to start the game!")

    view = KenoView(wager_usd, user_id, num_picks, None)
    await interaction.response.send_message(embed=embed, view=view)

# PLAYER STATS
@bot.tree.command(name="stats", description="View your player statistics")
async def stats(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user

    user_id = str(user.id)
    init_user(user_id)

    user_data = balances[user_id]
    rakeback_info = rakeback_data.get(user_id, {"total_wagered": 0.0, "rakeback_earned": 0.0})

    embed = discord.Embed(
        title=f"📊 Player Statistics - {user.display_name}",
        color=0x0099ff
    )

    embed.add_field(name="💰 Current Balance", value=f"${format_number(user_data['balance'])} USD", inline=True)
    embed.add_field(name="📥 Total Deposited", value=f"${format_number(user_data['deposited'])} USD", inline=True)
    embed.add_field(name="📤 Total Withdrawn", value=f"${format_number(user_data['withdrawn'])} USD", inline=True)
    embed.add_field(name="🎲 Total Wagered", value=f"${format_number(user_data['wagered'])} USD", inline=True)
    embed.add_field(name="💎 Rakeback Earned", value=f"${format_number(rakeback_info['rakeback_earned'])} USD", inline=True)

    # Calculate profit/loss
    profit_loss = user_data['balance'] + user_data['withdrawn'] - user_data['deposited']
    profit_loss_color = "🟢" if profit_loss >= 0 else "🔴"
    embed.add_field(name=f"{profit_loss_color} Profit/Loss", value=f"${format_number(profit_loss)} USD", inline=True)

    embed.set_footer(text="Keep playing to improve your stats!")

    await interaction.response.send_message(embed=embed)

# HELP
@bot.tree.command(name="help", description="View all available game modes and commands")
async def help_command(interaction: discord.Interaction):
    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    class HelpDropdown(discord.ui.Select):
        def __init__(self, is_admin):
            options = [
                discord.SelectOption(label="🎮 Games", description="View all casino games", emoji="🎮"),
                discord.SelectOption(label="💳 Account", description="Balance, deposit, withdraw commands", emoji="💳"),
                discord.SelectOption(label="🛠️ Utility", description="General utility commands", emoji="🛠️"),
            ]

            if is_admin:
                options.append(discord.SelectOption(label="👑 Admin", description="Admin-only commands", emoji="👑"))

            super().__init__(placeholder="Select a category...", options=options, row=0)

        async def callback(self, interaction: discord.Interaction):
            if self.values[0] == "🎮 Games":
                embed = discord.Embed(
                    title="🎮 Game Commands",
                    description="All available casino games:",
                    color=0x00ff00
                )
                embed.add_field(name="🪙 Coinflip", value="`/coinflip [amount]` - Choose heads or tails (80% RTP)", inline=False)
                embed.add_field(name="🎲 Dice", value="`/dice [amount]` - Battle the bot - highest roll wins! (80% RTP)", inline=False)
                embed.add_field(name="🤜 Rock Paper Scissors", value="`/rps [amount]` - Classic RPS (78% RTP)", inline=False)
                embed.add_field(name="🎰 Slots", value="`/slots [amount]` - Spin the reels for jackpots!", inline=False)
                embed.add_field(name="🃏 Blackjack", value="`/blackjack [amount]` - Beat the dealer with strategy!", inline=False)
                embed.add_field(name="🎴 Baccarat", value="`/baccarat [amount]` - Classic card game", inline=False)
                embed.add_field(name="💎 Mines", value="`/mines [amount] [mine_count]` - Find diamonds, avoid mines!", inline=False)
                embed.add_field(name="🏗️ Towers", value="`/towers [amount]` - Climb 8 levels choosing paths!", inline=False)
                embed.add_field(name="🌌 Limbo", value="`/limbo [amount] [multiplier]` - Cosmic multiplier game!", inline=False)
                embed.add_field(name="🏀 Plinko", value="`/plinko [amount] [rows] [difficulty]` - Drop a ball down!", inline=False)
                embed.add_field(name="🎈 Balloon", value="`/balloon [amount]` - Pump without popping!", inline=False)
                embed.add_field(name="🎰 Keno", value="`/keno [amount] [num_picks]` - Select numbers on a 5x5 grid!", inline=False)
                embed.set_footer(text="🎲 Minimum wager: $0.10 USD")

            elif self.values[0] == "💳 Account":
                embed = discord.Embed(
                    title="💳 Account Commands",
                    description="Manage your account and balance:",
                    color=0x0099ff
                )
                embed.add_field(name="💰 Balance", value="`/balance` - Check your balance and stats", inline=False)
                embed.add_field(name="📊 Stats", value="`/stats [user]` - View player statistics", inline=False)
                embed.add_field(name="💸 Tip", value="`/tip [user] [amount]` - Send money to another player", inline=False)
                embed.add_field(name="🎁 Claim Rakeback", value="`/claimrakeback` - Claim 0.5% of total wagered", inline=False)
                embed.add_field(name="🤝 Affiliate", value="`/affiliate [user]` - Earn 0.5% from their wagers", inline=False)
                embed.add_field(name="💳 Deposit", value="`/deposit` - Get your personal LTC deposit address", inline=False)
                embed.add_field(name="📤 Withdraw", value="`/withdraw [amount_usd] [ltc_address]` - Instant LTC withdrawal", inline=False)
                embed.set_footer(text="💡 Chat rewards: $0.10 per 100 messages")

            elif self.values[0] == "🛠️ Utility":
                embed = discord.Embed(
                    title="🛠️ Utility Commands",
                    description="General commands:",
                    color=0xff6600
                )
                embed.add_field(name="🆘 Help", value="`/help` - Show this help menu", inline=False)
                embed.add_field(name="💡 Info", value="• All amounts in USD\n• Min wager: $0.10\n• Rakeback: 0.5%\n• 1 second cooldown", inline=False)
                embed.set_footer(text="🎲 Good luck and gamble responsibly!")

            elif self.values[0] == "👑 Admin":
                embed = discord.Embed(
                    title="👑 Admin Commands",
                    description="Administrator-only commands:",
                    color=0xffd700
                )
                embed.add_field(name="💳 Add Balance", value="`/addbalance [user] [amount]` - Add balance to user", inline=False)
                embed.add_field(name="💸 Remove Balance", value="`/removebalance [user] [amount]` - Remove balance from user", inline=False)
                embed.add_field(name="🔄 Reset Stats", value="`/resetstats [user]` - Reset user's complete account", inline=False)
                embed.add_field(name="🏦 House Balance", value="`/housebalance` - Check house wallet balance", inline=False)
                embed.add_field(name="📤 House Withdraw", value="`/housewithdraw [ltc] [address]` - Withdraw from house", inline=False)
                embed.add_field(name="💰 House Deposit", value="`/housedosit` - Get house deposit address", inline=False)
                embed.set_footer(text="⚠️ Use admin commands responsibly")

            await interaction.response.edit_message(embed=embed, view=view)

    class HelpView(discord.ui.View):
        def __init__(self, is_admin):
            super().__init__(timeout=180)
            self.add_item(HelpDropdown(is_admin))

    # Initial embed
    embed = discord.Embed(
        title="🎮 VaultBet Help Menu",
        description="Welcome to VaultBet! Select a category below to view commands.",
        color=0x00ff00
    )
    embed.add_field(name="📋 Categories", value="🎮 **Games** - All casino games\n💳 **Account** - Balance & transactions\n🛠️ **Utility** - General commands" + ("\n👑 **Admin** - Admin commands" if is_admin(interaction.user.id) else ""), inline=False)
    embed.set_footer(text="Use the dropdown menu below to navigate")

    view = HelpView(is_admin(interaction.user.id))
    await interaction.response.send_message(embed=embed, view=view)

# RUN THE BOT
if __name__ == "__main__":
    if TOKEN:
        print("Starting VaultBet Discord Bot...")
        try:
            # Add a small delay before connecting
            import time
            time.sleep(5)
            bot.run(TOKEN, reconnect=True)
        except discord.errors.HTTPException as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                print("❌ Rate limited by Discord. Please wait 15-30 minutes before restarting.")
                print("   This happens when too many connection attempts are made.")
            else:
                print(f"❌ Discord connection error: {e}")
        except Exception as e:
            print(f"❌ Bot startup error: {e}")
    else:
        print("❌ No Discord token found! Please set DISCORD_BOT_TOKEN in your environment variables.")
