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

# Load environment variables from .env file
load_dotenv()

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
    total_deposited_usd = user_data["deposited"]
    total_withdrawn_usd = user_data["withdrawn"]
    total_wagered_usd = user_data["wagered"]

    # Calculate profit/loss in USD
    profit_loss_usd = current_balance_usd + total_withdrawn_usd - total_deposited_usd
    profit_loss_emoji = "📈" if profit_loss_usd >= 0 else "📉"

    embed = discord.Embed(
        title=f"💰 {user.display_name}'s Account Statistics",
        color=0x00ff00 if profit_loss_usd >= 0 else 0xff0000
    )

    embed.add_field(name="💳 Current Balance", value=f"${format_number(current_balance_usd)} USD", inline=True)
    embed.add_field(name="⬇️ Total Deposited", value=f"${format_number(total_deposited_usd)} USD", inline=True)
    embed.add_field(name="⬆️ Total Withdrawn", value=f"${format_number(total_withdrawn_usd)} USD", inline=True)
    embed.add_field(name="🎲 Total Wagered", value=f"${format_number(total_wagered_usd)} USD", inline=True)
    embed.add_field(name=f"{profit_loss_emoji} Profit/Loss", value=f"${format_number(profit_loss_usd)} USD", inline=True)

    # Show affiliation info
    if user_id in affiliation_data:
        affiliated_to = affiliation_data[user_id]["affiliated_to"]
        total_earned = affiliation_data[user_id]["total_earned"]

        if affiliated_to:
            try:
                affiliate_user = bot.get_user(int(affiliated_to))
                affiliate_name = affiliate_user.display_name if affiliate_user else f"User #{affiliated_to[-4:]}"
                embed.add_field(name="🤝 Affiliated To", value=affiliate_name, inline=True)
            except:
                embed.add_field(name="🤝 Affiliated To", value="Unknown User", inline=True)
        else:
            embed.add_field(name="🤝 Affiliated To", value="None", inline=True)

        embed.add_field(name="💰 Affiliate Earnings", value=f"${format_number(total_earned)} USD", inline=True)
    else:
        embed.add_field(name="🤝 Affiliated To", value="None", inline=True)
        embed.add_field(name="💰 Affiliate Earnings", value="$0.00 USD", inline=True)

    embed.set_footer(text="Use gambling commands to start playing!")

    await interaction.response.send_message(embed=embed)

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
async def coinflip(interaction: discord.Interaction, choice: str, wager_amount: str):
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

    if choice.lower() not in ["heads", "tails"]:
        await interaction.response.send_message("❌ Please choose either 'heads' or 'tails'!", ephemeral=True)
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

    coin_flip = random.choice(["heads", "tails"])
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

    embed.add_field(name="🎯 Coinflip Visual", value=visual_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

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
        embed.add_field(name="🎯 Coinflip Visual", value=visual_text, inline=False)
        embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

        # Add play again buttons
        play_again_view = CoinflipPlayAgainView(wager_usd, user_id)
        await interaction.edit_original_response(embed=embed, view=play_again_view)

    # Add play again buttons to current result
    play_again_view = CoinflipPlayAgainView(wager_usd, user_id)
    await interaction.edit_original_response(embed=embed, view=play_again_view)

# DICE
@bot.tree.command(name="dice", description="Roll a dice and choose over/under 3 to win (in USD)")
async def dice(interaction: discord.Interaction, wager_amount: str, choice: str):
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

    if choice.lower() not in ["over", "under"]:
        await interaction.response.send_message("❌ Please choose either 'over' or 'under'!", ephemeral=True)
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

    roll = random.randint(1, 6)
    user_choice = choice.lower()

    # Determine win condition based on choice
    if user_choice == "over":
        won = roll > 3
        win_condition = ">3"
    else:  # under
        won = roll < 4  # rolls 1, 2, or 3
        win_condition = "<4"

    if won:
        # 75% RTP - pay out 0.75x for wins (25% house edge)
        winnings_usd = wager_usd * 0.75
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0x00ff00
        title = "🎲 Dice Roll - YOU WON! 🎉"
        result_text = f"You rolled a **{roll}** and chose **{user_choice}** ({win_condition})!"
    else:
        balances[user_id]["balance"] -= wager_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0xff0000
        title = "🎲 Dice Roll - You Lost 😔"
        result_text = f"You rolled a **{roll}** and chose **{user_choice}** ({win_condition})."

    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    # Create dice visual
    dice_visuals = {
        1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"
    }

    # Start with rolling animation
    embed = discord.Embed(title="🎲 Dice Roll - Rolling...", color=0xffaa00)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="🎯 Your Bet", value=f"{user_choice.title()} ({win_condition})", inline=True)
    embed.add_field(name="⏳ Status", value="🎲 Rolling dice...", inline=False)

    await interaction.response.send_message(embed=embed)

    # Animation frames
    roll_frames = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]

    for i, frame in enumerate(roll_frames):
        embed.set_field_at(2, name="⏳ Status", value=f"🎲 {frame} Rolling...", inline=False)
        await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(0.3)

    # Show final result
    embed = discord.Embed(title=title, color=color)

    # Visual section
    visual_text = f"""
**Your Bet:** {user_choice.title()} (roll {win_condition})
**Dice Result:** {dice_visuals[roll]} **{roll}**

{dice_visuals[roll]} ← **You rolled this number!**
    """

    embed.add_field(name="🎲 Dice Visual", value=visual_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

    # Create play again view
    class DicePlayAgainView(discord.ui.View):
        def __init__(self, wager_usd, user_id):
            super().__init__(timeout=300)
            self.wager_usd = wager_usd
            self.user_id = user_id

        @discord.ui.button(label="🎲 Play Again - Over", style=discord.ButtonStyle.primary)
        async def play_again_over(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            await start_new_dice_game(interaction, "over", self.wager_usd, self.user_id)

        @discord.ui.button(label="🎲 Play Again - Under", style=discord.ButtonStyle.primary)
        async def play_again_under(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ You don't have enough balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to play again.", ephemeral=True)
                return

            await start_new_dice_game(interaction, "under", self.wager_usd, self.user_id)

    async def start_new_dice_game(interaction, choice, wager_usd, user_id):
        roll = random.randint(1, 6)
        user_choice = choice.lower()

        if user_choice == "over":
            won = roll > 3
            win_condition = ">3"
        else:  # under
            won = roll < 4
            win_condition = "<4"

        if won:
            winnings_usd = wager_usd * 0.75
            balances[user_id]["balance"] += winnings_usd
            new_balance_usd = balances[user_id]["balance"]
            color = 0x00ff00
            title = "🎲 Dice Roll - YOU WON! 🎉"
            result_text = f"You rolled a **{roll}** and chose **{user_choice}** ({win_condition})!"
        else:
            balances[user_id]["balance"] -= wager_usd
            new_balance_usd = balances[user_id]["balance"]
            color = 0xff0000
            title = "🎲 Dice Roll - You Lost 😔"
            result_text = f"You rolled a **{roll}** and chose **{user_choice}** ({win_condition})."

        balances[user_id]["wagered"] += wager_usd
        add_rakeback(user_id, wager_usd)
        save_balances(balances)

        dice_visuals = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

        embed = discord.Embed(title=title, color=color)
        visual_text = f"""
**Your Bet:** {user_choice.title()} (roll {win_condition})
**Dice Result:** {dice_visuals[roll]} **{roll}**

{dice_visuals[roll]} ← **You rolled this number!**
        """

        embed.add_field(name="🎲 Dice Visual", value=visual_text, inline=False)
        embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

        play_again_view = DicePlayAgainView(wager_usd, user_id)
        await interaction.response.edit_message(embed=embed, view=play_again_view)

    play_again_view = DicePlayAgainView(wager_usd, user_id)
    await interaction.edit_original_response(embed=embed, view=play_again_view)

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

        play_again_view = RPSPlayAgainView(wager_usd, user_id)
        await interaction.response.edit_message(embed=embed, view=play_again_view)

    play_again_view = RPSPlayAgainView(wager_usd, user_id)
    await interaction.response.send_message(embed=embed, view=play_again_view)

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

    # Final result embed
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${format_number(wager_usd)} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)
    embed.set_footer(text="Jackpot: 2x | Two Match: 1.0x")

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
        await interaction.response.edit_message(embed=embed, view=play_again_view)

    play_again_view = SlotsPlayAgainView(wager_usd, user_id)
    await interaction.edit_original_response(embed=embed, view=play_again_view)

# Import card generator
from card_generator import CardImageGenerator

# Global card generator
card_generator = CardImageGenerator()

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
            embed.set_footer(text="Hit: take another card | Stand: keep hand | Double Down: double bet + 1 card")

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

    # Deduct the initial wager when starting the game
    balances[user_id]["balance"] -= wager_usd
    save_balances(balances)

    # Interactive blackjack game with splitting and visual cards
    class BlackjackView(discord.ui.View):
        def __init__(self, player_hand, dealer_hand, deck, wager_usd, user_id):
            super().__init__(timeout=180)
            self.player_hands = [player_hand]  # Support multiple hands for splitting
            self.dealer_hand = dealer_hand
            self.deck = deck
            self.wager_usd = wager_usd
            self.user_id = user_id
            self.game_over = False
            self.can_double_down = True
            self.current_hand_index = 0
            self.hands_completed = [False]  # Track which hands are done
            self.split_count = 0
            self.total_wager = wager_usd
            self.card_generator = CardImageGenerator() # Use the global card generator instance
            self.can_split = self.check_can_split()

        def card_value(self, card):
            rank = card[0]
            if rank in ['J', 'Q', 'K']:
                return 10
            elif rank == 'A':
                return 11
            else:
                return int(rank)

        def hand_value(self, hand):
            value = sum(self.card_value(card) for card in hand)
            aces = sum(1 for card in hand if card[0] == 'A')
            while value > 21 and aces:
                value -= 10
                aces -= 1
            return value

        def format_hand(self, hand, hide_first=False):
            if hide_first:
                return f"🂠 {hand[1][0]}{hand[1][1]}"
            return " ".join(f"{card[0]}{card[1]}" for card in hand)

        def check_can_split(self):
            if len(self.player_hands[0]) == 2 and self.split_count < 3:
                card1, card2 = self.player_hands[0]
                return self.card_value(card1) == self.card_value(card2)
            return False

        def get_current_hand(self):
            return self.player_hands[self.current_hand_index]

        def format_all_hands(self):
            result = ""
            for i, hand in enumerate(self.player_hands):
                indicator = "👉 " if i == self.current_hand_index and not self.hands_completed[i] else "   "
                status = " ✅" if self.hands_completed[i] else ""
                result += f"{indicator}Hand {i+1}: {self.format_hand(hand)}{status}\n"
            return result.strip()

        @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, emoji="🃏")
        async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if self.hands_completed[self.current_hand_index]:
                await interaction.response.send_message("This hand is already completed!", ephemeral=True)
                return

            current_hand = self.get_current_hand()
            current_hand.append(self.deck.pop())
            player_value = self.hand_value(current_hand)

            self.can_double_down = False
            self.can_split = False
            self.update_buttons()

            if player_value > 21:
                # Current hand busts
                self.hands_completed[self.current_hand_index] = True

                if all(self.hands_completed):
                    # All hands are done
                    await self.finish_game(interaction)
                else:
                    # Move to next hand
                    self.move_to_next_hand()
                    await self.update_display(interaction, "🃏 Blackjack - Next Hand")
            else:
                await self.update_display(interaction, "🃏 Blackjack - Your Turn")

        @discord.ui.button(label="Stand", style=discord.ButtonStyle.red, emoji="✋")
        async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if self.hands_completed[self.current_hand_index]:
                await interaction.response.send_message("This hand is already completed!", ephemeral=True)
                return

            self.hands_completed[self.current_hand_index] = True

            if all(self.hands_completed):
                # All hands are done, dealer plays
                await self.dealer_play(interaction)
            else:
                # Move to next hand
                self.move_to_next_hand()
                await self.update_display(interaction, "🃏 Blackjack - Next Hand")

        @discord.ui.button(label="Double Down", style=discord.ButtonStyle.blurple, emoji="💸")
        async def double_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if not self.can_double_down or self.hands_completed[self.current_hand_index]:
                await interaction.response.send_message("You can only double down on your first turn!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ Insufficient balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to double down.", ephemeral=True)
                return

            balances[self.user_id]["balance"] -= self.wager_usd
            self.total_wager += self.wager_usd
            current_hand = self.get_current_hand()
            current_hand.append(self.deck.pop())
            player_value = self.hand_value(current_hand)

            self.can_double_down = False
            self.can_split = False
            self.hands_completed[self.current_hand_index] = True

            if all(self.hands_completed):
                await self.dealer_play(interaction)
            else:
                self.move_to_next_hand()
                await self.update_display(interaction, "🃏 Blackjack - Next Hand (Doubled)")

        @discord.ui.button(label="Split", style=discord.ButtonStyle.secondary, emoji="✂️")
        async def split_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if not self.can_split:
                await interaction.response.send_message("You cannot split this hand!", ephemeral=True)
                return

            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ Insufficient balance! You have ${format_number(current_balance_usd)} USD but need ${format_number(self.wager_usd)} USD to split.", ephemeral=True)
                return

            # Deduct additional wager for split
            balances[self.user_id]["balance"] -= self.wager_usd
            self.total_wager += self.wager_usd

            # Split the hand
            current_hand = self.get_current_hand()
            card1, card2 = current_hand[0], current_hand[1]

            # Create two new hands
            self.player_hands[self.current_hand_index] = [card1, self.deck.pop()]
            self.player_hands.append([card2, self.deck.pop()])
            self.hands_completed.append(False)

            self.split_count += 1
            self.can_split = False
            self.can_double_down = True
            self.update_buttons()

            await self.update_display(interaction, "🃏 Blackjack - Hand Split!")

        def update_buttons(self):
            """Update button states based on current game state"""
            for item in self.children:
                if hasattr(item, 'label'):
                    if item.label == "Double Down":
                        item.disabled = not self.can_double_down
                    elif item.label == "Split":
                        item.disabled = not self.can_split
                    elif item.label == "Hit" or item.label == "Stand":
                        item.disabled = self.game_over or (self.current_hand_index < len(self.hands_completed) and self.hands_completed[self.current_hand_index])

        def move_to_next_hand(self):
            for i in range(self.current_hand_index + 1, len(self.player_hands)):
                if not self.hands_completed[i]:
                    self.current_hand_index = i
                    self.can_double_down = len(self.player_hands[i]) == 2
                    self.can_split = self.check_can_split() if i == 0 else False # Split only allowed on first hand
                    self.update_buttons()
                    return
            # If no more hands, mark game for dealer
            self.current_hand_index = len(self.player_hands)

        async def create_game_image(self, show_dealer_cards=False):
            """Create comprehensive blackjack game image showing all hands"""
            try:
                game_img_path = f"temp_blackjack_{self.user_id}_{time.time()}.png"

                # Use the enhanced blackjack image generator
                success = self.card_generator.save_blackjack_game_image(
                    self.player_hands,
                    self.dealer_hand,
                    game_img_path,
                    self.current_hand_index,
                    hide_dealer_first=not show_dealer_cards
                )

                return game_img_path if success else None, None
            except Exception as e:
                print(f"Error creating game images: {e}")
                return None, None

        async def update_display(self, interaction, title):
            # Create comprehensive game image
            game_img, _ = await self.create_game_image(show_dealer_cards=False)

            embed = discord.Embed(title=title, color=0x0099ff)

            # Add hand information
            current_hand = self.get_current_hand() if self.current_hand_index < len(self.player_hands) else self.player_hands[0] # Handle case where all hands are completed
            player_value = self.hand_value(current_hand)

            if len(self.player_hands) == 1:
                embed.add_field(name="🃏 Your Hand", value=f"{self.format_hand(current_hand)} = **{player_value}**", inline=True)
            else:
                embed.add_field(name="🃏 Current Hand", value=f"Hand {self.current_hand_index + 1}: {self.format_hand(current_hand)} = **{player_value}**", inline=True)

            embed.add_field(name="🤖 Dealer Hand", value=f"{self.format_hand(self.dealer_hand, hide_first=True)} = **?**", inline=True)
            embed.add_field(name="💰 Total Wager", value=f"${format_number(self.total_wager)} USD", inline=True)

            if len(self.player_hands) > 1:
                hands_status = []
                for i, hand in enumerate(self.player_hands):
                    status = "🔥 ACTIVE" if i == self.current_hand_index and not self.hands_completed[i] else "✅ DONE" if self.hands_completed[i] else "⏳ WAITING"
                    hands_status.append(f"Hand {i+1}: {status}")
                embed.add_field(name="📊 All Hands Status", value="\n".join(hands_status), inline=False)

            embed.set_footer(text="Hit: take card | Stand: keep hand | Double Down: double bet + 1 card | Split: split pairs")

            # Attach comprehensive game image
            files = []
            if game_img and os.path.exists(game_img):
                files.append(discord.File(game_img, filename="blackjack_game.png"))
                embed.set_image(url="attachment://blackjack_game.png")

            try:
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, view=self, attachments=files)
                else:
                    await interaction.response.edit_message(embed=embed, view=self, attachments=files)

                # Clean up image files
                if game_img and os.path.exists(game_img):
                    try:
                        os.remove(game_img)
                    except:
                        pass

            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(embed=embed, view=self, files=files)
                except:
                    pass

        async def dealer_play(self, interaction):
            self.clear_items()

            # Initial dealer reveal with image
            dealer_img, _ = await self.create_game_image(show_dealer_cards=True)

            embed = discord.Embed(title="🃏 Blackjack - Dealer's Turn", color=0xffaa00)
            embed.add_field(name="🃏 Your Final Hands", value=self.format_all_hands(), inline=False)
            embed.add_field(name="🤖 Dealer Reveals...", value=f"{self.format_hand(self.dealer_hand)} = {self.hand_value(self.dealer_hand)}", inline=True)
            embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)

            files = []
            if dealer_img and os.path.exists(dealer_img):
                files.append(discord.File(dealer_img, filename="dealer_reveal.png"))
                embed.set_image(url="attachment://dealer_reveal.png")

            try:
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, view=self, attachments=files)
                else:
                    await interaction.response.edit_message(embed=embed, view=self, attachments=files)

                if dealer_img and os.path.exists(dealer_img):
                    try:
                        os.remove(dealer_img)
                    except:
                        pass
            except discord.errors.NotFound:
                await interaction.followup.send(embed=embed, view=self, files=files)
                return

            await asyncio.sleep(2)

            while self.hand_value(self.dealer_hand) < 17:
                self.dealer_hand.append(self.deck.pop())
                current_dealer_value = self.hand_value(self.dealer_hand)

                # Create updated image showing dealer hitting
                dealer_hit_img, _ = await self.create_game_image(show_dealer_cards=True)

                embed = discord.Embed(title="🃏 Blackjack - Dealer Hits", color=0xffaa00)
                embed.add_field(name="🃏 Your Final Hands", value=self.format_all_hands(), inline=False)
                embed.add_field(name="🤖 Dealer Hand", value=f"{self.format_hand(self.dealer_hand)} = {current_dealer_value}", inline=True)
                embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)

                files = []
                if dealer_hit_img and os.path.exists(dealer_hit_img):
                    files.append(discord.File(dealer_hit_img, filename="dealer_hit.png"))
                    embed.set_image(url="attachment://dealer_hit.png")

                try:
                    await interaction.edit_original_response(embed=embed, view=self, attachments=files)

                    if dealer_hit_img and os.path.exists(dealer_hit_img):
                        try:
                            os.remove(dealer_hit_img)
                        except:
                            pass
                except discord.errors.NotFound:
                    # Interaction expired during dealer play
                    break
                await asyncio.sleep(1.5)

            await self.finish_game(interaction)

        async def finish_game(self, interaction):
            dealer_value = self.hand_value(self.dealer_hand)
            results = []
            total_winnings = 0

            for i, hand in enumerate(self.player_hands):
                player_value = self.hand_value(hand)
                # Double down detection: if hand has more than 2 cards and the wager is double the initial
                hand_wager = self.wager_usd
                if len(hand) > 2 and self.total_wager > self.wager_usd and player_value <= 21:
                    if self.wager_usd * 2 == self.total_wager: # A bit crude, but checks if total wager implies double down
                         hand_wager = self.wager_usd * 2
                    elif self.wager_usd * 3 == self.total_wager and len(self.player_hands) == 2: # Handles split + double down case
                         hand_wager = self.wager_usd * 3
                    # Note: This logic might need refinement for more complex split/double down scenarios


                if player_value > 21:
                    results.append(f"Hand {i+1}: **BUST** ({player_value}) - Lost ${hand_wager:.2f}")
                elif dealer_value > 21:
                    winnings = hand_wager * 2  # Return wager + 1x win (1:1 payout)
                    total_winnings += winnings
                    results.append(f"Hand {i+1}: **WON** ({player_value} vs {dealer_value}) - +${winnings:.2f}")
                elif player_value > dealer_value:
                    winnings = hand_wager * 2  # Return wager + 1x win (1:1 payout)
                    total_winnings += winnings
                    results.append(f"Hand {i+1}: **WON** ({player_value} vs {dealer_value}) - +${winnings:.2f}")
                elif dealer_value > player_value:
                    results.append(f"Hand {i+1}: **LOST** ({player_value} vs {dealer_value}) - Lost ${hand_wager:.2f}")
                else:
                    # Push - return original wager
                    total_winnings += hand_wager
                    results.append(f"Hand {i+1}: **PUSH** ({player_value} vs {dealer_value}) - Returned ${hand_wager:.2f}")

            balances[self.user_id]["balance"] += total_winnings
            balances[self.user_id]["wagered"] += self.total_wager
            add_rakeback(self.user_id, self.total_wager)
            save_balances(balances)

            new_balance_usd = balances[self.user_id]["balance"]
            net_result = total_winnings - self.total_wager

            color = 0x00ff00 if net_result > 0 else 0xff0000 if net_result < 0 else 0xffff00
            title_emoji = "🎉" if net_result > 0 else "😔" if net_result < 0 else "🤝"
            title = f"🃏 Blackjack - Game Complete! {title_emoji}"

            # Create final comprehensive game image showing all hands revealed
            final_img, _ = await self.create_game_image(show_dealer_cards=True)

            embed = discord.Embed(title=title, color=color)

            # Show final hands with values
            if len(self.player_hands) == 1:
                current_hand = self.player_hands[0]
                player_value = self.hand_value(current_hand)
                embed.add_field(name="🃏 Your Hand", value=f"{self.format_hand(current_hand)} = **{player_value}**", inline=True)
            else:
                hands_summary = []
                for i, hand in enumerate(self.player_hands):
                    hand_val = self.hand_value(hand)
                    hands_summary.append(f"Hand {i+1}: {self.format_hand(hand)} = **{hand_val}**")
                embed.add_field(name="🃏 Your Hands", value="\n".join(hands_summary), inline=False)

            embed.add_field(name="🤖 Dealer Hand", value=f"{self.format_hand(self.dealer_hand)} = **{dealer_value}**", inline=True)

            # Show detailed results for each hand
            if len(results) > 1:
                embed.add_field(name="📊 Individual Results", value="\n".join(results), inline=False)

            # Add game result
            if net_result > 0:
                result_text = f"🎉 **YOU WON!** +${net_result:.2f}"
            elif net_result < 0:
                result_text = f"😔 **YOU LOST** {net_result:.2f}"
            else:
                result_text = f"🤝 **PUSH** - No money lost or gained"

            embed.add_field(name="🎯 Final Result", value=result_text, inline=False)
            embed.add_field(name="💰 Total Wagered", value=f"${format_number(self.total_wager)} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${format_number(new_balance_usd)} USD", inline=True)

            # Attach final comprehensive game image
            files = []
            if final_img and os.path.exists(final_img):
                files.append(discord.File(final_img, filename="final_blackjack.png"))
                embed.set_image(url="attachment://final_blackjack.png")

            self.game_over = True

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
                embed.set_footer(text="Hit: take another card | Stand: keep hand | Double Down: double bet + 1 card")

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

            play_again_view = BlackjackPlayAgainView(self.wager_usd, self.user_id)

            try:
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, view=play_again_view, attachments=files)
                else:
                    await interaction.response.edit_message(embed=embed, view=play_again_view, attachments=files)

                # Clean up image file
                if final_img and os.path.exists(final_img):
                    try:
                        os.remove(final_img)
                    except:
                        pass

            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(embed=embed, view=play_again_view, files=files)
                except:
                    pass

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
async def towers(interaction: discord.Interaction, wager_amount: str, difficulty: int = 3):
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

    if difficulty < 2 or difficulty > 4:
        await interaction.response.send_message("❌ Difficulty must be between 2-4!", ephemeral=True)
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

    # Generate tower structure - 8 levels, each with 'difficulty' number of paths
    tower_structure = []
    for level in range(8):
        correct_path = random.randint(0, difficulty - 1)
        tower_structure.append(correct_path)

    def get_tower_multiplier(level, difficulty):
        base_multiplier = 1.0
        level_bonus = level * (0.10 + (difficulty - 2) * 0.02)
        return round(base_multiplier + level_bonus, 2)

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
                # Deduct the wager when starting the game
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
        embed.add_field(name="💰 Bet", value=f"${format_number(wager_usd)} USD", inline=True)
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

