import discord
from discord import app_commands
from discord.ext import commands
import os
import random
import json
import aiohttp
import asyncio    
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_ID", "").split(",") if id.strip()]
BLOCKCYPHER_API_KEY = os.getenv("BLOCKCYPHER_API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

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

# Initialize user
def init_user(user_id):
    if user_id not in balances:
        balances[user_id] = {"balance": 0.0, "deposited": 0.0, "withdrawn": 0.0, "wagered": 0.0}
    if user_id not in rakeback_data:
        rakeback_data[user_id] = {"total_wagered": 0.0, "rakeback_earned": 0.0}

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

# Rakeback system constants
RAKEBACK_PERCENTAGE = 0.005  # 0.5%

# Add rakeback to a user's total wagered amount
def add_rakeback(user_id, wager_amount_usd):
    init_user(user_id)
    rakeback_data[user_id]["total_wagered"] += wager_amount_usd
    rakeback_data[user_id]["rakeback_earned"] += wager_amount_usd * RAKEBACK_PERCENTAGE
    save_rakeback_data(rakeback_data)

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

    # Initialize Litecoin handler with bot instance
    if BLOCKCYPHER_API_KEY and not ltc_handler:
        try:
            from crypto_handler import init_litecoin_handler
            ltc_handler = init_litecoin_handler(BLOCKCYPHER_API_KEY, WEBHOOK_SECRET, bot)
            
            # Initialize house wallet
            house_wallet_initialized = await ltc_handler.initialize_house_wallet()
            if house_wallet_initialized:
                print(f"House wallet initialized: {ltc_handler.house_wallet_address}")
            else:
                print("Failed to initialize house wallet")
            
            # Start blockchain monitoring in background
            asyncio.create_task(ltc_handler.start_blockchain_monitoring())
            print("Crypto handler initialized and blockchain monitoring started")
        except ImportError:
            print("Warning: crypto_handler not available")
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
    embed.add_field(name="📊 Win Rate", value="Coming Soon!", inline=True)

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
    
    save_balances(balances)
    save_rakeback_data(rakeback_data)

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

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

    await interaction.response.send_message(embed=embed)

# DICE
@bot.tree.command(name="dice", description="Roll a dice and win if it's over 3 (in USD)")
async def dice(interaction: discord.Interaction, wager_usd: float):
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

    roll = random.randint(1, 6)
    won = roll > 3

    if won:
        # 75% RTP - pay out 0.75x for wins (25% house edge)
        winnings_usd = wager_usd * 0.75
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0x00ff00
        title = "🎲 Dice Roll - YOU WON! 🎉"
        result_text = f"You rolled a **{roll}** (needed >3 to win)!"
    else:
        balances[user_id]["balance"] -= wager_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0xff0000
        title = "🎲 Dice Roll - You Lost 😔"
        result_text = f"You rolled a **{roll}** (needed >3 to win)."

    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)
    save_balances(balances)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

    await interaction.response.send_message(embed=embed)

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

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
    embed.set_footer(text="Jackpot: 2x | Two Match: 1.0x")

    await interaction.response.send_message(embed=embed)

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

    # Interactive blackjack game with splitting
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
            self.can_split = self.check_can_split()
            self.current_hand_index = 0
            self.hands_completed = [False]  # Track which hands are done
            self.split_count = 0
            self.total_wager = wager_usd

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

        def update_buttons(self):
            for item in self.children:
                if hasattr(item, 'label'):
                    if item.label == "Double Down":
                        item.disabled = not self.can_double_down
                        item.style = discord.ButtonStyle.blurple if self.can_double_down else discord.ButtonStyle.gray
                    elif item.label == "Split":
                        item.disabled = not self.can_split
                        item.style = discord.ButtonStyle.secondary if self.can_split else discord.ButtonStyle.gray

        async def update_display(self, interaction, title):
            embed = discord.Embed(title=title, color=0x0099ff)
            embed.add_field(name="🃏 Your Hands", value=self.format_all_hands(), inline=False)
            embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand, hide_first=True)} = ?", inline=True)
            embed.add_field(name="💰 Total Wager", value=f"${self.total_wager:.2f} USD", inline=True)
            
            if len(self.player_hands) > 1:
                embed.add_field(name="👉 Current Hand", value=f"Hand {self.current_hand_index + 1}", inline=True)
            
            embed.set_footer(text="Hit: take card | Stand: keep hand | Double Down: double bet + 1 card | Split: split pairs")
            await interaction.response.edit_message(embed=embed, view=self)

        async def dealer_play(self, interaction):
            self.clear_items()
            
            embed = discord.Embed(title="🃏 Blackjack - Dealer's Turn", color=0xffaa00)
            embed.add_field(name="🃏 Your Final Hands", value=self.format_all_hands(), inline=False)
            embed.add_field(name="🤖 Dealer Reveals...", value=f"{format_hand(self.dealer_hand)} = {hand_value(self.dealer_hand)}", inline=True)
            embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)

            await interaction.response.edit_message(embed=embed, view=self)
            await asyncio.sleep(2)

            while hand_value(self.dealer_hand) < 17:
                self.dealer_hand.append(self.deck.pop())
                current_dealer_value = hand_value(self.dealer_hand)

                embed = discord.Embed(title="🃏 Blackjack - Dealer Hits", color=0xffaa00)
                embed.add_field(name="🃏 Your Final Hands", value=self.format_all_hands(), inline=False)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand)} = {current_dealer_value}", inline=True)
                embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)

                await interaction.edit_original_response(embed=embed, view=self)
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
                    results.append(f"Hand {i+1}: BUST ({player_value}) - Lost ${hand_wager:.2f}")
                elif dealer_value > 21:
                    winnings = hand_wager + (hand_wager * 0.82)
                    total_winnings += winnings
                    results.append(f"Hand {i+1}: WON ({player_value}) - Dealer bust! +${winnings:.2f}")
                elif player_value > dealer_value:
                    winnings = hand_wager + (hand_wager * 0.82)
                    total_winnings += winnings
                    results.append(f"Hand {i+1}: WON ({player_value} vs {dealer_value}) - +${winnings:.2f}")
                elif dealer_value > player_value:
                    results.append(f"Hand {i+1}: LOST ({player_value} vs {dealer_value}) - Lost ${hand_wager:.2f}")
                else:
                    total_winnings += hand_wager
                    results.append(f"Hand {i+1}: PUSH ({player_value}) - Returned ${hand_wager:.2f}")

            balances[self.user_id]["balance"] += total_winnings
            balances[self.user_id]["wagered"] += self.total_wager
            add_rakeback(self.user_id, self.total_wager)
            save_balances(balances)
            
            new_balance_usd = balances[self.user_id]["balance"]
            net_result = total_winnings - self.total_wager

            color = 0x00ff00 if net_result > 0 else 0xff0000 if net_result < 0 else 0xffff00
            title = "🃏 Blackjack - Game Complete!"

            embed = discord.Embed(title=title, color=color)
            embed.add_field(name="🃏 Your Final Hands", value=self.format_all_hands(), inline=False)
            embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand)} = {dealer_value}", inline=True)
            embed.add_field(name="🎯 Results", value="\n".join(results), inline=False)
            embed.add_field(name="💰 Total Wagered", value=f"${self.total_wager:.2f} USD", inline=True)
            embed.add_field(name="💵 Net Result", value=f"${net_result:+.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

            self.game_over = True
            if hasattr(interaction, 'edit_original_response'):
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)

    # Create initial embed
    embed = discord.Embed(title="🃏 Blackjack - Your Turn", color=0x0099ff)
    embed.add_field(name="🃏 Your Hand", value=f"{format_hand(player_hand)} = {player_value}", inline=True)
    embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(dealer_hand, hide_first=True)} = ?", inline=True)
    embed.add_field(name="💰 Wager", value=f"${wager_usd:.2f} USD", inline=True)
    embed.set_footer(text="Hit: take another card | Stand: keep hand | Double Down: double bet + 1 card")

    view = BlackjackView(player_hand, dealer_hand, deck, wager_usd, user_id)
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

    # Generate mine positions (0-24 for 5x5 grid)
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
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
                embed.set_footer(text="Perfect Game Bonus!")

                await interaction.response.edit_message(embed=embed, view=self)
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
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
            embed.set_footer(text="Smart move!")

            self.clear_items()
            await interaction.response.edit_message(embed=embed, view=self)

    # Create initial embed
    embed = discord.Embed(title="💎 Minesweeper", color=0x0099ff)
    embed.add_field(name="💰 Bet", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="📈 Multiplier", value="1.00x", inline=True)
    embed.add_field(name="💎 Current winnings", value="NONE", inline=True)
    embed.add_field(name="💎 Diamonds Found", value="0", inline=True)
    embed.add_field(name="💣 Mines Hidden", value=str(mine_count), inline=True)
    embed.add_field(name="⬜ Tiles Left", value="25", inline=True)
    embed.set_footer(text="Click tiles to find diamonds! Click any revealed diamond to cash out!")

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
                    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
                    embed.set_footer(text="Congratulations!")

                    self.clear_items()
                    await interaction.response.edit_message(embed=embed, view=self)
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

                    await interaction.response.edit_message(embed=embed, view=self)
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
            await interaction.response.edit_message(embed=embed, view=self)

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

