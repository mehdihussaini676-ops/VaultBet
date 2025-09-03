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
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_ID", "").split(",") if id.strip()]
BLOCKCYPHER_API_KEY = os.getenv("BLOCKCYPHER_API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

# Debug: Print if keys are loaded
print(f"Environment check:")
print(f"- Discord token: {'✅' if TOKEN else '❌'}")
print(f"- BlockCypher key: {'✅' if BLOCKCYPHER_API_KEY else '❌'}")
print(f"- Webhook secret: {'✅' if WEBHOOK_SECRET else '❌'}")

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
                                    embed.set_footer(text="Your deposit has been automatically credited")

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

    embed.add_field(name="💳 Current Balance", value=f"${current_balance_usd:.2f} USD", inline=True)
    embed.add_field(name="⬇️ Total Deposited", value=f"${total_deposited_usd:.2f} USD", inline=True)
    embed.add_field(name="⬆️ Total Withdrawn", value=f"${total_withdrawn_usd:.2f} USD", inline=True)
    embed.add_field(name="🎲 Total Wagered", value=f"${total_wagered_usd:.2f} USD", inline=True)
    embed.add_field(name=f"{profit_loss_emoji} Profit/Loss", value=f"${profit_loss_usd:.2f} USD", inline=True)

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

        embed.add_field(name="💰 Affiliate Earnings", value=f"${total_earned:.2f} USD", inline=True)
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
    embed.add_field(name="💸 Rakeback Claimed", value=f"${rakeback_earned_usd:.2f} USD", inline=True)
    embed.add_field(name="🎲 Total Wagered", value=f"${total_wagered_usd:.2f} USD", inline=True)
    embed.add_field(name="📊 Rakeback Rate", value="0.5%", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
    embed.set_footer(text="Keep gambling to earn more rakeback!")

    await interaction.response.send_message(embed=embed)

# TIP PLAYER
@bot.tree.command(name="tip", description="Tip another player some of your balance (in USD)")
async def tip(interaction: discord.Interaction, member: discord.Member, amount_usd: float):
    user_id = str(interaction.user.id)
    target_id = str(member.id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
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

    if amount_usd < 0.01:
        await interaction.response.send_message("❌ Minimum tip amount is $0.01 USD!", ephemeral=True)
        return

    if amount_usd > 1000:
        await interaction.response.send_message("❌ Maximum tip amount is $1000 USD!", ephemeral=True)
        return

    init_user(user_id)
    init_user(target_id)

    if balances[user_id]["balance"] < amount_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to tip ${amount_usd:.2f} USD.")
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
    embed.add_field(name="💰 Amount", value=f"${amount_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 Your New Balance", value=f"${sender_new_balance_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 Their New Balance", value=f"${receiver_new_balance_usd:.2f} USD", inline=True)
    embed.set_footer(text="Spread the love!")

    await interaction.response.send_message(embed=embed)

# ADMIN: ADD BALANCE
@bot.tree.command(name="addbalance", description="Admin command to add balance to a user (in USD)")
async def addbalance(interaction: discord.Interaction, member: discord.Member, amount_usd: float):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
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
    embed.add_field(name="💵 Amount Added", value=f"${amount_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${balances[user_id]['balance']:.2f} USD", inline=True)

    await interaction.response.send_message(embed=embed)

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
async def coinflip(interaction: discord.Interaction, choice: str, wager_usd: float):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if choice.lower() not in ["heads", "tails"]:
        await interaction.response.send_message("❌ Please choose either 'heads' or 'tails'!", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.01:
        await interaction.response.send_message("❌ Minimum wager is $0.01 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    # Start with animation
    embed = discord.Embed(title="🪙 Coinflip - Flipping...", color=0xffaa00)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="🎯 Your Call", value=choice.title(), inline=True)
    embed.add_field(name="⏳ Status", value="🪙 Coin is spinning...", inline=False)

    await interaction.response.send_message(embed=embed)

    # Improved animation frames with spinning effect
    frames = [
        "🪙 ↗️ FLIP",
        "🔄 ↘️ SPIN", 
        "🪙 ↙️ FLIP",
        "🔄 ↖️ SPIN",
        "🪙 ↗️ FLIP",
        "🔄 ↘️ SPIN",
        "🪙 ↙️ FLIP",
        "🔄 ↖️ SPIN",
        "🪙 ⏹️ LANDING...",
        "⭐ 🪙 ⭐"
    ]

    for i, frame in enumerate(frames):
        embed.set_field_at(2, name="⏳ Status", value=f"{frame}", inline=False)
        await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(0.4)

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
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

    await interaction.edit_original_response(embed=embed)

# DICE
@bot.tree.command(name="dice", description="Roll a dice and choose over/under 3 to win (in USD)")
async def dice(interaction: discord.Interaction, wager_usd: float, choice: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if choice.lower() not in ["over", "under"]:
        await interaction.response.send_message("❌ Please choose either 'over' or 'under'!", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.01:
        await interaction.response.send_message("❌ Minimum wager is $0.01 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
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
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
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
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

    await interaction.edit_original_response(embed=embed)

# ROCK PAPER SCISSORS
@bot.tree.command(name="rps", description="Play Rock Paper Scissors (in USD)")
async def rps(interaction: discord.Interaction, choice: str, wager_usd: float):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if choice.lower() not in ["rock", "paper", "scissors"]:
        await interaction.response.send_message("❌ Please choose either 'rock', 'paper', or 'scissors'!", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.01:
        await interaction.response.send_message("❌ Minimum wager is $0.01 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
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
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

    await interaction.response.send_message(embed=embed)

# SLOTS
@bot.tree.command(name="slots", description="Spin the slot machine! (in USD)")
async def slots(interaction: discord.Interaction, wager_usd: float):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.01:
        await interaction.response.send_message("❌ Minimum wager is $0.01 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
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
        result_text = f"**{result_display}**\n\nAll three match! You won **${winnings_usd:.2f} USD** (2x multiplier)!"
    elif len(set(result)) == 2:
        # Two symbols match (reduced to 1.0x for higher house edge)
        multiplier = 1.0
        winnings_usd = wager_usd * multiplier
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0x00ff00
        title = "🎰 Nice Win! 🎉"
        result_text = f"**{result_display}**\n\nTwo symbols match! You won **${winnings_usd:.2f} USD** (1.0x multiplier)!"
    else:
        # No match - player loses
        balances[user_id]["balance"] -= wager_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0xff0000
        title = "🎰 No Match 😔"
        result_text = f"**{result_display}**\n\nNo symbols match. You lost **${wager_usd:.2f} USD**."

    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)  # Add rakeback
    save_balances(balances)

    # Start with spinning animation
    embed = discord.Embed(title="🎰 Slots - Spinning...", color=0xffaa00)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
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
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
    embed.set_footer(text="Jackpot: 2x | Two Match: 1.0x")

    await interaction.edit_original_response(embed=embed)

# Import card generator
from card_generator import CardImageGenerator

# Global card generator
card_generator = CardImageGenerator()

# BLACKJACK
@bot.tree.command(name="blackjack", description="Play Blackjack against the dealer (in USD)")
async def blackjack(interaction: discord.Interaction, wager_usd: float):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.01:
        await interaction.response.send_message("❌ Minimum wager is $0.01 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    # Create deck
    suits = ['♠️', '♥️', '♦️', '♣️']
    ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    deck = [(rank, suit) for suit in suits for rank in ranks]
    random.shuffle(deck)

    # Deal initial cards
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    def card_value(card):
        rank = card[0]
        if rank in ['J', 'Q', 'K']:
            return 10
        elif rank == 'A':
            return 11
        else:
            return int(rank)

    def hand_value(hand):
        value = sum(card_value(card) for card in hand)
        aces = sum(1 for card in hand if card[0] == 'A')
        while value > 21 and aces:
            value -= 10
            aces -= 1
        return value

    def format_hand(hand, hide_first=False):
        if hide_first:
            return f"🂠 {hand[1][0]}{hand[1][1]}"
        return " ".join(f"{card[0]}{card[1]}" for card in hand)

    player_value = hand_value(player_hand)
    dealer_value = hand_value(dealer_hand)

    # Check for initial blackjack
    player_blackjack = player_value == 21
    dealer_blackjack = dealer_value == 21

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
        embed.add_field(name="🃏 Your Hand", value=f"{format_hand(player_hand)} = {player_value}", inline=True)
        embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(dealer_hand)} = {dealer_value}", inline=True)
        embed.add_field(name="🎯 Result", value=result_text, inline=False)
        embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
        embed.set_footer(text="Blackjack pays 1.5x")

        await interaction.response.send_message(embed=embed)
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
            self.can_split = self.check_can_split()
            self.card_generator = CardImageGenerator()

        def check_can_split(self):
            if len(self.player_hands[0]) == 2 and self.split_count < 3:
                card1, card2 = self.player_hands[0]
                return card_value(card1) == card_value(card2)
            return False

        def get_current_hand(self):
            return self.player_hands[self.current_hand_index]

        def format_all_hands(self):
            result = ""
            for i, hand in enumerate(self.player_hands):
                indicator = "👉 " if i == self.current_hand_index and not self.hands_completed[i] else "   "
                status = " ✅" if self.hands_completed[i] else ""
                result += f"{indicator}Hand {i+1}: {format_hand(hand)} = {hand_value(hand)}{status}\n"
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
            player_value = hand_value(current_hand)

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
                await interaction.response.send_message(f"❌ Insufficient balance! You have ${current_balance_usd:.2f} USD but need ${self.wager_usd:.2f} USD to double down.", ephemeral=True)
                return

            balances[self.user_id]["balance"] -= self.wager_usd
            self.total_wager += self.wager_usd
            current_hand = self.get_current_hand()
            current_hand.append(self.deck.pop())
            player_value = hand_value(current_hand)

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
                await interaction.response.send_message(f"❌ Insufficient balance! You have ${current_balance_usd:.2f} USD but need ${self.wager_usd:.2f} USD to split.", ephemeral=True)
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
                    self.can_split = self.check_can_split() if i == 0 else False
                    self.update_buttons()
                    return
            # If no more hands, mark game for dealer
            self.current_hand_index = len(self.player_hands)

        async def create_game_image(self, show_dealer_cards=False):
            """Create combined game image showing both player and dealer hands"""
            try:
                current_hand = self.get_current_hand() if self.current_hand_index < len(self.player_hands) else self.player_hands[0]
                player_img_path = f"temp_player_{self.user_id}_{time.time()}.png"
                dealer_img_path = f"temp_dealer_{self.user_id}_{time.time()}.png"

                self.card_generator.save_hand_image(current_hand, player_img_path)
                self.card_generator.save_hand_image(self.dealer_hand, dealer_img_path, hide_first=not show_dealer_cards)

                return player_img_path, dealer_img_path
            except Exception as e:
                print(f"Error creating game images: {e}")
                return None, None

        async def update_display(self, interaction, title):
            # Create card images
            player_img, dealer_img = await self.create_game_image(show_dealer_cards=False)

            embed = discord.Embed(title=title, color=0x0099ff)

            # Add hand information
            current_hand = self.get_current_hand() if self.current_hand_index < len(self.player_hands) else self.player_hands[0]
            player_value = hand_value(current_hand)

            embed.add_field(name="🃏 Your Hand", value=f"{format_hand(current_hand)} = **{player_value}**", inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand, hide_first=True)} = **?**", inline=True)
            embed.add_field(name="💰 Total Wager", value=f"${self.total_wager:.2f} USD", inline=True)

            if len(self.player_hands) > 1:
                embed.add_field(name="👉 Current Hand", value=f"Hand {self.current_hand_index + 1} of {len(self.player_hands)}", inline=True)
                embed.add_field(name="🃏 All Hands", value=self.format_all_hands(), inline=False)

            embed.set_footer(text="Hit: take card | Stand: keep hand | Double Down: double bet + 1 card | Split: split pairs")

            # Attach card images if available
            files = []
            if player_img and os.path.exists(player_img):
                files.append(discord.File(player_img, filename="player_cards.png"))
                embed.set_image(url="attachment://player_cards.png")

            try:
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, view=self, attachments=files)
                else:
                    await interaction.response.edit_message(embed=embed, view=self, attachments=files)

                # Clean up image files
                for img_file in [player_img, dealer_img]:
                    if img_file and os.path.exists(img_file):
                        try:
                            os.remove(img_file)
                        except:
                            pass

            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(embed=embed, view=self, files=files)
                except:
                    pass

        async def dealer_play(self, interaction):
            self.clear_items()

            embed = discord.Embed(title="🃏 Blackjack - Dealer's Turn", color=0xffaa00)
            embed.add_field(name="🃏 Your Final Hands", value=self.format_all_hands(), inline=False)
            embed.add_field(name="🤖 Dealer Reveals...", value=f"{format_hand(self.dealer_hand)} = {hand_value(self.dealer_hand)}", inline=True)
            embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)

            try:
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, view=self)
                else:
                    await interaction.response.edit_message(embed=embed, view=self)
            except discord.errors.NotFound:
                await interaction.followup.send(embed=embed, view=self)
                return

            await asyncio.sleep(2)

            while hand_value(self.dealer_hand) < 17:
                self.dealer_hand.append(self.deck.pop())
                current_dealer_value = hand_value(self.dealer_hand)

                embed = discord.Embed(title="🃏 Blackjack - Dealer Hits", color=0xffaa00)
                embed.add_field(name="🃏 Your Final Hands", value=self.format_all_hands(), inline=False)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand)} = {current_dealer_value}", inline=True)
                embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)

                try:
                    await interaction.edit_original_response(embed=embed, view=self)
                except discord.errors.NotFound:
                    # Interaction expired during dealer play
                    break
                await asyncio.sleep(1.5)

            await self.finish_game(interaction)

        async def finish_game(self, interaction):
            dealer_value = hand_value(self.dealer_hand)
            results = []
            total_winnings = 0

            for i, hand in enumerate(self.player_hands):
                player_value = hand_value(hand)
                hand_wager = self.wager_usd * (2 if len(hand) > 2 and player_value <= 21 else 1)  # Double down detection

                if player_value > 21:
                    results.append(f"Hand {i+1}: **BUST** ({player_value}) - Lost ${hand_wager:.2f}")
                elif dealer_value > 21:
                    winnings = hand_wager + (hand_wager * 0.82)
                    total_winnings += winnings
                    results.append(f"Hand {i+1}: **WON** ({player_value} vs {dealer_value}) - +${winnings:.2f}")
                elif player_value > dealer_value:
                    winnings = hand_wager + (hand_wager * 0.82)
                    total_winnings += winnings
                    results.append(f"Hand {i+1}: **WON** ({player_value} vs {dealer_value}) - +${winnings:.2f}")
                elif dealer_value > player_value:
                    results.append(f"Hand {i+1}: **LOST** ({player_value} vs {dealer_value}) - Lost ${hand_wager:.2f}")
                else:
                    total_winnings += hand_wager
                    results.append(f"Hand {i+1}: **PUSH** ({player_value}) - Returned ${hand_wager:.2f}")

            balances[self.user_id]["balance"] += total_winnings
            balances[self.user_id]["wagered"] += self.total_wager
            add_rakeback(self.user_id, self.total_wager)
            save_balances(balances)

            new_balance_usd = balances[self.user_id]["balance"]
            net_result = total_winnings - self.total_wager

            color = 0x00ff00 if net_result > 0 else 0xff0000 if net_result < 0 else 0xffff00
            title_emoji = "🎉" if net_result > 0 else "😔" if net_result < 0 else "🤝"
            title = f"🃏 Blackjack - Game Complete! {title_emoji}"

            # Create final game image showing both hands revealed
            player_img, dealer_img = await self.create_game_image(show_dealer_cards=True)

            embed = discord.Embed(title=title, color=color)

            # Show final hands with values
            current_hand = self.player_hands[0] if len(self.player_hands) == 1 else None
            if current_hand:
                player_value = hand_value(current_hand)
                embed.add_field(name="🃏 Your Hand", value=f"{format_hand(current_hand)} = **{player_value}**", inline=True)
            else:
                embed.add_field(name="🃏 Your Hands", value=self.format_all_hands(), inline=False)

            embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand)} = **{dealer_value}**", inline=True)

            # Add game result
            if net_result > 0:
                result_text = f"🎉 **YOU WON!** +${net_result:.2f}"
            elif net_result < 0:
                result_text = f"😔 **YOU LOST** {net_result:.2f}"
            else:
                result_text = f"🤝 **PUSH** - No money lost"

            embed.add_field(name="🎯 Final Result", value=result_text, inline=False)
            embed.add_field(name="💰 Total Wagered", value=f"${self.total_wager:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

            # Attach final game image
            files = []
            if player_img and os.path.exists(player_img):
                files.append(discord.File(player_img, filename="final_game.png"))
                embed.set_image(url="attachment://final_game.png")

            self.game_over = True
            try:
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, view=self, attachments=files)
                else:
                    await interaction.response.edit_message(embed=embed, view=self, attachments=files)

                # Clean up image files
                for img_file in [player_img, dealer_img]:
                    if img_file and os.path.exists(img_file):
                        try:
                            os.remove(img_file)
                        except:
                            pass

            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(embed=embed, view=self, files=files)
                except:
                    pass

    # Create initial card images
    temp_generator = CardImageGenerator()
    player_img = f"initial_player_{user_id}.png"
    dealer_img = f"initial_dealer_{user_id}.png"

    try:
        temp_generator.save_hand_image(player_hand, player_img)
        temp_generator.save_hand_image(dealer_hand, dealer_img, hide_first=True)
    except Exception as e:
        print(f"Error creating initial card images: {e}")

    # Create initial embed
    embed = discord.Embed(title="🃏 Blackjack - Your Turn", color=0x0099ff)
    embed.add_field(name="🃏 Your Hand", value=f"{format_hand(player_hand)} = **{player_value}**", inline=True)
    embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(dealer_hand, hide_first=True)} = **?**", inline=True)
    embed.add_field(name="💰 Wager", value=f"${wager_usd:.2f} USD", inline=True)
    embed.set_footer(text="Hit: take another card | Stand: keep hand | Double Down: double bet + 1 card")

    # Add card image if available
    files = []
    if os.path.exists(player_img):
        files.append(discord.File(player_img, filename="game_cards.png"))
        embed.set_image(url="attachment://game_cards.png")

    view = BlackjackView(player_hand, dealer_hand, deck, wager_usd, user_id)

    try:
        await interaction.response.send_message(embed=embed, view=view, files=files)

        # Clean up image files
        for img_file in [player_img, dealer_img]:
            if os.path.exists(img_file):
                try:
                    os.remove(img_file)
                except:
                    pass
    except Exception as e:
        # Fallback without images
        await interaction.response.send_message(embed=embed, view=view)