# HELP
@bot.tree.command(name="help", description="View all available game modes and commands")
async def help_command(interaction: discord.Interaction):
    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎮 VaultBet - All Commands & Games",
        description="Welcome to VaultBet! Here are all the available commands:",
        color=0x00ff00
    )

    # Game Commands Section
    games_text = """
🪙 `/coinflip [heads/tails] [amount]` - Call heads or tails (80% RTP)
🎲 `/dice [amount] [over/under]` - Roll dice, choose over/under 3 (75% RTP)
🤜 `/rps [choice] [amount]` - Rock Paper Scissors (78% RTP)
🎰 `/slots [amount]` - Spin the reels for jackpots!
🃏 `/blackjack [amount]` - Beat the dealer with strategy!
💎 `/mines [amount] [mine_count]` - Find diamonds, avoid mines!
🏗️ `/towers [amount] [difficulty]` - Climb 8 levels choosing paths!
🌌 `/limbo [amount] [target_multiplier]` - Choose your cosmic multiplier!
🏀 `/plinko [amount] [rows] [difficulty]` - Drop a ball down the Plinko board!
    """

    embed.add_field(name="🎯 Game Commands", value=games_text, inline=False)

    # Account Commands Section
    account_text = """
💰 `/balance` - Check your account stats and balance
💸 `/tip [user] [amount]` - Send money to another player
🎁 `/claimrakeback` - Claim 0.5% of your total wagered
🤝 `/affiliate [user]` - Affiliate to a player (they get 0.5% of your wagers)
📤 `/withdraw [amount] [address]` - Request withdrawal (direct LTC payout)
🏆 `/leaderboard [category]` - View top players
🎫 `/redeem [code]` - Redeem a promo code for rewards
    """

    embed.add_field(name="💳 Account Commands", value=account_text, inline=False)

    # Utility Commands Section
    utility_text = """
🆘 `/help` - Show this help message
🧪 `/test` - Test if the bot is working
    """

    embed.add_field(name="🛠️ Utility Commands", value=utility_text, inline=False)

    # Admin Commands Section (only show to admins)
    if is_admin(interaction.user.id):
        admin_text = """
💳 `/addbalance [user] [amount]` - Add balance to user account
💸 `/removebalance [user] [amount]` - Remove balance from user account
🔄 `/resetstats [user]` - Reset user's complete account
    """
        embed.add_field(name="👑 Admin Commands", value=admin_text, inline=False)

        house_admin_text = """
🏦 `/housebalance` - Check house wallet balance and stats
📤 `/housewithdraw [amount_ltc] [address]` - Withdraw LTC from house wallet
💰 `/housedeposit` - Get house wallet deposit address
        """
        embed.add_field(name="🏛️ House Wallet Commands", value=house_admin_text, inline=False)

    # Additional Info
    embed.add_field(name="💡 Important Info", value="• All amounts are in USD\n• Minimum wager: $0.10\n• Rakeback rate: 0.5%\n• Commands have 1 second cooldown\n• Chat rewards: $0.10 per 100 messages", inline=False)

    embed.set_footer(text="🎲 Good luck and gamble responsibly!")

    await interaction.response.send_message(embed=embed)

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