# DEPOSIT COMMAND
@bot.tree.command(name="deposit", description="Generate a Litecoin deposit address")
async def deposit(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if not ltc_handler:
        await interaction.response.send_message("❌ Crypto deposits are currently unavailable. Please contact an admin.", ephemeral=True)
        return

    # Respond immediately to prevent timeout
    await interaction.response.defer(ephemeral=True)

    try:
        init_user(user_id)
        
        # Generate deposit address
        address = await ltc_handler.generate_deposit_address(user_id)
        
        if address:
            # Get current LTC price
            ltc_rate = await get_ltc_price()
            
            embed = discord.Embed(
                title="🪙 Litecoin deposit",
                description="To top up your balance, transfer the desired amount to this address.",
                color=0xffa500
            )
            
            embed.add_field(
                name="Please note:",
                value="1. This is your permanent deposit address.\n2. You can use it as many times as you want.",
                inline=False
            )
            
            embed.add_field(
                name="Litecoin Address:",
                value=f"`{address}`",
                inline=False
            )
            
            embed.add_field(
                name="⚠️ Important Security Notice",
                value="• Send **ONLY** Litecoin (LTC) to this address\n• Other cryptocurrencies will be lost permanently\n• Double-check the address before sending",
                inline=False
            )
            
            embed.add_field(
                name="⏰ Processing Information",
                value="• Deposits are automatically credited after 1 blockchain confirmation\n• Typical confirmation time: ~2.5 minutes\n• You will receive a notification when processed",
                inline=False
            )
            
            embed.add_field(
                name="💱 Exchange Rate",
                value=f"Current LTC Rate: ${ltc_rate:.2f} USD\nDeposits are converted to USD at current market rates",
                inline=False
            )
            
            embed.set_footer(text="⚡ All deposits are processed automatically • Keep this address safe")
            
            try:
                # Try to send DM first
                await interaction.user.send(embed=embed)
                await interaction.followup.send("📨 I've sent you a DM with your deposit address and instructions!", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to generate deposit address. Please try again later.", ephemeral=True)
    except Exception as e:
        print(f"Error in deposit command: {e}")
        try:
            await interaction.followup.send("❌ An error occurred while generating your deposit address. Please try again later.", ephemeral=True)
        except:
            pass  # If followup also fails, ignore to prevent further errors

# WITHDRAW
@bot.tree.command(name="withdraw", description="Withdraw your balance to your Litecoin address")
async def withdraw(interaction: discord.Interaction, amount_usd: float, ltc_address: str):
    user_id = str(interaction.user.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if balances[user_id]["balance"] < amount_usd:
        current_balance_usd = balances[user_id]["balance"]
        await interaction.response.send_message(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to withdraw ${amount_usd:.2f} USD.")
        return

    # Basic Litecoin address validation
    if not ltc_address.startswith(('L', 'M', '3')) or len(ltc_address) < 26:
        await interaction.response.send_message("❌ Invalid Litecoin address format!", ephemeral=True)
        return

    if not ltc_handler:
        await interaction.response.send_message("❌ Automatic withdrawals are currently unavailable. Please try again later.", ephemeral=True)
        return

    try:
        ltc_price_usd = await get_ltc_price()
        ltc_amount = amount_usd / ltc_price_usd

        if ltc_amount < 0.001:
            await interaction.response.send_message(f"❌ Minimum withdrawal is $1.00 USD (approximately 0.001 LTC)", ephemeral=True)
            return

        # Attempt withdrawal from house wallet
        tx_hash = await ltc_handler.withdraw_from_house_wallet(ltc_address, ltc_amount)
        
        if tx_hash:
            # Successful withdrawal
            balances[user_id]["balance"] -= amount_usd
            balances[user_id]["withdrawn"] += amount_usd
            save_balances(balances)

            embed = discord.Embed(
                title="✅ Litecoin Withdrawal Successful! 🎉",
                color=0x00ff00
            )
            embed.add_field(name="💵 Amount", value=f"${amount_usd:.2f} USD", inline=True)
            embed.add_field(name="🪙 LTC Amount", value=f"{ltc_amount:.6f} LTC", inline=True)
            embed.add_field(name="📍 Address", value=f"`{ltc_address}`", inline=False)
            embed.add_field(name="🧾 Transaction Hash", value=f"`{tx_hash}`", inline=False)
            embed.add_field(name="💳 New Balance", value=f"${balances[user_id]['balance']:.2f} USD", inline=True)
            embed.set_footer(text="⚡ Withdrawal processed from house wallet!")

            await interaction.response.send_message(embed=embed)
            await log_withdraw(interaction.user, amount_usd, ltc_address)
        else:
            await interaction.response.send_message("❌ Withdrawal failed. Insufficient house balance or technical error. Please contact an admin.", ephemeral=True)

    except Exception as e:
        print(f"Withdrawal error: {e}")
        await interaction.response.send_message("❌ Withdrawal failed due to technical error. Please contact an admin.", ephemeral=True)

# ADMIN: HOUSE BALANCE
@bot.tree.command(name="housebalance", description="Admin command to check the house wallet balance")
async def housebalance(interaction: discord.Interaction):
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
🎲 `/dice [amount]` - Roll dice, win if >3 (75% RTP)
🤜 `/rps [choice] [amount]` - Rock Paper Scissors (78% RTP)
🎰 `/slots [amount]` - Spin the reels for jackpots!
🃏 `/blackjack [amount]` - Beat the dealer with strategy!
💎 `/mines [amount] [mine_count]` - Find diamonds, avoid mines!
🏗️ `/towers [amount] [difficulty]` - Climb 8 levels choosing paths!
    """

    embed.add_field(name="🎯 Game Commands", value=games_text, inline=False)

    # Account Commands Section
    account_text = """
💰 `/balance` - Check your account stats and balance
💸 `/tip [user] [amount]` - Send money to another player
🎁 `/claimrakeback` - Claim 0.5% of your total wagered
💎 `/deposit` - Generate a Litecoin deposit address
📤 `/withdraw [amount] [address]` - Withdraw to crypto address
🏆 `/leaderboard [category]` - View top players
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
🔄 `/resetstats [user]` - Reset user's complete account
🏦 `/housebalance` - Check house wallet balance
📤 `/housewithdraw [amount] [address]` - Withdraw from house wallet
💰 `/housedeposit` - Get house wallet address for deposits
        """
        embed.add_field(name="👑 Admin Commands", value=admin_text, inline=False)

    # Additional Info
    embed.add_field(name="💡 Important Info", value="• All amounts are in USD\n• Minimum wager: $0.01\n• Rakeback rate: 0.5%\n• Commands have 1 second cooldown", inline=False)

    embed.set_footer(text="🎲 Good luck and gamble responsibly!")

    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN environment variable not set!")
        exit(1)
    bot.run(TOKEN)