# MINES
@bot.tree.command(name="mines", description="Play Mines - find diamonds while avoiding mines! (in USD)")
async def mines(interaction: discord.Interaction, wager_usd: float, mine_count: int):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.01:
        await interaction.response.send_message("❌ Minimum wager is $0.01 USD!", ephemeral=True)
        return

    if mine_count < 1 or mine_count > 24:
        await interaction.response.send_message("❌ Mine count must be between 1-24!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
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
                        embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

                        await interaction.response.edit_message(embed=embed)
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
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
                embed.set_footer(text="Perfect Game Bonus!")

                self.clear_items()
                await interaction.response.edit_message(embed=embed)
                return

            current_winnings_usd = self.wager_usd * self.current_multiplier

            embed = discord.Embed(title="💎 Minesweeper", color=0x0099ff)
            embed.add_field(name="💰 Bet", value=f"${self.wager_usd:.2f} USD", inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
            embed.add_field(name="💎 Current winnings", value=f"${current_winnings_usd:.2f} USD", inline=True)
            embed.add_field(name="💎 Diamonds Found", value=str(self.diamonds_found), inline=True)
            embed.add_field(name="💣 Mines Hidden", value=str(self.mine_count), inline=True)
            embed.add_field(name="⬜ Tiles Left", value=str(25 - len(self.revealed_tiles)), inline=True)
            embed.set_footer(text="Click tiles to find diamonds! Click any revealed diamond to cash out.")

            await interaction.response.edit_message(embed=embed)

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
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
            embed.set_footer(text="Smart move!")

            self.clear_items()
            await interaction.response.edit_message(embed=embed)

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
async def towers(interaction: discord.Interaction, wager_usd: float, difficulty: int = 3):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.01:
        await interaction.response.send_message("❌ Minimum wager is $0.01 USD!", ephemeral=True)
        return

    if difficulty < 2 or difficulty > 4:
        await interaction.response.send_message("❌ Difficulty must be between 2-4!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
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
                self.add_item(button)

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
                    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
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
                    embed.add_field(name="💎 Current Winnings", value=f"${current_winnings_usd:.2f} USD", inline=True)
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
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

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
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
            embed.set_footer(text="Smart move!")

            self.clear_items()
            await interaction.response.edit_message(embed=embed)

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

# LEADERBOARD
@bot.tree.command(name="leaderboard", description="View leaderboards for different categories")
async def leaderboard(interaction: discord.Interaction, category: str):
    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if category not in ["balance", "wagered", "deposited", "withdrawn", "profit"]:
        await interaction.response.send_message("❌ Invalid category! Choose from: balance, wagered, deposited, withdrawn, profit", ephemeral=True)
        return

    current_balances = load_balances()

    if not current_balances:
        await interaction.response.send_message("❌ No user data found!", ephemeral=True)
        return

    leaderboard_data = []

    for user_id, data in current_balances.items():
        try:
            user = bot.get_user(int(user_id))
            display_name = user.display_name if user else f"User #{user_id[-4:]}"

            if category == "balance":
                value = data.get("balance", 0.0)
            elif category == "wagered":
                value = data.get("wagered", 0.0)
            elif category == "deposited":
                value = data.get("deposited", 0.0)
            elif category == "withdrawn":
                value = data.get("withdrawn", 0.0)
            elif category == "profit":
                current_balance = data.get("balance", 0.0)
                total_withdrawn = data.get("withdrawn", 0.0)
                total_deposited = data.get("deposited", 0.0)
                value = current_balance + total_withdrawn - total_deposited

            leaderboard_data.append((display_name, value))
        except:
            continue

    leaderboard_data.sort(key=lambda x: x[1], reverse=True)
    top_10 = leaderboard_data[:10]

    if not top_10:
        await interaction.response.send_message("❌ No data available for this category!", ephemeral=True)
        return

    category_info = {
        "balance": {"title": "💰 Current Balance Leaderboard", "emoji": "💳", "color": 0x00ff00},
        "wagered": {"title": "🎲 Total Wagered Leaderboard", "emoji": "🎯", "color": 0xff6600},
        "deposited": {"title": "⬇️ Total Deposited Leaderboard", "emoji": "💸", "color": 0x0099ff},
        "withdrawn": {"title": "⬆️ Total Withdrawn Leaderboard", "emoji": "💰", "color": 0xffaa00},
        "profit": {"title": "📈 Profit/Loss Leaderboard", "emoji": "📊", "color": 0xffd700}
    }

    info = category_info[category]
    embed = discord.Embed(title=info["title"], color=info["color"])

    leaderboard_text = ""
    for i, (name, value) in enumerate(top_10, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

        if category == "profit":
            profit_emoji = "📈" if value >= 0 else "📉"
            leaderboard_text += f"{medal} **{name}** {profit_emoji} ${value:.2f}\n"
        else:
            leaderboard_text += f"{medal} **{name}** {info['emoji']} ${value:.2f}\n"

    embed.add_field(name=f"🏆 Top {len(top_10)} Players", value=leaderboard_text, inline=False)
    embed.set_footer(text=f"Category: {category.title()} | Updated in real-time")

    await interaction.response.send_message(embed=embed)

# LOAD WITHDRAWAL QUEUE
def load_withdrawal_queue():
    if not os.path.exists("withdrawal_queue.json"):
        return {}
    with open("withdrawal_queue.json", "r") as f:
        return json.load(f)

# SAVE WITHDRAWAL QUEUE
def save_withdrawal_queue(queue):
    with open("withdrawal_queue.json", "w") as f:
        json.dump(queue, f, indent=2)

# WITHDRAW (Modified to use queue system)
@bot.tree.command(name="withdraw", description="Request a withdrawal to your Litecoin address (goes to admin queue)")
async def withdraw(interaction: discord.Interaction, amount_usd: float, ltc_address: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if amount_usd <= 0:
        await interaction.response.send_message("❌ Withdrawal amount must be positive!", ephemeral=True)
        return

    if amount_usd < 1.00:
        await interaction.response.send_message("❌ Minimum withdrawal is $1.00 USD!", ephemeral=True)
        return

    if balances[user_id]["balance"] < amount_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to withdraw ${amount_usd:.2f} USD.")
        return

    # Basic Litecoin address validation
    if not ltc_address.startswith(('L', 'M', '3')) or len(ltc_address) < 26:
        await interaction.response.send_message("❌ Invalid Litecoin address format!", ephemeral=True)
        return

    # Check if user already has a pending withdrawal
    withdrawal_queue = load_withdrawal_queue()
    for withdrawal_id, withdrawal_data in withdrawal_queue.items():
        if withdrawal_data['user_id'] == user_id:
            await interaction.response.send_message("❌ You already have a pending withdrawal request! Please wait for it to be processed.", ephemeral=True)
            return

    # Deduct amount from balance and add to queue
    balances[user_id]["balance"] -= amount_usd
    save_balances(balances)

    # Generate unique withdrawal ID
    withdrawal_id = str(int(time.time() * 1000))  # Timestamp in milliseconds

    # Add to withdrawal queue
    withdrawal_queue[withdrawal_id] = {
        "user_id": user_id,
        "username": interaction.user.display_name,
        "amount_usd": amount_usd,
        "ltc_address": ltc_address,
        "timestamp": time.time(),
        "status": "pending"
    }
    save_withdrawal_queue(withdrawal_queue)

    # Get LTC equivalent for display
    ltc_price = await get_ltc_price()
    ltc_amount = amount_usd / ltc_price

    embed = discord.Embed(
        title="📝 Withdrawal Request Submitted!",
        description="Your withdrawal request has been added to the admin queue",
        color=0xffaa00
    )
    embed.add_field(name="💵 Amount", value=f"${amount_usd:.2f} USD", inline=True)
    embed.add_field(name="🪙 LTC Equivalent", value=f"~{ltc_amount:.6f} LTC", inline=True)
    embed.add_field(name="📍 Address", value=f"`{ltc_address}`", inline=False)
    embed.add_field(name="🆔 Request ID", value=f"`{withdrawal_id}`", inline=True)
    embed.add_field(name="⏳ Status", value="Pending admin approval", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${balances[user_id]['balance']:.2f} USD", inline=True)
    embed.set_footer(text="You will be notified when your withdrawal is processed")

    await interaction.response.send_message(embed=embed)

# ADMIN: HOUSE BALANCE
@bot.tree.command(name="housebalance", description="Admin command to check the house wallet balance")
async def housebalance(interaction: discord.Interaction):
    global ltc_handler
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if not ltc_handler:
        await interaction.response.send_message("❌ Crypto handler not available.", ephemeral=True)
        return

    try:
        house_balance_ltc = await ltc_handler.get_house_balance()
        ltc_price = await get_ltc_price()
        house_balance_usd = house_balance_ltc * ltc_price

        embed = discord.Embed(
            title="🏦 House Wallet Balance",
            color=0x00ff00
        )
        embed.add_field(name="🪙 LTC Balance", value=f"{house_balance_ltc:.8f} LTC", inline=True)
        embed.add_field(name="💵 USD Value", value=f"${house_balance_usd:.2f} USD", inline=True)
        embed.add_field(name="📍 House Address", value=f"`{ltc_handler.house_wallet_address}`", inline=False)
        embed.add_field(name="💱 LTC Price", value=f"${ltc_price:.2f} USD", inline=True)
        embed.set_footer(text="House wallet automatically receives all player deposits")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"❌ Error checking house balance: {str(e)}", ephemeral=True)

# ADMIN: HOUSE WITHDRAW
@bot.tree.command(name="housewithdraw", description="Admin command to withdraw from house wallet to personal address")
async def housewithdraw(interaction: discord.Interaction, amount_ltc: float, personal_address: str):
    global ltc_handler
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if not ltc_handler:
        await interaction.response.send_message("❌ Crypto handler not available.", ephemeral=True)
        return

    # Basic Litecoin address validation
    if not personal_address.startswith(('L', 'M', '3')) or len(personal_address) < 26:
        await interaction.response.send_message("❌ Invalid Litecoin address format!", ephemeral=True)
        return

    if amount_ltc < 0.001:
        await interaction.response.send_message("❌ Minimum withdrawal is 0.001 LTC!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        house_balance = await ltc_handler.get_house_balance()

        if house_balance < amount_ltc:
            await interaction.followup.send(f"❌ Insufficient house balance! Available: {house_balance:.6f} LTC, Requested: {amount_ltc:.6f} LTC", ephemeral=True)
            return

        tx_hash = await ltc_handler.withdraw_from_house_wallet(personal_address, amount_ltc)

        if tx_hash:
            ltc_price = await get_ltc_price()
            amount_usd = amount_ltc * ltc_price

            embed = discord.Embed(
                title="✅ House Withdrawal Successful! 🎉",
                color=0x00ff00
            )
            embed.add_field(name="🪙 LTC Amount", value=f"{amount_ltc:.6f} LTC", inline=True)
            embed.add_field(name="💵 USD Value", value=f"${amount_usd:.2f} USD", inline=True)
            embed.add_field(name="📍 To Address", value=f"`{personal_address}`", inline=False)
            embed.add_field(name="🧾 Transaction Hash", value=f"`{tx_hash}`", inline=False)
            embed.add_field(name="🏦 Remaining House Balance", value=f"{house_balance - amount_ltc:.6f} LTC", inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Withdrawal failed. Please check the address and try again.", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Error processing withdrawal: {str(e)}", ephemeral=True)

# ADMIN: HOUSE DEPOSIT
@bot.tree.command(name="housedeposit", description="Admin command to deposit LTC to house wallet from external address")
async def housedeposit(interaction: discord.Interaction):
    global ltc_handler
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    if not ltc_handler:
        await interaction.response.send_message("❌ Crypto handler not available.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🏦 House Wallet Deposit Information",
        description="Send LTC to this address to add funds to the house wallet",
        color=0x0099ff
    )
    embed.add_field(name="🏦 House Wallet Address", value=f"`{ltc_handler.house_wallet_address}`", inline=False)
    embed.add_field(name="⚠️ Important", value="• Send **ONLY** Litecoin (LTC) to this address\n• Funds will be available immediately after 1 confirmation\n• Use this for topping up the house balance", inline=False)
    embed.set_footer(text="Copy the address above to send LTC from your personal wallet")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# TEST COMMAND
@bot.tree.command(name="test", description="Test if the bot is working")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("Bot is working! ✅")

# CONFIRM DEPOSIT COMMAND
@bot.tree.command(name="confirmdeposit", description="Admin command to credit a user's balance and update their total deposited")
async def confirmdeposit(interaction: discord.Interaction, member: discord.Member, amount_usd: float):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown for the admin user
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    user_id = str(member.id)
    init_user(user_id)

    # Update user's balance and total deposited
    balances[user_id]["balance"] += amount_usd
    balances[user_id]["deposited"] += amount_usd
    save_balances(balances)

    embed = discord.Embed(
        title="✅ Deposit Confirmed & Credited!",
        color=0x00ff00
    )
    embed.add_field(name="👤 User", value=member.display_name, inline=True)
    embed.add_field(name="💵 Amount Credited", value=f"${amount_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${balances[user_id]['balance']:.2f} USD", inline=True)
    embed.add_field(name="⬇️ Total Deposited", value=f"${balances[user_id]['deposited']:.2f} USD", inline=True)
    embed.set_footer(text="Deposit manually confirmed by an administrator.")

    await interaction.response.send_message(embed=embed)

    # Notify the user
    try:
        user_embed = discord.Embed(
            title="✅ Deposit Credited",
            description="An administrator has credited your account",
            color=0x00ff00
        )
        user_embed.add_field(name="💵 Amount Credited", value=f"${amount_usd:.2f} USD", inline=True)
        user_embed.add_field(name="💳 New Balance", value=f"${balances[user_id]['balance']:.2f} USD", inline=True)
        user_embed.add_field(name="👑 Processed by", value=interaction.user.display_name, inline=True)
        user_embed.set_footer(text="Contact an admin if you have questions about this credit")

        await member.send(embed=user_embed)
    except discord.Forbidden:
        print(f"Could not send deposit confirmation to user {user_id} - DMs disabled")
    except Exception as e:
        print(f"Error sending deposit confirmation: {e}")

# QUEUE COMMAND
@bot.tree.command(name="queue", description="Admin command to view all pending withdrawal requests")
async def queue(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    withdrawal_queue = load_withdrawal_queue()

    if not withdrawal_queue:
        embed = discord.Embed(
            title="📋 Withdrawal Queue",
            description="No pending withdrawal requests",
            color=0x00ff00
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Sort by timestamp (oldest first)
    sorted_withdrawals = sorted(withdrawal_queue.items(), key=lambda x: x[1]['timestamp'])

    embed = discord.Embed(
        title="📋 Pending Withdrawal Requests",
        description=f"Total requests: {len(sorted_withdrawals)}",
        color=0xffaa00
    )

    queue_text = ""
    for i, (withdrawal_id, data) in enumerate(sorted_withdrawals[:10], 1):  # Show max 10
        timestamp = data['timestamp']
        time_ago = int(time.time() - timestamp)
        hours = time_ago // 3600
        minutes = (time_ago % 3600) // 60

        time_str = f"{hours}h {minutes}m ago" if hours > 0 else f"{minutes}m ago"

        queue_text += f"**{i}.** {data['username']}\n"
        queue_text += f"   💵 ${data['amount_usd']:.2f} USD\n"
        queue_text += f"   📍 `{data['ltc_address'][:20]}...`\n"
        queue_text += f"   🆔 ID: `{withdrawal_id}`\n"
        queue_text += f"   ⏰ {time_str}\n\n"

    if len(queue_text) > 1024:  # Discord field limit
        queue_text = queue_text[:1000] + "..."

    embed.add_field(name="📋 Queue", value=queue_text if queue_text else "No pending requests", inline=False)

    if len(sorted_withdrawals) > 10:
        embed.set_footer(text="Showing 10 of {len(sorted_withdrawals)} requests. Use /confirmwithdraw to process them.")
    else:
        embed.set_footer(text="Use /confirmwithdraw [withdrawal_id] to process requests")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# CONFIRM WITHDRAW COMMAND
@bot.tree.command(name="confirmwithdraw", description="Admin command to confirm and process a withdrawal from the queue")
async def confirmwithdraw(interaction: discord.Interaction, withdrawal_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    withdrawal_queue = load_withdrawal_queue()

    if withdrawal_id not in withdrawal_queue:
        await interaction.response.send_message("❌ Withdrawal request not found! Use `/queue` to see pending requests.", ephemeral=True)
        return

    withdrawal_data = withdrawal_queue[withdrawal_id]
    user_id = withdrawal_data['user_id']
    amount_usd = withdrawal_data['amount_usd']
    ltc_address = withdrawal_data['ltc_address']
    username = withdrawal_data['username']

    # Remove from queue
    del withdrawal_queue[withdrawal_id]
    save_withdrawal_queue(withdrawal_queue)

    # Update user's withdrawn stat
    init_user(user_id)
    balances[user_id]["withdrawn"] += amount_usd
    save_balances(balances)

    embed = discord.Embed(
        title="✅ Withdrawal Confirmed & Processed!",
        color=0x00ff00
    )
    embed.add_field(name="👤 User", value=username, inline=True)
    embed.add_field(name="💵 Amount", value=f"${amount_usd:.2f} USD", inline=True)
    embed.add_field(name="📍 Address", value=f"`{ltc_address}`", inline=False)
    embed.add_field(name="🆔 Request ID", value=f"`{withdrawal_id}`", inline=True)
    embed.add_field(name="📊 User's Total Withdrawn", value=f"${balances[user_id]['withdrawn']:.2f} USD", inline=True)
    embed.set_footer(text="Withdrawal manually processed by administrator")

    await interaction.response.send_message(embed=embed)

    # Notify the user
    try:
        user = bot.get_user(int(user_id))
        if user:
            ltc_price = await get_ltc_price()
            ltc_amount = amount_usd / ltc_price

            user_embed = discord.Embed(
                title="✅ Withdrawal Processed!",
                description="Your withdrawal request has been approved and processed",
                color=0x00ff00
            )
            user_embed.add_field(name="💵 Amount", value=f"${amount_usd:.2f} USD", inline=True)
            user_embed.add_field(name="🪙 LTC Equivalent", value=f"~{ltc_amount:.6f} LTC", inline=True)
            user_embed.add_field(name="📍 Address", value=f"`{ltc_address}`", inline=False)
            user_embed.add_field(name="⏰ Status", value="✅ Complete", inline=True)
            user_embed.set_footer(text="Your funds have been sent manually by an administrator")

            await user.send(embed=user_embed)
            await log_withdraw(user, amount_usd, ltc_address)
    except discord.Forbidden:
        print(f"Could not send withdrawal confirmation to user {user_id} - DMs disabled")
    except Exception as e:
        print(f"Error sending withdrawal confirmation: {e}")

# REMOVE BALANCE COMMAND
@bot.tree.command(name="removebalance", description="Admin command to remove balance from a user")
async def removebalance(interaction: discord.Interaction, member: discord.Member, amount_usd: float):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if amount_usd <= 0:
        await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
        return

    user_id = str(member.id)
    init_user(user_id)

    current_balance = balances[user_id]["balance"]

    if current_balance < amount_usd:
        await interaction.response.send_message(f"❌ User only has ${current_balance:.2f} USD but you tried to remove ${amount_usd:.2f} USD!", ephemeral=True)
        return

    # Remove the balance
    balances[user_id]["balance"] -= amount_usd
    save_balances(balances)

    embed = discord.Embed(
        title="💸 Balance Removed Successfully",
        color=0xff6600
    )
    embed.add_field(name="👤 User", value=member.display_name, inline=True)
    embed.add_field(name="💵 Amount Removed", value=f"${amount_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${balances[user_id]['balance']:.2f} USD", inline=True)
    embed.add_field(name="👑 Admin", value=interaction.user.display_name, inline=True)
    embed.set_footer(text="Balance manually removed by administrator")

    await interaction.response.send_message(embed=embed)

    # Notify the user
    try:
        user_embed = discord.Embed(
            title="💸 Balance Adjustment",
            description="An administrator has adjusted your balance",
            color=0xff6600
        )
        user_embed.add_field(name="💵 Amount Removed", value=f"${amount_usd:.2f} USD", inline=True)
        user_embed.add_field(name="💳 New Balance", value=f"${balances[user_id]['balance']:.2f} USD", inline=True)
        user_embed.add_field(name="👑 Processed by", value=interaction.user.display_name, inline=True)
        user_embed.set_footer(text="Contact an admin if you have questions about this adjustment")

        await member.send(embed=user_embed)
    except discord.Forbidden:
        print(f"Could not send balance removal notification to user {user_id} - DMs disabled")
    except Exception as e:
        print(f"Error sending balance removal notification: {e}")

# CREATE PROMO CODE
@bot.tree.command(name="createpromo", description="Admin command to create a promo code")
async def createpromo(interaction: discord.Interaction, code: str, reward_usd: float, max_uses: int):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(interaction.user.id))
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if reward_usd <= 0:
        await interaction.response.send_message("❌ Reward amount must be positive!", ephemeral=True)
        return

    if max_uses <= 0:
        await interaction.response.send_message("❌ Max uses must be positive!", ephemeral=True)
        return

    if len(code) < 3 or len(code) > 20:
        await interaction.response.send_message("❌ Promo code must be between 3-20 characters!", ephemeral=True)
        return

    # Check if code already exists
    if code.upper() in promo_codes:
        await interaction.response.send_message(f"❌ Promo code '{code.upper()}' already exists!", ephemeral=True)
        return

    # Create the promo code
    promo_codes[code.upper()] = {
        "reward_usd": reward_usd,
        "max_uses": max_uses,
        "current_uses": 0,
        "created_by": interaction.user.display_name,
        "created_at": time.time()
    }
    save_promo_codes(promo_codes)

    embed = discord.Embed(
        title="🎫 Promo Code Created Successfully!",
        color=0x00ff00
    )
    embed.add_field(name="🏷️ Code", value=f"`{code.upper()}`", inline=True)
    embed.add_field(name="💰 Reward", value=f"${reward_usd:.2f} USD", inline=True)
    embed.add_field(name="🔢 Max Uses", value=str(max_uses), inline=True)
    embed.add_field(name="👑 Created by", value=interaction.user.display_name, inline=True)
    embed.add_field(name="📊 Current Uses", value="0", inline=True)
    embed.set_footer(text="Users can redeem with /redeem [code]")

    await interaction.response.send_message(embed=embed)

# REDEEM PROMO CODE
@bot.tree.command(name="redeem", description="Redeem a promo code for rewards")
async def redeem(interaction: discord.Interaction, code: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    code_upper = code.upper()

    # Check if promo code exists
    if code_upper not in promo_codes:
        await interaction.response.send_message("❌ Invalid promo code!", ephemeral=True)
        return

    promo_data = promo_codes[code_upper]

    # Check if promo code has uses left
    if promo_data["current_uses"] >= promo_data["max_uses"]:
        await interaction.response.send_message("❌ This promo code has reached its maximum uses!", ephemeral=True)
        return

    # Check if user has already used this promo code
    if user_id not in promo_usage:
        promo_usage[user_id] = []

    if code_upper in promo_usage[user_id]:
        await interaction.response.send_message("❌ You have already used this promo code!", ephemeral=True)
        return

    # Redeem the promo code
    reward_usd = promo_data["reward_usd"]
    balances[user_id]["balance"] += reward_usd
    promo_codes[code_upper]["current_uses"] += 1
    promo_usage[user_id].append(code_upper)

    save_balances(balances)
    save_promo_codes(promo_codes)
    save_promo_usage(promo_usage)

    new_balance_usd = balances[user_id]["balance"]
    remaining_uses = promo_data["max_uses"] - promo_codes[code_upper]["current_uses"]

    embed = discord.Embed(
        title="🎫 Promo Code Redeemed Successfully! 🎉",
        color=0x00ff00
    )
    embed.add_field(name="🏷️ Code", value=f"`{code_upper}`", inline=True)
    embed.add_field(name="💰 Reward", value=f"${reward_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
    embed.add_field(name="📊 Remaining Uses", value=str(remaining_uses), inline=True)
    embed.set_footer(text="Enjoy your bonus!")

    await interaction.response.send_message(embed=embed)

# AFFILIATE
@bot.tree.command(name="affiliate", description="Affiliate yourself to another player to give them 0.5% of your wagers")
async def affiliate(interaction: discord.Interaction, member: discord.Member):
    user_id = str(interaction.user.id)
    affiliate_id = str(member.id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Security checks
    if user_id == affiliate_id:
        await interaction.response.send_message("❌ You cannot affiliate yourself to yourself!", ephemeral=True)
        return

    if member.bot:
        await interaction.response.send_message("❌ You cannot affiliate yourself to bots!", ephemeral=True)
        return

    init_user(user_id)
    init_user(affiliate_id)

    # Check if already affiliated
    current_affiliate = affiliation_data[user_id]["affiliated_to"]
    if current_affiliate == affiliate_id:
        await interaction.response.send_message(f"❌ You are already affiliated to {member.display_name}!", ephemeral=True)
        return

    # Update affiliation
    previous_affiliate = None
    if current_affiliate:
        try:
            previous_affiliate = bot.get_user(int(current_affiliate))
        except:
            pass

    affiliation_data[user_id]["affiliated_to"] = affiliate_id
    save_affiliation_data(affiliation_data)

    embed = discord.Embed(
        title="🤝 Affiliation Updated Successfully! 🎉",
        color=0x00ff00
    )

    if previous_affiliate:
        embed.add_field(name="👤 Previous Affiliate", value=previous_affiliate.display_name, inline=True)

    embed.add_field(name="👤 New Affiliate", value=member.display_name, inline=True)
    embed.add_field(name="💰 Commission Rate", value="0.5%", inline=True)
    embed.add_field(name="ℹ️ How it works", value=f"{member.display_name} will receive 0.5% of all your future wagers as commission", inline=False)
    embed.add_field(name="📊 Your Total Earned", value=f"${affiliation_data[affiliate_id]['total_earned']:.2f} USD", inline=True)
    embed.set_footer(text="Start gambling to generate commission for your affiliate!")

    await interaction.response.send_message(embed=embed)

    # Notify the affiliate
    try:
        affiliate_embed = discord.Embed(
            title="🎉 New Affiliate! 🤝",
            description=f"{interaction.user.display_name} has affiliated themselves to you!",
            color=0x00ff00
        )
        affiliate_embed.add_field(name="💰 You will earn", value="0.5% of their wagers", inline=True)
        affiliate_embed.add_field(name="📊 Your Total Earned", value=f"${affiliation_data[affiliate_id]['total_earned']:.2f} USD", inline=True)

        await member.send(embed=affiliate_embed)
    except discord.Forbidden:
        pass  # User has DMs disabled



# LIMBO
@bot.tree.command(name="limbo", description="Choose your target multiplier and bet in the cosmic void! (in USD)")
async def limbo(interaction: discord.Interaction, wager_usd: float, target_multiplier: float):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.01:
        await interaction.response.send_message("❌ Minimum wager is $0.01 USD!", ephemeral=True)
        return

    if target_multiplier < 1.01 or target_multiplier > 1000:
        await interaction.response.send_message("❌ Target multiplier must be between 1.01x and 1000x!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    # Start animation
    embed = discord.Embed(title="🌌 Limbo - Calculating...", color=0x9932cc)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
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
        # Player wins
        winnings_usd = wager_usd * target_multiplier
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]

        embed = discord.Embed(title="🌌 Limbo - TRANSCENDED! 🎉", color=0x00ff00)
        embed.add_field(name="🎯 Target Hit", value=f"{target_multiplier:.2f}x", inline=True)
        embed.add_field(name="🎲 Win Chance", value=f"{win_chance*100:.1f}%", inline=True)
        embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
        embed.add_field(name="✨ Result", value="🌟 The cosmos favor you! 🌟", inline=False)
    else:
        # Player loses
        balances[user_id]["balance"] -= wager_usd
        new_balance_usd = balances[user_id]["balance"]

        embed = discord.Embed(title="🌌 Limbo - LOST IN THE VOID 😔", color=0xff0000)
        embed.add_field(name="🎯 Target Missed", value=f"{target_multiplier:.2f}x", inline=True)
        embed.add_field(name="🎲 Win Chance", value=f"{win_chance*100:.1f}%", inline=True)
        embed.add_field(name="💸 Lost", value=f"${wager_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
        embed.add_field(name="🌑 Result", value="The void claims another soul...", inline=False)

    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    await interaction.edit_original_response(embed=embed)

# PLINKO
@bot.tree.command(name="plinko", description="Drop a ball down the Plinko board with customizable rows and difficulty! (in USD)")
async def plinko(interaction: discord.Interaction, wager_usd: float, rows: int = 8, difficulty: str = "medium"):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if wager_usd <= 0:
        await interaction.response.send_message("❌ Wager amount must be positive!", ephemeral=True)
        return

    if wager_usd < 0.01:
        await interaction.response.send_message("❌ Minimum wager is $0.01 USD!", ephemeral=True)
        return

    if rows < 8 or rows > 16:
        await interaction.response.send_message("❌ Rows must be between 8-16!", ephemeral=True)
        return

    if difficulty.lower() not in ["low", "medium", "high"]:
        await interaction.response.send_message("❌ Difficulty must be 'low', 'medium', or 'high'!", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
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
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
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
        embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
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
        embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
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

    await interaction.edit_original_response(embed=embed)

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
📤 `/withdraw [amount] [address]` - Request withdrawal (goes to admin queue)
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
📋 `/queue` - View pending withdrawal requests
✅ `/confirmwithdraw [withdrawal_id]` - Process withdrawal from queue
✅ `/confirmdeposit [user] [amount]` - Credit a user's balance manually
🏦 `/housebalance` - Check house wallet balance
📤 `/housewithdraw [amount] [address]` - Withdraw from house wallet
💰 `/housedeposit` - Get house wallet address for deposits
🎫 `/createpromo [code] [reward] [max_uses]` - Create a promo code
        """
        embed.add_field(name="👑 Admin Commands", value=admin_text, inline=False)

    # Additional Info
    embed.add_field(name="💡 Important Info", value="• All amounts are in USD\n• Minimum wager: $0.01\n• Rakeback rate: 0.5%\n• Commands have 1 second cooldown", inline=False)

    embed.set_footer(text="🎲 Good luck and gamble responsibly!")

    await interaction.response.send_message(embed=embed)

# Run the bot
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
