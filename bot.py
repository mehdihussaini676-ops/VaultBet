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
    """Parses a string amount with abbreviations (k, M, B) or 'half'/'all' into a float."""
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

async def auto_force_check_deposits():
    """Automatically check all addresses for confirmed transactions every 30 seconds"""
    try:
        if not ltc_handler:
            print("⚠️ auto_force_check_deposits: LTC handler not initialized.")
            return

        # Load all addresses
        try:
            with open('crypto_addresses.json', 'r') as f:
                address_mappings = json.load(f)
        except FileNotFoundError:
            print("⚠️ auto_force_check_deposits: crypto_addresses.json not found.")
            return

        processed_count = 0

        for address, addr_data in address_mappings.items():
            user_id = addr_data['user_id']

            try:
                # Get all transactions for this address
                async with aiohttp.ClientSession() as session:
                    url = f"{ltc_handler.base_url}/addrs/{address}/full"
                    async with session.get(url) as response:
                        if response.status == 200:
                            addr_full_data = await response.json()
                            transactions = addr_full_data.get('txs', [])

                            # Load existing processed transactions
                            try:
                                with open('pending_transactions.json', 'r') as f:
                                    pending = json.load(f)
                            except FileNotFoundError:
                                pending = {}

                            for tx in transactions:
                                tx_hash = tx['hash']
                                confirmations = tx.get('confirmations', 0)

                                # Skip if already processed
                                if tx_hash in pending and pending[tx_hash].get('confirmed') and pending[tx_hash].get('notification_sent'):
                                    continue

                                # Only process confirmed transactions
                                if confirmations >= 1:
                                    # Check if this is an incoming transaction
                                    incoming_amount = 0
                                    for output in tx.get('outputs', []):
                                        if address in output.get('addresses', []):
                                            incoming_amount += output.get('value', 0) / 100000000

                                    if incoming_amount > 0:
                                        # Convert to USD
                                        ltc_price = await get_ltc_price()
                                        amount_usd = incoming_amount * ltc_price

                                        # Update balance
                                        balances = load_balances()
                                        if user_id not in balances:
                                            balances[user_id] = {"balance": 0.0, "deposited": 0.0, "withdrawn": 0.0, "wagered": 0.0}

                                        old_balance = balances[user_id]["balance"]
                                        balances[user_id]["balance"] += amount_usd
                                        balances[user_id]["deposited"] += amount_usd
                                        save_balances(balances)

                                        print(f"🔄 AUTO: Processed {incoming_amount:.8f} LTC (${amount_usd:.2f}) for user {user_id}")

                                        # Send notification
                                        user = bot.get_user(int(user_id))
                                        if user:
                                            embed = discord.Embed(
                                                title="✅ Deposit Confirmed & Credited!",
                                                description="Your Litecoin deposit has been automatically processed",
                                                color=0x00ff00
                                            )
                                            embed.add_field(name="💰 Amount", value=f"{incoming_amount:.8f} LTC", inline=True)
                                            embed.add_field(name="💵 USD Value", value=f"${amount_usd:.2f} USD", inline=True)
                                            embed.add_field(name="🔗 Transaction", value=f"`{tx_hash[:16]}...`", inline=False)
                                            embed.add_field(name="✅ Confirmations", value=f"{confirmations}", inline=True)
                                            embed.add_field(name="🎮 Status", value="Balance updated - ready to play!", inline=True)
                                            embed.set_footer(text="Your deposit has been credited automatically!")

                                            try:
                                                await user.send(embed=embed)
                                                await log_deposit(user, amount_usd)
                                                print(f"✅ AUTO: Sent notification to user {user_id}")
                                            except discord.Forbidden:
                                                print(f"⚠️ Could not send DM to user {user_id} - DMs disabled")
                                            except Exception as dm_error:
                                                print(f"❌ Error sending DM: {dm_error}")

                                        # Forward funds to house wallet
                                        forwarding_success = False
                                        try:
                                            if ltc_handler and ltc_handler.house_wallet_address:
                                                private_key = addr_data.get('private_key')
                                                if private_key:
                                                    forward_tx = await ltc_handler.forward_to_house_wallet(address, private_key, incoming_amount)
                                                    if forward_tx:
                                                        print(f"✅ AUTO: Forwarded {incoming_amount:.8f} LTC to house wallet: {forward_tx}")
                                                        forwarding_success = True
                                                    else:
                                                        print(f"⚠️ AUTO: Failed to forward to house wallet")
                                                else:
                                                    print(f"⚠️ AUTO: No private key found for address {address}")
                                            else:
                                                print(f"⚠️ AUTO: House wallet not available for forwarding")
                                        except Exception as forward_error:
                                            print(f"❌ AUTO: Error forwarding to house wallet: {forward_error}")

                                        # Record as processed
                                        pending[tx_hash] = {
                                            'user_id': user_id,
                                            'address': address,
                                            'amount_ltc': incoming_amount,
                                            'confirmed': True,
                                            'notification_sent': True,
                                            'notification_processed': True,
                                            'processed_by': 'auto_check',
                                            'confirmations': confirmations,
                                            'timestamp': time.time(),
                                            'forwarded_to_house': forwarding_success
                                        }

                                        processed_count += 1

                            # Save updated pending transactions
                            if processed_count > 0:
                                with open('pending_transactions.json', 'w') as f:
                                    json.dump(pending, f, indent=2)

            except Exception as e:
                print(f"⚠️ auto_force_check_deposits: Error processing address {address}: {e}")
                continue  # Skip this address and continue with others

        if processed_count > 0:
            print(f"🔄 AUTO: Processed {processed_count} confirmed transactions")

    except Exception as e:
        print(f"❌ Error in auto force check: {e}")

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
        """Start webhook server in a separate process"""
        try:
            subprocess.Popen([sys.executable, "webhook_server.py"],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
            print("✅ Webhook server started on port 5000")
        except Exception as e:
            print(f"❌ Failed to start webhook server: {e}")

    # Start webhook server
    start_webhook_server()

    # Start notification checker
    asyncio.create_task(check_notifications())
    print("✅ Notification checker started")

    # Start auto deposit checker
    asyncio.create_task(auto_force_check_deposits())
    print("✅ Auto deposit checker started")

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

                        # Start blockchain monitoring in background
                        asyncio.create_task(ltc_handler.start_blockchain_monitoring())
                        print("✅ Blockchain monitoring started")
                    else:
                        print("⚠️ House wallet initialization failed - address generation will still work")
                except Exception as house_error:
                    print(f"⚠️ House wallet setup failed: {house_error}")
                    print("   Address generation will still work for deposits")

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

async def start_coinflip(interaction, choice, wager_usd, user_id):
    
    # Generate coin flip result first
    coin_flip = random.choice(["heads", "tails"])
    
    # Create coin flip image
    coinflip_img_path = f"coinflip_{user_id}_{time.time()}.png"
    game_img_gen.create_coinflip_image(coin_flip, choice, coinflip_img_path)

    # Start with animation
    embed = discord.Embed(title="🪙 Coinflip - Flipping...", color=0xffaa00)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="🎯 Your Call", value=choice.title(), inline=True)
    embed.add_field(name="⏳ Status", value="🪙 Coin is spinning...", inline=False)

    # Add the coin flip animation image
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

    # coin_flip already defined at the start of function
    won = coin_flip == choice.lower()

    if won:
        # 80% RTP - pay out 0.80x for wins (20% house edge)
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
    add_rakeback(user_id, wager_usd)  # Add rakeback
    save_balances(balances)

    # Create visual representation
    coin_visual = "🪙" if coin_flip == "heads" else "🟡"
    choice_visual = "🪙" if choice.lower() == "heads" else "🟡"

    embed = discord.Embed(title=title, color=color)

    # Visual section
    visual_text = f"""
**Your Call:** {choice.title()} {choice_visual}
**Result:** {coin_flip.title()} {coin_visual}

{coin_visual} ← **The coin landed here!**
    """

    embed.add_field(name="🃏 Coinflip Visual", value=visual_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

    # Attach image if it exists
    files = []
    if os.path.exists(coinflip_img_path):
        files.append(discord.File(coinflip_img_path, filename="coinflip.png"))
        embed.set_image(url="attachment://coinflip.png")

    # Create play again buttons
    class CoinflipPlayAgainView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=300)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="🪙 Play Again - Heads", style=discord.ButtonStyle.primary)
        async def play_again_heads(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            # Start new coinflip with heads
            await start_new_coinflip(interaction, "heads", self.wager_usd, self.user_id)

        @discord.ui.button(label="🪙 Play Again - Tails", style=discord.ButtonStyle.primary)
        async def play_again_tails(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            # Start new coinflip with tails
            await start_new_coinflip(interaction, "tails", self.wager_usd, self.user_id)

    async def start_new_coinflip(interaction, choice, wager_usd, user_id):
        # Start with animation
        embed = discord.Embed(title="🪙 Coinflip - Flipping...", color=0xffaa00)
        embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
        embed.add_field(name="🎯 Your Call", value=choice.title(), inline=True)
        embed.add_field(name="⏳ Status", value="🪙 Coin is spinning...", inline=False)

        # Add the coin flip animation image
        coin_flip_file = None
        files = []
        if os.path.exists("attached_assets"):
            for filename in os.listdir("attached_assets"):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    coin_flip_file = discord.File(f"attached_assets/{filename}", filename="coinflip.gif")
                    embed.set_image(url="attachment://coinflip.gif")
                    files.append(coin_flip_file)
                    break

        try:
            await interaction.response.edit_message(embed=embed, attachments=files, view=None)
        except:
            await interaction.edit_original_response(embed=embed, attachments=files, view=None)

        # Animation frames
        frames = [
            "🪙 FLIPPING...",
            "🔄 SPINNING...",
            "🪙 TUMBLING...",
            "✨ LANDING..."
        ]

        for i, frame in enumerate(frames):
            embed.set_field_at(2, name="⏳ Status", value=f"{frame}", inline=False)
            if i == len(frames) - 1:
                embed.set_image(url=None)
            try:
                await interaction.edit_original_response(embed=embed, attachments=[]) # Remove attachments on subsequent edits
            except:
                pass # Ignore if edit fails
            await asyncio.sleep(0.8)

        # Game logic
        coin_flip = random.choice(["heads", "tails"])
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

        # Attach image if it exists
        files = []
        if os.path.exists(coinflip_img_path):
            files.append(discord.File(coinflip_img_path, filename="coinflip.png"))
            embed.set_image(url="attachment://coinflip.png")

        # Add play again buttons
        play_again_view = CoinflipPlayAgainView(wager_usd, user_id)
        await interaction.edit_original_response(embed=embed, view=play_again_view, attachments=files)

    # Add play again buttons to current result
    play_again_view = CoinflipPlayAgainView(wager_usd, user_id)
    await interaction.edit_original_response(embed=embed, view=play_again_view, attachments=files)
    if os.path.exists(coinflip_img_path): # Clean up image file
        try:
            os.remove(coinflip_img_path)
        except:
            pass


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
        await interaction.response.edit_message(embed=embed, view=play_again_view, attachments=files)

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
async def rps(interaction: discord.Interaction, wager_amount: str, choice: str):
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

    if choice.lower() not in ["rock", "paper", "scissors"]:
        await interaction.response.send_message("❌ Please choose either 'rock', 'paper', or 'scissors'!", ephemeral=True)
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

    choices = ["rock", "paper", "scissors"]
    bot_choice = random.choice(choices)
    user_choice = choice.lower()

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
        winnings_usd = wager_usd * 0.78
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
    add_rakeback(user_id, wager_usd)  # Add rakeback
    save_balances(balances)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

    # Create and attach RPS image
    rps_img_path = f"rps_{user_id}_{time.time()}.png"
    game_img_gen.create_rps_image(user_choice, bot_choice, rps_img_path)
    
    files = []
    if os.path.exists(rps_img_path) and os.path.getsize(rps_img_path) > 0:
        files.append(discord.File(rps_img_path, filename="rps.png"))
        embed.set_image(url="attachment://rps.png")

    # Create play again view
    class RPSPlayAgainView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=300)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="🤜 Play Again - Rock", style=discord.ButtonStyle.secondary)
        async def play_again_rock(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            await start_new_rps_game(interaction, "rock", self.wager_usd, self.user_id)

        @discord.ui.button(label="📄 Play Again - Paper", style=discord.ButtonStyle.secondary)
        async def play_again_paper(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            await start_new_rps_game(interaction, "paper", self.wager_usd, self.user_id)

        @discord.ui.button(label="✂️ Play Again - Scissors", style=discord.ButtonStyle.secondary)
        async def play_again_scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            await start_new_rps_game(interaction, "scissors", self.wager_usd, self.user_id)

    async def start_new_rps_game(interaction, choice, wager_usd, user_id):
        choices = ["rock", "paper", "scissors"]
        bot_choice = random.choice(choices)
        user_choice = choice.lower()

        choice_emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        win_map = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

        if bot_choice == user_choice:
            new_balance_usd = balances[user_id]["balance"]
            color = 0xffff00
            title = "🤝 Rock Paper Scissors - It's a Tie!"
            result_text = f"You both chose **{user_choice}** {choice_emojis[user_choice]}!"
        elif win_map[user_choice] == bot_choice:
            winnings_usd = wager_usd * 0.78
            balances[user_id]["balance"] += winnings_usd
            new_balance_usd = balances[user_id]["balance"]
            color = 0x00ff00
            title = "🤜 Rock Paper Scissors - YOU WON! 🎉"
            result_text = f"Your **{user_choice}** {choice_emojis[user_choice]} beats **{bot_choice}** {choice_emojis[bot_choice]}!"
        else:
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

        # Attach RPS image
        rps_img_path = f"rps_{user_id}_{time.time()}.png"
        files = []
        if os.path.exists(rps_img_path) and os.path.getsize(rps_img_path) > 0:
            files.append(discord.File(rps_img_path, filename="rps.png"))
            embed.set_image(url="attachment://rps.png")

        play_again_view = RPSPlayAgainView(wager_usd, user_id)
        await interaction.response.edit_message(embed=embed, view=play_again_view, attachments=files)

    play_again_view = RPSPlayAgainView(wager_usd, user_id)
    await interaction.response.send_message(embed=embed, view=play_again_view, files=files)
    if os.path.exists(rps_img_path): # Clean up image file
        try:
            os.remove(rps_img_path)
        except:
            pass

# WITHDRAW COMMAND
@bot.tree.command(name="withdraw", description="Withdraw your balance in Litecoin (automatic processing)")
async def withdraw(interaction: discord.Interaction, amount_usd: float, ltc_address: str):
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

    # Validate LTC address format (basic check)
    if not ltc_address.startswith('L') or len(ltc_address) < 26:
        await interaction.response.send_message("❌ Invalid Litecoin address! Please check and try again.", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        # Get current LTC price and calculate amount
        ltc_price = await get_ltc_price()
        amount_ltc = amount_usd / ltc_price

        # Check if crypto handler is available
        if not ltc_handler:
            await interaction.followup.send("❌ Crypto system is currently unavailable. Please use manual deposits with an admin.", ephemeral=True)
            return

        # Check house wallet balance
        house_balance_ltc = await ltc_handler.get_house_balance()
        if house_balance_ltc < amount_ltc:
            await interaction.followup.send("❌ Insufficient house wallet balance. Please contact an admin.", ephemeral=True)
            return

        # Process withdrawal from house wallet
        tx_hash = await ltc_handler.withdraw_from_house_wallet(ltc_address, amount_ltc)

        if tx_hash:
            # Deduct from user balance
            balances[user_id]["balance"] -= amount_usd
            balances[user_id]["withdrawn"] += amount_usd
            save_balances(balances)

            # Update house balance stats
            house_stats = load_house_balance()
            house_stats['total_withdrawals'] += amount_usd
            save_house_balance(house_stats)

            # Create unique withdrawal ID
            withdrawal_id = f"WD-{int(time.time())}-{user_id[-6:]}"

            # Send success message
            embed = discord.Embed(
                title="✅ Withdrawal Processed Successfully!",
                description="Your Litecoin withdrawal has been sent",
                color=0x00ff00
            )
            embed.add_field(name="💰 Amount", value=f"{amount_ltc:.8f} LTC", inline=True)
            embed.add_field(name="💵 USD Value", value=f"${amount_usd:.2f} USD", inline=True)
            embed.add_field(name="📍 Destination", value=f"`{ltc_address[:16]}...{ltc_address[-8:]}`", inline=False)
            embed.add_field(name="🔗 Transaction Hash", value=f"`{tx_hash[:16]}...{tx_hash[-8:]}`", inline=False)
            embed.add_field(name="🆔 Withdrawal ID", value=f"`{withdrawal_id}`", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(balances[user_id]['balance'])} USD", inline=True)
            embed.set_footer(text="Withdrawal processed automatically")

            await interaction.followup.send(embed=embed)

            # Log withdrawal
            await log_withdraw(interaction.user, amount_usd, ltc_address)

        else:
            await interaction.followup.send("❌ Failed to process withdrawal. Please try again later or contact an admin.", ephemeral=True)

    except Exception as e:
        print(f"Error processing withdrawal: {e}")
        await interaction.followup.send("❌ An error occurred processing your withdrawal. Please contact an admin.", ephemeral=True)



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

        await interaction.followup.send(embed=embed, ephemeral=True)

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

    # Spinning animation frames
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

    play_again_view = SlotsPlayAgainView(wager_usd, user_id)
    await interaction.edit_original_response(embed=embed, view=play_again_view, attachments=files if files else [])
    
    # Clean up image
    if os.path.exists(slots_img_path):
        try:
            os.remove(slots_img_path)
        except:
            pass

# BlackjackView class definition
class BlackjackView(discord.ui.View):
    def __init__(self, player_hand, dealer_hand, deck, wager_usd, user_id):
        super().__init__(timeout=180)
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.deck = deck
        self.wager_usd = wager_usd
        self.user_id = user_id
        self.game_over = False

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.user_id) or self.game_over:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        self.player_hand.append(self.deck.pop())
        player_value = card_generator.hand_value(self.player_hand)

        if player_value > 21:
            # Bust
            self.game_over = True
            self.clear_items()

            balances[self.user_id]["balance"] -= self.wager_usd
            save_balances(balances)
            new_balance = balances[self.user_id]["balance"]

            embed = discord.Embed(title="🃏 Blackjack - BUST! 💥", color=0xff0000)
            embed.add_field(name="🃏 Your Hand", value=f"{card_generator.format_hand(self.player_hand)} = {player_value}", inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand)} = {card_generator.hand_value(self.dealer_hand)}", inline=True)
            embed.add_field(name="💸 Lost", value=f"${self.wager_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance)} USD", inline=True)

            # Generate updated card image for bust (show all cards)
            bust_img = f"bust_blackjack_{self.user_id}.png"
            files = []
            try:
                temp_generator = CardImageGenerator()
                temp_generator.save_blackjack_game_image([self.player_hand], self.dealer_hand, bust_img, 0, hide_dealer_first=False)
                files.append(discord.File(bust_img, filename="blackjack_bust.png"))
                embed.set_image(url="attachment://blackjack_bust.png")
            except Exception as e:
                print(f"Error creating bust image: {e}")

            await interaction.response.edit_message(embed=embed, view=self, attachments=files)
            
            # Schedule cleanup after Discord finishes sending
            async def cleanup_later():
                await asyncio.sleep(2)
                if os.path.exists(bust_img):
                    try:
                        os.remove(bust_img)
                    except:
                        pass
            asyncio.create_task(cleanup_later())
        else:
            embed = discord.Embed(title="🃏 Blackjack - Your Turn", color=0x0099ff)
            embed.add_field(name="🃏 Your Hand", value=f"{card_generator.format_hand(self.player_hand)} = **{player_value}**", inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand, hide_first=True)} = **?**", inline=True)
            embed.add_field(name="💰 Wager", value=f"${self.wager_usd:.2f} USD", inline=True)

            # Generate updated card image for hit
            hit_img = f"hit_blackjack_{self.user_id}.png"
            files = []
            try:
                temp_generator = CardImageGenerator()
                temp_generator.save_blackjack_game_image([self.player_hand], self.dealer_hand, hit_img, 0, hide_dealer_first=True)
                files.append(discord.File(hit_img, filename="blackjack_hit.png"))
                embed.set_image(url="attachment://blackjack_hit.png")
            except Exception as e:
                print(f"Error creating hit image: {e}")

            await interaction.response.edit_message(embed=embed, view=self, attachments=files)
            
            # Schedule cleanup after Discord finishes sending
            async def cleanup_later():
                await asyncio.sleep(2)
                if os.path.exists(hit_img):
                    try:
                        os.remove(hit_img)
                    except:
                        pass
            asyncio.create_task(cleanup_later())

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.user_id) or self.game_over:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        self.game_over = True
        self.clear_items()

        # Dealer plays
        dealer_value = card_generator.hand_value(self.dealer_hand)
        while dealer_value < 17:
            self.dealer_hand.append(self.deck.pop())
            dealer_value = card_generator.hand_value(self.dealer_hand)

        player_value = card_generator.hand_value(self.player_hand)

        if dealer_value > 21 or player_value > dealer_value:
            winnings = self.wager_usd * 2
            balances[self.user_id]["balance"] += winnings
            color = 0x00ff00
            title = "🃏 Blackjack - YOU WON! 🎉"
        elif player_value == dealer_value:
            balances[self.user_id]["balance"] += self.wager_usd
            color = 0xffff00
            title = "🃏 Blackjack - Push! 🤝"
        else:
            balances[self.user_id]["balance"] -= self.wager_usd
            color = 0xff0000
            title = "🃏 Blackjack - Dealer Wins 😔"

        save_balances(balances)
        new_balance = balances[self.user_id]["balance"]

        embed = discord.Embed(title=title, color=color)
        embed.add_field(name="🃏 Your Hand", value=f"{card_generator.format_hand(self.player_hand)} = {player_value}", inline=True)
        embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(self.dealer_hand)} = {dealer_value}", inline=True)
        embed.add_field(name="💰 Wagered", value=f"${self.wager_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance)} USD", inline=True)

        # Generate final game state image (reveal all cards)
        stand_img = f"stand_blackjack_{self.user_id}.png"
        files = []
        try:
            temp_generator = CardImageGenerator()
            temp_generator.save_blackjack_game_image([self.player_hand], self.dealer_hand, stand_img, 0, hide_dealer_first=False)
            files.append(discord.File(stand_img, filename="blackjack_result.png"))
            embed.set_image(url="attachment://blackjack_result.png")
        except Exception as e:
            print(f"Error creating stand image: {e}")

        await interaction.response.edit_message(embed=embed, view=self, attachments=files)
        
        # Schedule cleanup after Discord finishes sending
        async def cleanup_later():
            await asyncio.sleep(2)
            if os.path.exists(stand_img):
                try:
                    os.remove(stand_img)
                except:
                    pass
        asyncio.create_task(cleanup_later())

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

    # Create deck
    suits = ['♠️', '♥️', '♦️', '♣️']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    deck = [(rank, suit) for suit in suits for rank in ranks]
    random.shuffle(deck)

    # Deal initial cards
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    # Check for initial blackjack
    player_blackjack = card_generator.hand_value(player_hand) == 21
    dealer_blackjack = card_generator.hand_value(dealer_hand) == 21

    if player_blackjack or dealer_blackjack:
        # Handle blackjack scenarios immediately
        if player_blackjack and dealer_blackjack:
            # Push - return wager
            new_balance_usd = balances[user_id]["balance"]
            color = 0xffff00
            title = "🃏 Blackjack - Push! 🤝"
            result_text = "Both you and the dealer have Blackjack!"
        elif player_blackjack:
            # Player wins with blackjack (1.5x payout)
            winnings_usd = wager_usd * 1.5
            balances[user_id]["balance"] += winnings_usd
            new_balance_usd = balances[user_id]["balance"]
            color = 0x00ff00
            title = "🃏 BLACKJACK! 🎉"
            result_text = f"You got Blackjack! Won ${winnings_usd:.2f} USD (1.5x payout)!"
        else:
            # Dealer has blackjack, player loses
            balances[user_id]["balance"] -= wager_usd
            new_balance_usd = balances[user_id]["balance"]
            color = 0xff0000
            title = "🃏 Blackjack - Dealer Wins 😔"
            result_text = "Dealer has Blackjack!"

        balances[user_id]["wagered"] += wager_usd
        add_rakeback(user_id, wager_usd)  # Add rakeback
        save_balances(balances)

        embed = discord.Embed(title=title, color=color)
        embed.add_field(name="🃏 Your Hand", value=f"{card_generator.format_hand(player_hand)} = {card_generator.hand_value(player_hand)}", inline=True)
        embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(dealer_hand)} = {card_generator.hand_value(dealer_hand)}", inline=True)
        embed.add_field(name="🎯 Result", value=result_text, inline=False)
        embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
        embed.set_footer(text="Blackjack pays 1.5x")

        # Create play again view for blackjack
        class BlackjackPlayAgainView(discord.ui.View):
            def __init__(self, wager_usd, user_id):
                super().__init__(timeout=300)
                self.wager_usd = wager_usd
                self.user_id = user_id

            @discord.ui.button(label="🃏 Play Again", style=discord.ButtonStyle.primary)
            async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != int(self.user_id):
                    await interaction.response.send_message("This is not your game!", ephemeral=True)
                    return

                if balances[self.user_id]["balance"] < self.wager_usd:
                    current_balance_usd = balances[self.user_id]["balance"]
                    await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                    return

                await start_new_blackjack_game(interaction, self.wager_usd, self.user_id)

        async def start_new_blackjack_game(interaction, wager_usd, user_id):
            # Deduct the initial wager when starting the game
            balances[user_id]["balance"] -= wager_usd
            save_balances(balances)

            # Create deck
            suits = ['♠️', '♥️', '♦️', '♣️']
            ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
            deck = [(rank, suit) for suit in suits for rank in ranks]
            random.shuffle(deck)

            # Deal initial cards
            player_hand = [deck.pop(), deck.pop()]
            dealer_hand = [deck.pop(), deck.pop()]

            # Check for initial blackjack
            player_blackjack = card_generator.hand_value(player_hand) == 21
            dealer_blackjack = card_generator.hand_value(dealer_hand) == 21

            if player_blackjack or dealer_blackjack:
                if player_blackjack and dealer_blackjack:
                    new_balance_usd = balances[user_id]["balance"]
                    color = 0xffff00
                    title = "🃏 Blackjack - Push! 🤝"
                    result_text = "Both you and the dealer have Blackjack!"
                elif player_blackjack:
                    winnings_usd = wager_usd * 1.5
                    balances[user_id]["balance"] += winnings_usd
                    new_balance_usd = balances[user_id]["balance"]
                    color = 0x00ff00
                    title = "🃏 BLACKJACK! 🎉"
                    result_text = f"You got Blackjack! Won ${winnings_usd:.2f} USD (1.5x payout)!"
                else:
                    balances[user_id]["balance"] -= wager_usd
                    new_balance_usd = balances[user_id]["balance"]
                    color = 0xff0000
                    title = "🃏 Blackjack - Dealer Wins 😔"
                    result_text = "Dealer has Blackjack!"

                balances[user_id]["wagered"] += wager_usd
                add_rakeback(user_id, wager_usd)
                save_balances(balances)

                embed = discord.Embed(title=title, color=color)
                embed.add_field(name="🃏 Your Hand", value=f"{card_generator.format_hand(player_hand)} = {card_generator.hand_value(player_hand)}", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(dealer_hand)} = {card_generator.hand_value(dealer_hand)}", inline=True)
                embed.add_field(name="🎯 Result", value=result_text, inline=False)
                embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
                embed.set_footer(text="Blackjack pays 1.5x")

                play_again_view = BlackjackPlayAgainView(wager_usd, user_id)
                await interaction.response.edit_message(embed=embed, view=play_again_view)
                return

            # Create view for interactive game
            temp_generator = CardImageGenerator()
            initial_img = f"initial_blackjack_{user_id}.png"

            try:
                temp_generator.save_blackjack_game_image([player_hand], dealer_hand, initial_img, 0, hide_dealer_first=True)
            except Exception as e:
                print(f"Error creating initial blackjack image: {e}")

            embed = discord.Embed(title="🃏 Blackjack - Your Turn", color=0x0099ff)
            embed.add_field(name="🃏 Your Hand", value=f"{card_generator.format_hand(player_hand)} = **{card_generator.hand_value(player_hand)}**", inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(dealer_hand, hide_first=True)} = **?**", inline=True)
            embed.add_field(name="💰 Wager", value=f"${wager_usd:.2f} USD", inline=True)
            embed.set_footer(text="Hit: take another card | Stand: keep your hand")

            files = []
            if os.path.exists(initial_img):
                files.append(discord.File(initial_img, filename="blackjack_start.png"))
                embed.set_image(url="attachment://blackjack_start.png")

            view = BlackjackView(player_hand, dealer_hand, deck, wager_usd, user_id)

            try:
                await interaction.response.edit_message(embed=embed, view=view, attachments=files)
                if os.path.exists(initial_img):
                    try:
                        os.remove(initial_img)
                    except:
                        pass
            except Exception as e:
                # Fallback if image creation failed
                await interaction.response.edit_message(embed=embed, view=view)

        # Add play again to initial blackjack result
        if player_blackjack or dealer_blackjack:
            play_again_view = BlackjackPlayAgainView(wager_usd, user_id)
            await interaction.response.send_message(embed=embed, view=play_again_view)
            return

        # If not initial blackjack, send the interactive game view
        await interaction.response.send_message(embed=embed, view=view)
        return

    # Create initial comprehensive game image
    temp_generator = CardImageGenerator()
    initial_img = f"initial_blackjack_{user_id}.png"

    try:
        temp_generator.save_blackjack_game_image([player_hand], dealer_hand, initial_img, 0, hide_dealer_first=True)
    except Exception as e:
        print(f"Error creating initial blackjack image: {e}")

    # Create initial embed
    embed = discord.Embed(title="🃏 Blackjack - Your Turn", color=0x0099ff)
    embed.add_field(name="🃏 Your Hand", value=f"{card_generator.format_hand(player_hand)} = **{card_generator.hand_value(player_hand)}**", inline=True)
    embed.add_field(name="🤖 Dealer Hand", value=f"{card_generator.format_hand(dealer_hand, hide_first=True)} = **?**", inline=True)
    embed.add_field(name="💰 Wager", value=f"${wager_usd:.2f} USD", inline=True)
    embed.set_footer(text="Hit: take another card | Stand: keep hand | Double Down: double bet + 1 card")

    # Add comprehensive game image
    files = []
    if os.path.exists(initial_img):
        files.append(discord.File(initial_img, filename="blackjack_start.png"))
        embed.set_image(url="attachment://blackjack_start.png")

    view = BlackjackView(player_hand, dealer_hand, deck, wager_usd, user_id)

    try:
        await interaction.response.send_message(embed=embed, view=view, files=files)

        # Clean up image file
        if os.path.exists(initial_img):
            try:
                os.remove(initial_img)
            except:
                pass
    except Exception as e:
        # Fallback without images
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

    # Show difficulty selection
    class TowersDifficultyView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=60)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="Easy (2 paths)", style=discord.ButtonStyle.success, emoji="🟢")
        async def easy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_towers_game(interaction, 2, self.wager_usd, self.user_id)

        @discord.ui.button(label="Medium (3 paths)", style=discord.ButtonStyle.primary, emoji="🟡")
        async def medium_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_towers_game(interaction, 3, self.wager_usd, self.user_id)

        @discord.ui.button(label="Hard (4 paths)", style=discord.ButtonStyle.danger, emoji="🔴")
        async def hard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_towers_game(interaction, 4, self.wager_usd, self.user_id)

    embed = discord.Embed(title="🏗️ Towers - Choose Difficulty", color=0x0099ff)
    embed.add_field(name="💰 Wager", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="🟢 Easy", value="2 paths per level\nHigher win chance", inline=True)
    embed.add_field(name="🟡 Medium", value="3 paths per level\nBalanced gameplay", inline=True)
    embed.add_field(name="🔴 Hard", value="4 paths per level\nHigher rewards!", inline=True)
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

    # Generate tower structure - 8 levels, each with 'difficulty' number of paths
    tower_structure = []
    for level in range(8):
        correct_path = random.randint(0, difficulty - 1)
        tower_structure.append(correct_path)

    def get_tower_multiplier(level, difficulty):
        base_multiplier = 1.0
        level_bonus = level * (0.10 + (difficulty - 2) * 0.02)
        return round(base_multiplier + level_bonus, 2)

    # Create initial embed
    embed = discord.Embed(title="🏗️ Towers - Level 1/8", color=0x0099ff)
    embed.add_field(name="💰 Bet", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="⚡ Difficulty", value=f"{difficulty} paths per level", inline=True)
    embed.add_field(name="📈 Multiplier", value="1.00x", inline=True)
    embed.add_field(name="🎯 Objective", value="Choose the correct path to climb!", inline=True)
    embed.add_field(name="💎 Current Winnings", value="NONE", inline=True)
    embed.add_field(name="🏢 Progress", value="0/8 levels", inline=True)
    embed.set_footer(text="Choose wisely! Only 1 path per level is correct.")

    class TowersView(discord.ui.View):
        def __init__(self, tower_structure, wager_usd, user_id, difficulty):
            super().__init__(timeout=300)
            self.tower_structure = tower_structure
            self.wager_usd = wager_usd
            self.user_id = user_id
            self.difficulty = difficulty
            self.current_level = 0
            self.game_over = False
            self.current_multiplier = 1.0

            self.setup_level()

        def setup_level(self):
            self.clear_items()

            if self.current_level >= 8:
                return

            for path in range(min(self.difficulty, 4)):
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
            correct_path = self.tower_structure[self.current_level]

            if chosen_path == correct_path:
                self.current_level += 1
                self.current_multiplier = get_tower_multiplier(self.current_level, self.difficulty)

                if self.current_level >= 8:
                    self.game_over = True
                    final_multiplier = get_tower_multiplier(8, self.difficulty)
                    winnings_usd = self.wager_usd * final_multiplier
                    balances[self.user_id]["balance"] += winnings_usd
                    save_balances(balances)

                    new_balance_usd = balances[self.user_id]["balance"]

                    embed = discord.Embed(title="🏗️ Towers - TOWER COMPLETED! 🎉", color=0xffd700)
                    embed.add_field(name="🏢 Level Reached", value="8/8 (TOP!)", inline=True)
                    embed.add_field(name="⚡ Difficulty", value=f"{self.difficulty} paths", inline=True)
                    embed.add_field(name="📈 Final Multiplier", value=f"{final_multiplier:.2f}x", inline=True)
                    embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
                    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
                    embed.set_footer(text="Congratulations!")

                    self.clear_items()
                    await interaction.response.edit_message(embed=embed)
                    return
                else:
                    self.setup_level()

                    current_winnings_usd = self.wager_usd * self.current_multiplier

                    embed = discord.Embed(title="🏗️ Towers - Correct Path! ✅", color=0x00ff00)
                    embed.add_field(name="🏢 Current Level", value=f"{self.current_level}/8", inline=True)
                    embed.add_field(name="⚡ Difficulty", value=f"{self.difficulty} paths", inline=True)
                    embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
                    embed.add_field(name="💎 Current Winnings", value=f"${format_number(current_winnings_usd)} USD", inline=True)
                    embed.add_field(name="🎯 Next Level", value=f"Choose 1 of {self.difficulty} paths", inline=True)
                    embed.set_footer(text="Choose the correct path to continue climbing!")

                    await interaction.response.edit_message(embed=embed)
            else:
                self.game_over = True
                new_balance_usd = balances[self.user_id]["balance"]

                embed = discord.Embed(title="🏗️ Towers - Wrong Path! ❌", color=0xff0000)
                embed.add_field(name="🏢 Level Reached", value=f"{self.current_level}/8", inline=True)
                embed.add_field(name="⚡ Difficulty", value=f"{self.difficulty} paths", inline=True)
                embed.add_field(name="🚪 Chosen Path", value=f"Path {chosen_path + 1}", inline=True)
                embed.add_field(name="✅ Correct Path", value=f"Path {correct_path + 1}", inline=True)
                embed.add_field(name="💸 Result", value=f"Lost ${self.wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

                self.clear_items()
                await interaction.response.edit_message(embed=embed)

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

            winnings_usd = self.wager_usd * self.current_multiplier
            balances[self.user_id]["balance"] += winnings_usd
            save_balances(balances)

            new_balance_usd = balances[self.user_id]["balance"]

            embed = discord.Embed(title="💰 Towers - Cashed Out! 🎉", color=0x00ff00)
            embed.add_field(name="🏢 Level Reached", value=f"{self.current_level}/8", inline=True)
            embed.add_field(name="⚡ Difficulty", value=f"{self.difficulty} paths", inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
            embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
            embed.set_footer(text="Smart move!")

            # Create play again view
            class TowersPlayAgainView(discord.ui.View):
                def __init__(self, wager_usd, difficulty, user_id):
                    super().__init__(timeout=300)
                    self.wager_usd = wager_usd
                    self.difficulty = difficulty
                    self.user_id = user_id

                @discord.ui.button(label="🏗️ Play Again", style=discord.ButtonStyle.primary)
                async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != int(self.user_id):
                        await interaction.response.send_message("This is not your game!", ephemeral=True)
                        return

                    if balances[self.user_id]["balance"] < self.wager_usd:
                        current_balance_usd = balances[self.user_id]["balance"]
                        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                        return

                    await start_new_towers_game(interaction, self.wager_usd, self.difficulty, self.user_id)

            async def start_new_towers_game(interaction, wager_usd, difficulty, user_id):
                # Deduct wager
                balances[user_id]["balance"] -= wager_usd
                balances[user_id]["wagered"] += wager_usd
                add_rakeback(user_id, wager_usd)
                save_balances(balances)

                # Generate tower structure
                tower_structure = []
                for level in range(8):
                    correct_path = random.randint(0, difficulty - 1)
                    tower_structure.append(correct_path)

                # Create initial embed
                embed = discord.Embed(title="🏗️ Towers - Level 1/8", color=0x0099ff)
                embed.add_field(name="💰 Bet", value=f"${wager_usd:.2f} USD", inline=True)
                embed.add_field(name="⚡ Difficulty", value=f"{difficulty} paths per level", inline=True)
                embed.add_field(name="📈 Multiplier", value="1.00x", inline=True)
                embed.add_field(name="🎯 Objective", value="Choose the correct path to climb!", inline=True)
                embed.add_field(name="💎 Current Winnings", value="NONE", inline=True)
                embed.add_field(name="🏢 Progress", value="0/8 levels", inline=True)
                embed.set_footer(text="Choose wisely! Only 1 path per level is correct.")

                view = TowersView(tower_structure, wager_usd, user_id, difficulty)
                await interaction.response.edit_message(embed=embed, view=view)

            play_again_view = TowersPlayAgainView(self.wager_usd, self.difficulty, self.user_id)
            await interaction.response.edit_message(embed=embed, view=play_again_view)

    view = TowersView(tower_structure, wager_usd, user_id, difficulty)
    await interaction.response.edit_message(embed=embed, view=view)

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

    # Deduct wager at the start of the game
    balances[user_id]["balance"] -= wager_usd
    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

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
            winnings_usd = wager_usd * multiplier * 0.85
            balances[user_id]["balance"] += winnings_usd
            new_balance_usd = balances[user_id]["balance"]

            embed = discord.Embed(title="🏀 Plinko - WINNER! 🎉", color=0x00ff00)
            embed.add_field(name="📍 Final Bucket", value=f"Position {final_position + 1}/{num_buckets}", inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{multiplier}x", inline=True)
            embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
            embed.add_field(name="🏀 Result", value="🎊 Ball landed in a winning bucket! 🎊", inline=False)
        else:
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

    # Get house balance from blockchain
    house_balance_ltc = await ltc_handler.get_house_balance()
    ltc_price = await get_ltc_price()
    house_balance_usd = house_balance_ltc * ltc_price

    # Load house balance stats
    house_stats = load_house_balance()

    # Create house balance image
    from balance_generator import HouseBalanceImageGenerator
    house_balance_gen = HouseBalanceImageGenerator()

    image_path = f"house_balance_{time.time()}.png"
    success = house_balance_gen.create_house_balance_image(
        house_balance_ltc=house_balance_ltc,
        house_balance_usd=house_balance_usd,
        total_deposits=house_stats['total_deposits'],
        total_withdrawals=house_stats['total_withdrawals'],
        ltc_price=ltc_price,
        wallet_address=ltc_handler.house_wallet_address,
        save_path=image_path
    )

    if success and os.path.exists(image_path):
        file = discord.File(image_path, filename="house_balance.png")
        await interaction.response.send_message(file=file, ephemeral=True)

        # Clean up image
        try:
            os.remove(image_path)
        except:
            pass
    else:
        # Fallback to embed if image generation fails
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

        await interaction.response.send_message(embed=embed, ephemeral=True)

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

# HOUSE DEPOSIT
@bot.tree.command(name="housedeposit", description="Admin command to get house wallet deposit address")
async def housedeposit(interaction: discord.Interaction):
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
async def baccarat(interaction: discord.Interaction, wager_amount: str, bet_on: str):
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

    if bet_on.lower() not in ["player", "banker", "tie"]:
        await interaction.response.send_message("❌ Please bet on 'player', 'banker', or 'tie'!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        await interaction.response.send_message(f"❌ Insufficient balance!", ephemeral=True)
        return

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
    embed.add_field(name="🎯 Your Bet", value=bet.title(), inline=True)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

    # Create baccarat image using game image generator
    baccarat_img_path = f"baccarat_{user_id}_{time.time()}.png"
    try:
        game_img_gen.create_baccarat_image(player_cards, banker_cards, player_total, banker_total, baccarat_img_path)
        
        files = [discord.File(baccarat_img_path, filename="baccarat.png")]
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

    # Show difficulty selection
    class BalloonDifficultyView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=60)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="Easy", style=discord.ButtonStyle.success, emoji="🟢")
        async def easy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_balloon_game(interaction, "easy", self.wager_usd, self.user_id)

        @discord.ui.button(label="Medium", style=discord.ButtonStyle.primary, emoji="🟡")
        async def medium_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_balloon_game(interaction, "medium", self.wager_usd, self.user_id)

        @discord.ui.button(label="Hard", style=discord.ButtonStyle.danger, emoji="🔴")
        async def hard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return
            await start_balloon_game(interaction, "hard", self.wager_usd, self.user_id)

    embed = discord.Embed(title="🎈 Balloon - Choose Difficulty", color=0xff6600)
    embed.add_field(name="💰 Wager", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="🟢 Easy", value="Pop: 10-25x\nSafe pumping", inline=True)
    embed.add_field(name="🟡 Medium", value="Pop: 15-40x\nModerate risk", inline=True)
    embed.add_field(name="🔴 Hard", value="Pop: 20-60x\nHigh risk!", inline=True)
    embed.set_footer(text="Select your difficulty level!")

    view = BalloonDifficultyView(wager_usd, user_id)
    await interaction.response.send_message(embed=embed, view=view)
    return

async def start_balloon_game(interaction, difficulty, wager_usd, user_id):
    # Deduct wager
    balances[user_id]["balance"] -= wager_usd
    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    # Set difficulty parameters (Stake-style)
    if difficulty == "easy":
        pop_chance_per_pump = 0.01  # 1% chance per pump
        multiplier_increase = 0.08  # 8% increase per pump
    elif difficulty == "medium":
        pop_chance_per_pump = 0.03  # 3% chance per pump
        multiplier_increase = 0.15  # 15% increase per pump
    else:  # hard
        pop_chance_per_pump = 0.05  # 5% chance per pump
        multiplier_increase = 0.25  # 25% increase per pump

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

        @discord.ui.button(label="🎈 Pump", style=discord.ButtonStyle.primary)
        async def pump_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            self.pumps += 1
            self.current_multiplier = round(self.current_multiplier * (1 + self.multiplier_increase), 2)

            # Calculate pop chance based on pumps
            cumulative_pop_chance = self.pop_chance_per_pump * self.pumps
            if random.random() < cumulative_pop_chance:
                # Balloon popped!
                self.game_over = True
                self.clear_items()

                new_balance_usd = balances[self.user_id]["balance"]

                balloon_size = "🎈" * min(self.pumps, 10)

                embed = discord.Embed(title="💥 BALLOON POPPED! 💥", color=0xff0000)
                embed.add_field(name="🎈 Pumps", value=str(self.pumps), inline=True)
                embed.add_field(name="📈 Reached", value=f"{self.current_multiplier:.2f}x", inline=True)
                embed.add_field(name="💸 Lost", value=f"${self.wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
                embed.add_field(name="🎈 Balloon", value=balloon_size + " 💥", inline=False)

                # Create balloon popped image
                balloon_img_path = f"balloon_{self.user_id}_{time.time()}.png"
                game_img_gen.create_balloon_image(self.pumps, True, balloon_img_path)
                
                files = []
                if os.path.exists(balloon_img_path):
                    files.append(discord.File(balloon_img_path, filename="balloon.png"))
                    embed.set_image(url="attachment://balloon.png")

                await interaction.response.edit_message(embed=embed, view=self, attachments=files)
                
                # Clean up
                if os.path.exists(balloon_img_path):
                    try:
                        os.remove(balloon_img_path)
                    except:
                        pass
            else:
                balloon_size = "🎈" * min(self.pumps, 10)
                current_winnings = self.wager_usd * self.current_multiplier

                embed = discord.Embed(title="🎈 Balloon Pump", color=0x0099ff)
                embed.add_field(name="🎈 Pumps", value=str(self.pumps), inline=True)
                embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
                embed.add_field(name="💰 Current Win", value=f"${current_winnings:.2f} USD", inline=True)
                embed.add_field(name="🎈 Balloon", value=balloon_size, inline=False)
                embed.set_footer(text="Keep pumping or cash out before it pops!")

                # Create balloon image
                balloon_img_path = f"balloon_{self.user_id}_{time.time()}.png"
                game_img_gen.create_balloon_image(self.pumps, False, balloon_img_path)
                
                files = []
                if os.path.exists(balloon_img_path):
                    files.append(discord.File(balloon_img_path, filename="balloon.png"))
                    embed.set_image(url="attachment://balloon.png")

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

            self.game_over = True
            self.clear_items()

            winnings_usd = self.wager_usd * self.current_multiplier
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

            # Create final balloon image
            balloon_img_path = f"balloon_{self.user_id}_{time.time()}.png"
            game_img_gen.create_balloon_image(self.pumps, False, balloon_img_path)
            
            files = []
            if os.path.exists(balloon_img_path):
                files.append(discord.File(balloon_img_path, filename="balloon.png"))
                embed.set_image(url="attachment://balloon.png")

            await interaction.response.edit_message(embed=embed, view=self, attachments=files)
            
            # Clean up
            if os.path.exists(balloon_img_path):
                try:
                    os.remove(balloon_img_path)
                except:
                    pass

    embed = discord.Embed(title="🎈 Balloon Pump", color=0x0099ff)
    embed.add_field(name="💰 Wager", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="🎈 Pumps", value="0", inline=True)
    embed.add_field(name="📈 Multiplier", value="1.00x", inline=True)
    embed.set_footer(text="Pump the balloon to increase your multiplier!")

    view = BalloonView(wager_usd, user_id, pop_chance_per_pump, multiplier_increase)
    await interaction.response.send_message(embed=embed, view=view)

# CHICKEN CROSSING
@bot.tree.command(name="chicken", description="Help the chicken cross the road! (in USD)")
async def chicken(interaction: discord.Interaction, wager_amount: str):
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

    # Deduct wager
    balances[user_id]["balance"] -= wager_usd
    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    # Generate road (10 rows, 3 lanes each)
    road = []
    for row in range(10):
        safe_lane = random.randint(0, 2)
        road.append(safe_lane)

    class ChickenView(discord.ui.View):
        def __init__(self, wager_usd, user_id, road):
            super().__init__(timeout=180)
            self.wager_usd = wager_usd
            self.user_id = user_id
            self.road = road
            self.current_row = 0
            self.game_over = False
            self.current_multiplier = 1.0

        def get_multiplier(self, row):
            return round(1.0 + (row * 0.3), 2)

        @discord.ui.button(label="⬅️ Left", style=discord.ButtonStyle.secondary, custom_id="left")
        async def left_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.move(interaction, 0)

        @discord.ui.button(label="⬆️ Forward", style=discord.ButtonStyle.secondary, custom_id="forward")
        async def forward_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.move(interaction, 1)

        @discord.ui.button(label="➡️ Right", style=discord.ButtonStyle.secondary, custom_id="right")
        async def right_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self.move(interaction, 2)

        @discord.ui.button(label="💰 Cash Out", style=discord.ButtonStyle.green, custom_id="cashout")
        async def cashout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if self.current_row == 0:
                await interaction.response.send_message("You need to cross at least one row!", ephemeral=True)
                return

            self.game_over = True
            self.clear_items()

            winnings_usd = self.wager_usd * self.current_multiplier
            balances[self.user_id]["balance"] += winnings_usd
            save_balances(balances)
            new_balance_usd = balances[self.user_id]["balance"]

            embed = discord.Embed(title="💰 Chicken Cashed Out! 🐔", color=0x00ff00)
            embed.add_field(name="🛣️ Rows Crossed", value=f"{self.current_row}/10", inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
            embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

            await interaction.response.edit_message(embed=embed, view=self)

        async def move(self, interaction, lane):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            safe_lane = self.road[self.current_row]

            if lane == safe_lane:
                # Safe!
                self.current_row += 1
                self.current_multiplier = self.get_multiplier(self.current_row)

                if self.current_row >= 10:
                    # Made it across!
                    self.game_over = True
                    self.clear_items()

                    winnings_usd = self.wager_usd * self.current_multiplier
                    balances[self.user_id]["balance"] += winnings_usd
                    save_balances(balances)
                    new_balance_usd = balances[self.user_id]["balance"]

                    embed = discord.Embed(title="🐔 CHICKEN MADE IT! 🎉", color=0xffd700)
                    embed.add_field(name="🛣️ Rows Crossed", value="10/10 (COMPLETE!)", inline=True)
                    embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
                    embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
                    embed.add_field(name="💳New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
                    embed.set_footer(text="Congratulations!")

                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    # Continue
                    road_visual = ""
                    for i in range(3):
                        if i == safe_lane:
                            road_visual += "✅ "
                        else:
                            road_visual += "🚗 "

                    embed = discord.Embed(title="🐔 Chicken Crossing", color=0x00ff00)
                    embed.add_field(name="🛣️ Current Row", value=f"{self.current_row}/10", inline=True)
                    embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
                    embed.add_field(name="💰 Current Win", value=f"${self.wager_usd * self.current_multiplier:.2f} USD", inline=True)
                    embed.add_field(name="🛣️ Next Row", value=road_visual, inline=False)
                    embed.set_footer(text="Choose a lane: Left, Forward, or Right")

                    await interaction.response.edit_message(embed=embed, view=self)
            else:
                # Hit by car!
                self.game_over = True
                self.clear_items()

                new_balance_usd = balances[self.user_id]["balance"]

                embed = discord.Embed(title="🚗 CHICKEN HIT! 💥", color=0xff0000)
                embed.add_field(name="🛣️ Rows Crossed", value=f"{self.current_row}/10", inline=True)
                embed.add_field(name="📈 Reached", value=f"{self.current_multiplier:.2f}x", inline=True)
                embed.add_field(name="💸 Lost", value=f"${self.wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

                await interaction.response.edit_message(embed=embed, view=self)

    # Initial display
    safe_lane = road[0]
    road_visual = ""
    for i in range(3):
        if i == safe_lane:
            road_visual += "✅ "
        else:
            road_visual += "🚗 "

    embed = discord.Embed(title="🐔 Chicken Crossing", color=0x0099ff)
    embed.add_field(name="💰 Wager", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="🛣️ Current Row", value="0/10", inline=True)
    embed.add_field(name="📈 Multiplier", value="1.00x", inline=True)
    embed.add_field(name="🛣️ First Row", value=road_visual, inline=False)
    embed.set_footer(text="Choose a lane to help the chicken cross!")

    view = ChickenView(wager_usd, user_id, road)
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
                embed.add_field(name="🤜 Rock Paper Scissors", value="`/rps [amount] [choice]` - Classic RPS (78% RTP)", inline=False)
                embed.add_field(name="🎰 Slots", value="`/slots [amount]` - Spin the reels for jackpots!", inline=False)
                embed.add_field(name="🃏 Blackjack", value="`/blackjack [amount]` - Beat the dealer with strategy!", inline=False)
                embed.add_field(name="🎴 Baccarat", value="`/baccarat [amount] [player/banker/tie]` - Classic card game", inline=False)
                embed.add_field(name="💎 Mines", value="`/mines [amount] [mine_count]` - Find diamonds, avoid mines!", inline=False)
                embed.add_field(name="🏗️ Towers", value="`/towers [amount]` - Climb 8 levels choosing paths!", inline=False)
                embed.add_field(name="🌌 Limbo", value="`/limbo [amount] [multiplier]` - Cosmic multiplier game!", inline=False)
                embed.add_field(name="🏀 Plinko", value="`/plinko [amount] [rows] [difficulty]` - Drop a ball down!", inline=False)
                embed.add_field(name="🎈 Balloon", value="`/balloon [amount]` - Pump without popping!", inline=False)
                embed.add_field(name="🐔 Chicken", value="`/chicken [amount]` - Help chicken cross the road!", inline=False)
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
                embed.add_field(name="💰 House Deposit", value="`/housedeposit` - Get house deposit address", inline=False)
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
