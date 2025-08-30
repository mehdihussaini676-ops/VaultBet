@bot.slash_command(name="deposit", description="Generate a Litecoin deposit address")
async def generate_deposit(ctx):
    user_id = str(ctx.author.id)
    
    # Ensure ltc_handler is initialized
    if not ltc_handler:
        await ctx.respond("❌ Litecoin deposits are currently unavailable. Please contact an admin.", ephemeral=True)
        return
    
    init_user(user_id)
    
    # Generate deposit address
    deposit_address = await ltc_handler.generate_deposit_address(user_id)
    
    if deposit_address:
        # Send detailed DM with deposit instructions
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
            value=f"`{deposit_address}`",
            inline=False
        )
        
        embed.set_footer(text="⚡ All deposits are processed automatically • Keep this address safe")
        
        try:
            # Try to send DM first
            await ctx.author.send(embed=embed)
            await ctx.respond("📨 I've sent you a DM with your deposit address and instructions!", ephemeral=True)
        except discord.Forbidden:
            await ctx.respond("❌ I couldn't send you a DM. Please enable DMs from server members.", ephemeral=True)
    else:
        await ctx.respond("❌ Failed to generate deposit address. Please try again later.", ephemeral=True)
import discord
from discord.ext import commands
import os
import random
import json
import aiohttp
import asyncio
from dotenv import load_dotenv
from crypto_handler import init_litecoin_handler, ltc_handler

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_ID").split(",")]
BLOCKCYPHER_API_KEY = os.getenv("BLOCKCYPHER_API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix="!", intents=intents)

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

# Initialize Litecoin handler
if BLOCKCYPHER_API_KEY:
    init_litecoin_handler(BLOCKCYPHER_API_KEY, WEBHOOK_SECRET)

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

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Bot is in {len(bot.guilds)} guilds")

    # Print all registered commands for debugging
    print("Registered commands:")
    for command in bot.pending_application_commands:
        print(f"  - /{command.name}: {command.description}")

    try:
        # Force sync commands globally
        synced = await bot.sync_commands(force=True)
        if synced is not None:
            print(f"Synced {len(synced)} commands globally")
        else:
            print("Commands synced successfully")

        # Also sync to each guild specifically
        for guild in bot.guilds:
            try:
                guild_synced = await bot.sync_commands(guild=guild, force=True)
                if guild_synced is not None:
                    print(f"Synced {len(guild_synced)} commands to guild {guild.name}")
                else:
                    print(f"Commands synced to guild {guild.name}")
            except Exception as guild_e:
                print(f"Failed to sync commands to guild {guild.name}: {guild_e}")

    except Exception as e:
        print(f"Failed to sync commands globally: {e}")

# BALANCE
@bot.slash_command(name="balance", description="Check your USD balance and statistics")
async def balance(ctx):
    user_id = str(ctx.author.id)
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
        title=f"💰 {ctx.author.display_name}'s Account Statistics",
        color=0x00ff00 if profit_loss_usd >= 0 else 0xff0000
    )

    embed.add_field(name="💳 Current Balance", value=f"${current_balance_usd:.2f} USD", inline=True)
    embed.add_field(name="⬇️ Total Deposited", value=f"${total_deposited_usd:.2f} USD", inline=True)
    embed.add_field(name="⬆️ Total Withdrawn", value=f"${total_withdrawn_usd:.2f} USD", inline=True)
    embed.add_field(name="🎲 Total Wagered", value=f"${total_wagered_usd:.2f} USD", inline=True)
    embed.add_field(name=f"{profit_loss_emoji} Profit/Loss", value=f"${profit_loss_usd:.2f} USD", inline=True)
    embed.add_field(name="📊 Win Rate", value="Coming Soon!", inline=True)

    embed.set_footer(text="Use /coinflip, /dice, /rps, or /slots to gamble!")

    await ctx.respond(embed=embed)

# CLAIM RAKEBACK
@bot.slash_command(name="claimrakeback", description="Claim your accumulated rakeback (0.5% of total wagered)")
async def claimrakeback(ctx):
    user_id = str(ctx.author.id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    init_user(user_id)

    rakeback_earned_usd = rakeback_data[user_id]["rakeback_earned"]

    if rakeback_earned_usd <= 0:
        await ctx.respond("❌ You don't have any rakeback to claim! Start gambling to earn rakeback.", ephemeral=True)
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

    await ctx.respond(embed=embed)

# TIP PLAYER
@bot.slash_command(name="tip", description="Tip another player some of your balance (in USD)")
async def tip(ctx, member: discord.Member, amount_usd: float):
    user_id = str(ctx.author.id)
    target_id = str(member.id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Security checks
    if user_id == target_id:
        await ctx.respond("❌ You cannot tip yourself!", ephemeral=True)
        return

    if member.bot:
        await ctx.respond("❌ You cannot tip bots!", ephemeral=True)
        return

    if amount_usd <= 0:
        await ctx.respond("❌ Tip amount must be positive!", ephemeral=True)
        return

    if amount_usd < 0.01:
        await ctx.respond("❌ Minimum tip amount is $0.01 USD!", ephemeral=True)
        return

    if amount_usd > 1000:
        await ctx.respond("❌ Maximum tip amount is $1000 USD!", ephemeral=True)
        return

    init_user(user_id)
    init_user(target_id)

    if balances[user_id]["balance"] < amount_usd:
        current_balance_usd = balances[user_id]["balance"]
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to tip ${amount_usd:.2f} USD.")
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
    embed.add_field(name="👤 From", value=ctx.author.display_name, inline=True)
    embed.add_field(name="👤 To", value=member.display_name, inline=True)
    embed.add_field(name="💰 Amount", value=f"${amount_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 Your New Balance", value=f"${sender_new_balance_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 Their New Balance", value=f"${receiver_new_balance_usd:.2f} USD", inline=True)
    embed.set_footer(text="Spread the love!")

    await ctx.respond(embed=embed)

# ADMIN: ADD BALANCE
@bot.slash_command(name="addbalance", description="Admin command to add balance to a user (in USD)")
async def addbalance(ctx, member: discord.Member, amount_usd: float):
    if not is_admin(ctx.author.id):
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(ctx.author.id))
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
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

    await ctx.respond(embed=embed)

# COINFLIP
@bot.slash_command(name="coinflip", description="Flip a coin to win or lose your wager (in USD)")
async def coinflip(ctx, choice: discord.Option(str, "Choose heads or tails", choices=["heads", "tails"]), wager_usd: float):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    coin_flip = random.choice(["heads", "tails"])
    won = coin_flip == choice

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

    await ctx.respond(embed=embed)

# DICE
@bot.slash_command(name="dice", description="Roll a dice and win if it's over 3 (in USD)")
async def dice(ctx, wager_usd: float):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
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
    add_rakeback(user_id, wager_usd)  # Add rakeback
    save_balances(balances)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

    await ctx.respond(embed=embed)

# ROCK PAPER SCISSORS
@bot.slash_command(name="rps", description="Play Rock Paper Scissors (in USD)")
async def rps(ctx, choice: discord.Option(str, "Your choice", choices=["rock", "paper", "scissors"]), wager_usd: float):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    choices = ["rock", "paper", "scissors"]
    bot_choice = random.choice(choices)

    # Emojis for choices
    choice_emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

    win_map = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

    if bot_choice == choice:
        # Tie - no money changes hands
        new_balance_usd = balances[user_id]["balance"]
        color = 0xffff00
        title = "🤝 Rock Paper Scissors - It's a Tie!"
        result_text = f"You both chose **{choice}** {choice_emojis[choice]}!"
    elif win_map[choice] == bot_choice:
        # Player wins - 78% RTP (22% house edge)
        winnings_usd = wager_usd * 0.78
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0x00ff00
        title = "🤜 Rock Paper Scissors - YOU WON! 🎉"
        result_text = f"Your **{choice}** {choice_emojis[choice]} beats **{bot_choice}** {choice_emojis[bot_choice]}!"
    else:
        # Player loses
        balances[user_id]["balance"] -= wager_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0xff0000
        title = "🤛 Rock Paper Scissors - You Lost 😔"
        result_text = f"**{bot_choice}** {choice_emojis[bot_choice]} beats your **{choice}** {choice_emojis[choice]}."

    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)  # Add rakeback
    save_balances(balances)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

    await ctx.respond(embed=embed)

# SLOTS
@bot.slash_command(name="slots", description="Spin the slot machine! (in USD)")
async def slots(ctx, wager_usd: float):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
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
        result_text = f"**{result_display}**\n\nAll three match! You won **${winnings_usd:.2f} USD** (4x multiplier)!"
    elif len(set(result)) == 2:
        # Two symbols match (reduced to 1.0x for higher house edge)
        multiplier = 1.0
        winnings_usd = wager_usd * multiplier
        balances[user_id]["balance"] += winnings_usd
        new_balance_usd = balances[user_id]["balance"]
        color = 0x00ff00
        title = "🎰 Nice Win! 🎉"
        result_text = f"**{result_display}**\n\nTwo symbols match! You won **${winnings_usd:.2f} USD** (1.5x multiplier)!"
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

    await ctx.respond(embed=embed)



# ADMIN: RESET STATS
@bot.slash_command(name="resetstats", description="Admin command to reset everything about a user including balance")
async def resetstats(ctx, member: discord.Member):
    if not is_admin(ctx.author.id):
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(ctx.author.id))
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    user_id = str(member.id)

    # Check if user exists
    if user_id not in balances:
        await ctx.respond("❌ User not found in the system!", ephemeral=True)
        return

    # Reset EVERYTHING including balance
    balances[user_id] = {
        "balance": 0.0,
        "deposited": 0.0,
        "withdrawn": 0.0,
        "wagered": 0.0
    }
    save_balances(balances)

    # Note: Automatic withdrawals are processed immediately, no queue cleanup needed
    removed_withdrawals = 0

    embed = discord.Embed(
        title="🔄 Complete Account Reset",
        color=0xff6600
    )
    embed.add_field(name="👤 User", value=member.display_name, inline=True)
    embed.add_field(name="💳 New Balance", value="$0.00 USD", inline=True)
    embed.add_field(name="📊 Statistics", value="All reset to 0", inline=True)
    embed.add_field(name="📤 Withdrawals", value="No pending withdrawals (automatic processing)", inline=True)
    embed.add_field(name="⚠️ Action", value="**COMPLETE ACCOUNT WIPE**", inline=False)
    embed.set_footer(text="Balance, statistics, and pending withdrawals have been completely reset.")

    await ctx.respond(embed=embed)

# BLACKJACK
@bot.slash_command(name="blackjack", description="Play Blackjack against the dealer (in USD)")
async def blackjack(ctx, wager_usd: float):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
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
            balances[user_id]["balance"] += wager_usd
            new_balance_usd = balances[user_id]["balance"]
            color = 0xffff00
            title = "🃏 Blackjack - Push! 🤝"
            result_text = "Both you and the dealer have Blackjack!"
        elif player_blackjack:
            # Player wins with blackjack (1.5x payout + return wager)
            total_payout = wager_usd + (wager_usd * 1.5)
            balances[user_id]["balance"] += total_payout
            new_balance_usd = balances[user_id]["balance"]
            winnings_usd = wager_usd * 1.5
            color = 0x00ff00
            title = "🃏 BLACKJACK! 🎉"
            result_text = f"You got Blackjack! Won ${winnings_usd:.2f} USD (1.5x payout)!"
        else:
            # Dealer has blackjack, player loses (wager already deducted)
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

        await ctx.respond(embed=embed)
        return

    # Deduct the initial wager when starting the game
    balances[user_id]["balance"] -= wager_usd
    save_balances(balances)

    # Interactive blackjack game
    class BlackjackView(discord.ui.View):
        def __init__(self, player_hand, dealer_hand, deck, wager_usd, user_id, original_wager_usd, is_split_hand=False, split_hand_index=0, parent_view=None):
            super().__init__(timeout=180)
            self.player_hand = player_hand
            self.dealer_hand = dealer_hand
            self.deck = deck
            self.wager_usd = wager_usd # Current wager, can be doubled
            self.user_id = user_id
            self.original_wager_usd = original_wager_usd
            self.game_over = False
            self.can_double_down = True # Flag to track if double down is allowed
            self.is_split_hand = is_split_hand
            self.split_hand_index = split_hand_index
            self.parent_view = parent_view
            self.can_split = False
            self.split_hands = []
            self.current_hand_index = 0
            
            # Check if splitting is possible (pair on first two cards)
            if not is_split_hand and len(player_hand) == 2 and card_value(player_hand[0]) == card_value(player_hand[1]):
                self.can_split = True

        

        @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, emoji="🃏")
        async def hit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            # Handle split hands
            if self.split_hands:
                current_hand = self.split_hands[self.current_hand_index]
                current_hand.append(self.deck.pop())
                hand_value_num = hand_value(current_hand)
                
                # Once player hits, double down and split are no longer options
                self.can_double_down = False
                self.can_split = False
                for item in self.children:
                    if hasattr(item, 'label') and item.label in ["Double Down", "Split"]:
                        item.disabled = True
                        item.style = discord.ButtonStyle.gray

                if hand_value_num > 21:
                    # Current split hand busts, move to next hand
                    await self.play_next_split_hand(interaction)
                else:
                    # Update embed with current split hand - highlight active hand
                    hand1_display = f"{format_hand(self.split_hands[0])} = {hand_value(self.split_hands[0])}"
                    hand2_display = f"{format_hand(self.split_hands[1])} = {hand_value(self.split_hands[1])}"
                    
                    # Add indicators to show which hand is active
                    if self.current_hand_index == 0:
                        hand1_display = f"🔥 **{hand1_display}** 🔥"
                    else:
                        hand2_display = f"🔥 **{hand2_display}** 🔥"
                    
                    embed = discord.Embed(title=f"🃏 Blackjack - Playing Split Hand {self.current_hand_index + 1}/2", color=0x0099ff)
                    embed.add_field(name="🃏 Hand 1", value=hand1_display, inline=True)
                    embed.add_field(name="🃏 Hand 2", value=hand2_display, inline=True)
                    embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand, hide_first=True)} = ?", inline=True)
                    embed.add_field(name="💰 Total Wager", value=f"${self.wager_usd * 2:.2f} USD", inline=True)
                    embed.add_field(name="🎯 Current Action", value=f"Playing Hand {self.current_hand_index + 1}", inline=True)
                    embed.set_footer(text=f"🔥 = Currently Playing | Hit or Stand for Hand {self.current_hand_index + 1}")
                    
                    await interaction.response.edit_message(embed=embed, view=self)
                return

            # Regular single hand logic
            self.player_hand.append(self.deck.pop())
            player_value = hand_value(self.player_hand)

            # Once player hits, double down and split are no longer options
            self.can_double_down = False
            self.can_split = False
            for item in self.children:
                if hasattr(item, 'label') and item.label in ["Double Down", "Split"]:
                    item.disabled = True
                    item.style = discord.ButtonStyle.gray

            if player_value > 21:
                # Player busts (wager already deducted when game started)
                balances[self.user_id]["wagered"] += self.wager_usd
                add_rakeback(self.user_id, self.wager_usd)  # Add rakeback
                save_balances(balances)

                new_balance_usd = balances[self.user_id]["balance"]

                embed = discord.Embed(title="🃏 Blackjack - BUST! 💥", color=0xff0000)
                embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand, hide_first=True)} = ?", inline=True)
                embed.add_field(name="🎯 Result", value=f"You busted with {player_value}! You lose ${self.wager_usd:.2f} USD.", inline=False)
                embed.add_field(name="💰 Wagered", value=f"${self.wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

                self.game_over = True
                self.clear_items()  # Only clear buttons when game ends
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                # Update the embed with new hand - player can continue hitting or stand
                embed = discord.Embed(title="🃏 Blackjack - Your Turn", color=0x0099ff)
                embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand, hide_first=True)} = ?", inline=True)
                embed.add_field(name="💰 Wager", value=f"${self.wager_usd:.2f} USD", inline=True)
                embed.set_footer(text="Hit: take another card | Stand: keep hand")

                await interaction.response.edit_message(embed=embed, view=self)

        @discord.ui.button(label="Stand", style=discord.ButtonStyle.red, emoji="✋")
        async def stand_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            # Handle split hands
            if self.split_hands:
                # Move to next split hand
                await self.play_next_split_hand(interaction)
                return

            # Player stands, dealer plays
            player_value = hand_value(self.player_hand)

            # Clear buttons first
            self.clear_items()

            # First, reveal dealer's hidden card with suspense
            embed = discord.Embed(title="🃏 Blackjack - Dealer's Turn", color=0xffaa00)
            embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
            embed.add_field(name="🤖 Dealer Reveals...", value=f"{format_hand(self.dealer_hand)} = {hand_value(self.dealer_hand)}", inline=True)
            embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)

            await interaction.response.edit_message(embed=embed, view=self)

            # Add delay for suspense
            await asyncio.sleep(2)

            # Dealer hits until 17 or higher, revealing each card slowly
            while hand_value(self.dealer_hand) < 17:
                self.dealer_hand.append(self.deck.pop())
                current_dealer_value = hand_value(self.dealer_hand)

                # Show each new card
                embed = discord.Embed(title="🃏 Blackjack - Dealer Hits", color=0xffaa00)
                embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand)} = {current_dealer_value}", inline=True)
                embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)

                await interaction.edit_original_response(embed=embed, view=self)
                await asyncio.sleep(1.5)  # Pause between each card

            dealer_value = hand_value(self.dealer_hand)

            # Determine winner
            if dealer_value > 21:
                # Dealer busts, player wins (82% RTP - 18% house edge)
                winnings = self.wager_usd + (self.wager_usd * 0.82)
                balances[self.user_id]["balance"] += winnings
                color = 0x00ff00
                title = "🃏 Blackjack - YOU WON! 🎉"
                result_text = f"Dealer busted with {dealer_value}!"
            elif player_value > dealer_value:
                # Player wins (82% RTP - 18% house edge)
                winnings = self.wager_usd + (self.wager_usd * 0.82)
                balances[self.user_id]["balance"] += winnings
                color = 0x00ff00
                title = "🃏 Blackjack - YOU WON! 🎉"
                result_text = f"Your {player_value} beats dealer's {dealer_value}!"
            elif dealer_value > player_value:
                # Dealer wins (wager already deducted, do nothing)
                color = 0xff0000
                title = "🃏 Blackjack - Dealer Wins 😔"
                result_text = f"Dealer's {dealer_value} beats your {player_value}."
            else:
                # Push - return wager
                balances[self.user_id]["balance"] += self.wager_usd
                color = 0xffff00
                title = "🃏 Blackjack - Push! 🤝"
                result_text = f"Both have {player_value} - it's a tie!"

            balances[self.user_id]["wagered"] += self.wager_usd
            add_rakeback(self.user_id, self.wager_usd)  # Add rakeback
            save_balances(balances)
            new_balance_usd = balances[self.user_id]["balance"]

            embed = discord.Embed(title=title, color=color)
            embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand)} = {dealer_value}", inline=True)
            embed.add_field(name="🎯 Result", value=result_text, inline=False)
            embed.add_field(name="💰 Wagered", value=f"${self.wager_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

            self.game_over = True
            await interaction.edit_original_response(embed=embed, view=self)

        @discord.ui.button(label="Split", style=discord.ButtonStyle.blurple, emoji="✂️")
        async def split_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if not self.can_split:
                await interaction.response.send_message("You can only split pairs!", ephemeral=True)
                return

            # Check if user has enough balance for the additional wager
            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                await interaction.response.send_message(f"❌ Insufficient balance! You have ${current_balance_usd:.2f} USD but need ${self.wager_usd:.2f} USD to split.", ephemeral=True)
                return

            # Deduct additional wager for split
            balances[self.user_id]["balance"] -= self.wager_usd
            save_balances(balances)

            # Split the hand
            hand1 = [self.player_hand[0]]
            hand2 = [self.player_hand[1]]

            # Deal one card to each split hand
            hand1.append(self.deck.pop())
            hand2.append(self.deck.pop())

            self.split_hands = [hand1, hand2]
            self.current_hand_index = 0
            self.can_split = False
            self.can_double_down = True  # Can double down after split

            # Disable split button and update other buttons
            for item in self.children:
                if hasattr(item, 'label') and item.label == "Split":
                    item.disabled = True
                    item.style = discord.ButtonStyle.gray
                    break

            # Check if first split hand has blackjack
            if hand_value(hand1) == 21:
                # Auto-stand on blackjack, move to second hand
                await self.play_next_split_hand(interaction)
                return

            # Update embed for first split hand with clear indicators
            hand1_display = f"🔥 **{format_hand(hand1)} = {hand_value(hand1)}** 🔥"
            hand2_display = f"{format_hand(hand2)} = {hand_value(hand2)}"
            
            embed = discord.Embed(title="🃏 Blackjack - Playing Split Hand 1/2", color=0x0099ff)
            embed.add_field(name="🃏 Hand 1", value=hand1_display, inline=True)
            embed.add_field(name="🃏 Hand 2", value=hand2_display, inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand, hide_first=True)} = ?", inline=True)
            embed.add_field(name="💰 Total Wager", value=f"${self.wager_usd * 2:.2f} USD", inline=True)
            embed.add_field(name="🎯 Current Action", value="Playing Hand 1", inline=True)
            embed.set_footer(text="🔥 = Currently Playing | Hit, Stand, or Double Down for Hand 1")

            await interaction.response.edit_message(embed=embed, view=self)

        async def play_next_split_hand(self, interaction):
            """Handle transition between split hands"""
            self.current_hand_index += 1
            
            if self.current_hand_index >= len(self.split_hands):
                # All split hands played, dealer plays
                await self.play_dealer_for_split(interaction)
                return
            
            # Move to next hand
            current_hand = self.split_hands[self.current_hand_index]
            self.can_double_down = True
            
            # Re-enable buttons for next hand
            for item in self.children:
                if hasattr(item, 'label') and item.label in ["Hit", "Stand"]:
                    item.disabled = False
                if hasattr(item, 'label') and item.label == "Double Down":
                    item.disabled = False
                    item.style = discord.ButtonStyle.blurple
            
            # Check if this hand has blackjack
            if hand_value(current_hand) == 21:
                # Auto-stand on blackjack, move to next hand
                await self.play_next_split_hand(interaction)
                return
            
            # Update embed for next split hand with clear indicators
            hand1_display = f"{format_hand(self.split_hands[0])} = {hand_value(self.split_hands[0])}"
            hand2_display = f"{format_hand(self.split_hands[1])} = {hand_value(self.split_hands[1])}"
            
            # Add indicators to show which hand is active
            if self.current_hand_index == 0:
                hand1_display = f"🔥 **{hand1_display}** 🔥"
            else:
                hand2_display = f"🔥 **{hand2_display}** 🔥"
            
            embed = discord.Embed(title=f"🃏 Blackjack - Playing Split Hand {self.current_hand_index + 1}/2", color=0x0099ff)
            embed.add_field(name="🃏 Hand 1", value=hand1_display, inline=True)
            embed.add_field(name="🃏 Hand 2", value=hand2_display, inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand, hide_first=True)} = ?", inline=True)
            embed.add_field(name="💰 Total Wager", value=f"${self.wager_usd * 2:.2f} USD", inline=True)
            embed.add_field(name="🎯 Current Action", value=f"Playing Hand {self.current_hand_index + 1}", inline=True)
            embed.set_footer(text=f"🔥 = Currently Playing | Hit, Stand, or Double Down for Hand {self.current_hand_index + 1}")

            await interaction.response.edit_message(embed=embed, view=self)

        async def play_dealer_for_split(self, interaction):
            """Play dealer against split hands"""
            self.clear_items()
            
            # Dealer plays
            embed = discord.Embed(title="🃏 Blackjack - Dealer's Turn (Split)", color=0xffaa00)
            embed.add_field(name="🃏 Hand 1 Final", value=f"{format_hand(self.split_hands[0])} = {hand_value(self.split_hands[0])}", inline=True)
            embed.add_field(name="🃏 Hand 2 Final", value=f"{format_hand(self.split_hands[1])} = {hand_value(self.split_hands[1])}", inline=True)
            embed.add_field(name="🤖 Dealer Reveals...", value=f"{format_hand(self.dealer_hand)} = {hand_value(self.dealer_hand)}", inline=True)
            embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)
            
            await interaction.response.edit_message(embed=embed, view=self)
            await asyncio.sleep(2)
            
            # Dealer hits until 17 or higher
            while hand_value(self.dealer_hand) < 17:
                self.dealer_hand.append(self.deck.pop())
                current_dealer_value = hand_value(self.dealer_hand)
                
                embed = discord.Embed(title="🃏 Blackjack - Dealer Hits (Split)", color=0xffaa00)
                embed.add_field(name="🃏 Hand 1 Final", value=f"{format_hand(self.split_hands[0])} = {hand_value(self.split_hands[0])}", inline=True)
                embed.add_field(name="🃏 Hand 2 Final", value=f"{format_hand(self.split_hands[1])} = {hand_value(self.split_hands[1])}", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand)} = {current_dealer_value}", inline=True)
                embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)
                
                await interaction.edit_original_response(embed=embed, view=self)
                await asyncio.sleep(1.5)
            
            # Determine results for both hands
            dealer_value = hand_value(self.dealer_hand)
            results = []
            total_winnings = 0
            
            for i, hand in enumerate(self.split_hands):
                hand_value_num = hand_value(hand)
                hand_num = i + 1
                
                if hand_value_num > 21:
                    # Hand busted
                    results.append(f"Hand {hand_num}: BUST ({hand_value_num}) - Lost ${self.wager_usd:.2f}")
                elif hand_value_num == 21 and len(hand) == 2:
                    # Blackjack on split (pays 1.5x)
                    if dealer_value == 21:
                        # Push with dealer blackjack
                        balances[self.user_id]["balance"] += self.wager_usd
                        results.append(f"Hand {hand_num}: BLACKJACK PUSH - Returned ${self.wager_usd:.2f}")
                    else:
                        winnings = self.wager_usd + (self.wager_usd * 1.5)
                        balances[self.user_id]["balance"] += winnings
                        total_winnings += self.wager_usd * 1.5
                        results.append(f"Hand {hand_num}: BLACKJACK! - Won ${self.wager_usd * 1.5:.2f}")
                elif dealer_value > 21:
                    # Dealer busts, hand wins
                    winnings = self.wager_usd + (self.wager_usd * 0.82)
                    balances[self.user_id]["balance"] += winnings
                    total_winnings += self.wager_usd * 0.82
                    results.append(f"Hand {hand_num}: WIN (Dealer bust) - Won ${self.wager_usd * 0.82:.2f}")
                elif hand_value_num > dealer_value:
                    # Hand wins
                    winnings = self.wager_usd + (self.wager_usd * 0.82)
                    balances[self.user_id]["balance"] += winnings
                    total_winnings += self.wager_usd * 0.82
                    results.append(f"Hand {hand_num}: WIN ({hand_value_num} vs {dealer_value}) - Won ${self.wager_usd * 0.82:.2f}")
                elif dealer_value > hand_value_num:
                    # Dealer wins
                    results.append(f"Hand {hand_num}: LOSE ({hand_value_num} vs {dealer_value}) - Lost ${self.wager_usd:.2f}")
                else:
                    # Push
                    balances[self.user_id]["balance"] += self.wager_usd
                    results.append(f"Hand {hand_num}: PUSH ({hand_value_num}) - Returned ${self.wager_usd:.2f}")
            
            # Add wagered amount to stats (total of both hands)
            balances[self.user_id]["wagered"] += self.wager_usd * 2
            add_rakeback(self.user_id, self.wager_usd * 2)
            save_balances(balances)
            
            new_balance_usd = balances[self.user_id]["balance"]
            
            # Create final results embed
            if total_winnings > 0:
                title = "🃏 Split Blackjack - Results! 🎉"
                color = 0x00ff00
            else:
                title = "🃏 Split Blackjack - Results"
                color = 0xff0000
            
            embed = discord.Embed(title=title, color=color)
            embed.add_field(name="🃏 Hand 1 Final", value=f"{format_hand(self.split_hands[0])} = {hand_value(self.split_hands[0])}", inline=True)
            embed.add_field(name="🃏 Hand 2 Final", value=f"{format_hand(self.split_hands[1])} = {hand_value(self.split_hands[1])}", inline=True)
            embed.add_field(name="🤖 Dealer Final", value=f"{format_hand(self.dealer_hand)} = {dealer_value}", inline=True)
            embed.add_field(name="🎯 Results", value="\n".join(results), inline=False)
            embed.add_field(name="💰 Total Wagered", value=f"${self.wager_usd * 2:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
            
            self.game_over = True
            await interaction.edit_original_response(embed=embed, view=self)

        @discord.ui.button(label="Double Down", style=discord.ButtonStyle.blurple, emoji="💸")
        async def double_down_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if not self.can_double_down:
                await interaction.response.send_message("You can only double down on your first turn!", ephemeral=True)
                return

            # Check if user has enough balance for the additional wager
            if balances[self.user_id]["balance"] < self.wager_usd:
                current_balance_usd = balances[self.user_id]["balance"]
                needed_usd = self.wager_usd
                await interaction.response.send_message(f"❌ Insufficient balance! You have ${current_balance_usd:.2f} USD but need ${needed_usd:.2f} USD to double down.", ephemeral=True)
                return

            # Handle split hands
            if self.split_hands:
                # Double down on current split hand
                balances[self.user_id]["balance"] -= self.wager_usd
                current_hand = self.split_hands[self.current_hand_index]
                current_hand.append(self.deck.pop())
                hand_value_num = hand_value(current_hand)
                
                self.can_double_down = False
                self.can_split = False
                
                # Update wager for this hand (will be calculated in final results)
                # Move to next hand after double down
                await self.play_next_split_hand(interaction)
                return

            # Player doubles down on single hand
            doubled_wager_usd = self.wager_usd * 2

            balances[self.user_id]["balance"] -= self.wager_usd # Remove the additional wager amount for double down
            self.player_hand.append(self.deck.pop())
            player_value = hand_value(self.player_hand)

            # Player hit only once, now dealer plays
            self.can_double_down = False # Prevent further double downs
            self.clear_items() # Remove buttons

            if player_value > 21:
                # Player busts after doubling down (both wagers already deducted)
                balances[self.user_id]["wagered"] += doubled_wager_usd
                add_rakeback(self.user_id, doubled_wager_usd)  # Add rakeback
                save_balances(balances)
                new_balance_usd = balances[self.user_id]["balance"]

                embed = discord.Embed(title="🃏 Blackjack - BUST After Double Down! 💥", color=0xff0000)
                embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand, hide_first=True)} = ?", inline=True)
                embed.add_field(name="🎯 Result", value=f"You busted with {player_value} after doubling down! You lose ${doubled_wager_usd:.2f} USD.", inline=False)
                embed.add_field(name="💰 Wagered", value=f"${doubled_wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

                self.game_over = True
                await self.update_message(interaction, embed)
            else:
                # Player stands after doubling down, dealer plays with slow reveal
                # First reveal dealer's hidden card
                embed = discord.Embed(title="🃏 Blackjack - Dealer's Turn (Double Down)", color=0xffaa00)
                embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
                embed.add_field(name="🤖 Dealer Reveals...", value=f"{format_hand(self.dealer_hand)} = {hand_value(self.dealer_hand)}", inline=True)
                embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)

                await interaction.edit_original_response(embed=embed, view=self)
                await asyncio.sleep(2)

                # Dealer hits until 17 or higher, revealing each card slowly
                while hand_value(self.dealer_hand) < 17:
                    self.dealer_hand.append(self.deck.pop())
                    current_dealer_value = hand_value(self.dealer_hand)

                    # Show each new card
                    embed = discord.Embed(title="🃏 Blackjack - Dealer Hits (Double Down)", color=0xffaa00)
                    embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
                    embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand)} = {current_dealer_value}", inline=True)
                    embed.add_field(name="⏳ Status", value="Dealer is playing...", inline=False)

                    await interaction.edit_original_response(embed=embed, view=self)
                    await asyncio.sleep(1.5)

                dealer_value = hand_value(self.dealer_hand)

                # Determine winner
                if dealer_value > 21:
                    # Dealer busts, player wins (82% RTP on double down)
                    winnings = doubled_wager_usd + (doubled_wager_usd * 0.82)
                    balances[self.user_id]["balance"] += winnings
                    color = 0x00ff00
                    title = "🃏 Blackjack - YOU WON After Double Down! 🎉"
                    result_text = f"Dealer busted with {dealer_value}! You win ${doubled_wager_usd:.2f} USD."
                elif player_value > dealer_value:
                    # Player wins (82% RTP on double down)
                    winnings = doubled_wager_usd + (doubled_wager_usd * 0.82)
                    balances[self.user_id]["balance"] += winnings
                    color = 0x00ff00
                    title = "🃏 Blackjack - YOU WON After Double Down! 🎉"
                    result_text = f"Your {player_value} beats dealer's {dealer_value}! You win ${doubled_wager_usd:.2f} USD."
                elif dealer_value > player_value:
                    # Dealer wins (doubled wager already deducted, do nothing)
                    color = 0xff0000
                    title = "🃏 Blackjack - Dealer Wins After Double Down 😔"
                    result_text = f"Dealer's {dealer_value} beats your {player_value}! You lose ${doubled_wager_usd:.2f} USD."
                else:
                    # Push - return doubled wager
                    balances[self.user_id]["balance"] += doubled_wager_usd
                    color = 0xffff00
                    title = "🃏 Blackjack - Push After Double Down! 🤝"
                    result_text = f"Both have {player_value} - it's a tie! Your bet is returned."

                balances[self.user_id]["wagered"] += doubled_wager_usd
                add_rakeback(self.user_id, doubled_wager_usd)  # Add rakeback
                save_balances(balances)
                new_balance_usd = balances[self.user_id]["balance"]

                embed = discord.Embed(title=title, color=color)
                embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand)} = {dealer_value}", inline=True)
                embed.add_field(name="🎯 Result", value=result_text, inline=False)
                embed.add_field(name="💰 Wagered", value=f"${doubled_wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

                self.game_over = True
                await self.update_message(interaction, embed)


    # Create initial embed
    embed = discord.Embed(title="🃏 Blackjack - Your Turn", color=0x0099ff)
    embed.add_field(name="🃏 Your Hand", value=f"{format_hand(player_hand)} = {player_value}", inline=True)
    embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(dealer_hand, hide_first=True)} = ?", inline=True)
    embed.add_field(name="💰 Wager", value=f"${wager_usd:.2f} USD", inline=True)
    
    # Check if splitting is possible for footer text
    can_split_pair = len(player_hand) == 2 and card_value(player_hand[0]) == card_value(player_hand[1])
    footer_text = "Hit: take another card | Stand: keep hand | Double Down: double bet + 1 card"
    if can_split_pair:
        footer_text += " | Split: split pair into 2 hands"
    embed.set_footer(text=footer_text)

    view = BlackjackView(player_hand, dealer_hand, deck, wager_usd, user_id, wager_usd)
    await ctx.respond(embed=embed, view=view)

# MINES
@bot.slash_command(name="mines", description="Play Mines - find diamonds while avoiding mines! (in USD)")
async def mines(ctx, wager_usd: float, mine_count: discord.Option(int, "Number of mines (1-24)", min_value=1, max_value=24)):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    # Deduct the wager when starting the game
    balances[user_id]["balance"] -= wager_usd
    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)  # Add rakeback
    save_balances(balances)

    # Generate mine positions (0-24 for 5x5 grid)
    mine_positions = set(random.sample(range(25), min(mine_count, 24)))

    # Calculate multipliers based on mines and diamonds found
    def get_multiplier(diamonds_found, total_mines):
        # Stake.com-style multipliers based on diamonds found and mine count
        if diamonds_found == 0:
            return 0

        # Base multiplier table similar to Stake.com
        safe_tiles = 25 - total_mines

        # Calculate multiplier using probability formula
        # Each safe tile revealed reduces probability of next safe tile
        multiplier = 1.0
        for i in range(diamonds_found):
            remaining_safe = safe_tiles - i
            remaining_total = 25 - i
            multiplier *= remaining_total / remaining_safe

        # Apply house edge (reduce by ~20% for higher house edge)
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

            # Get tile position from custom_id
            tile_pos = int(interaction.data['custom_id'].split('_')[1])

            if tile_pos in self.revealed_tiles:
                # If clicking on a revealed diamond, cash out
                if tile_pos not in self.mine_positions and self.diamonds_found > 0:
                    await self.cashout_callback(interaction)
                    return
                else:
                    await interaction.response.send_message("You've already revealed this tile!", ephemeral=True)
                    return

            self.revealed_tiles.add(tile_pos)

            # Find the button and update it
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

                        # Disable all buttons
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
                        # Keep diamond buttons enabled so they can be clicked to cash out
                        item.disabled = False
                        self.diamonds_found += 1
                        self.current_multiplier = get_multiplier(self.diamonds_found, self.mine_count)
                    break

            # Check if all safe tiles are revealed (perfect game)
            safe_tiles = 25 - self.mine_count
            if self.diamonds_found == safe_tiles:
                # Auto cash out - perfect game
                self.game_over = True
                for child in self.children:
                    child.disabled = True

                # Calculate winnings
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

            # Update the game embed
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

            # Cash out
            self.game_over = True
            for child in self.children:
                child.disabled = True

            # Calculate winnings
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
    await ctx.respond(embed=embed, view=view)

# TOWERS
@bot.slash_command(name="towers", description="Climb towers by choosing the correct path! (in USD)")
async def towers(ctx, wager_usd: float, difficulty: discord.Option(int, "Difficulty level (2-4 paths per level)", min_value=2, max_value=4, default=3)):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if balances[user_id]["balance"] < wager_usd:
        current_balance_usd = balances[user_id]["balance"]
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    # Deduct the wager when starting the game
    balances[user_id]["balance"] -= wager_usd
    balances[user_id]["wagered"] += wager_usd
    add_rakeback(user_id, wager_usd)  # Add rakeback
    save_balances(balances)

    # Generate tower structure - 8 levels, each with 'difficulty' number of paths
    # Only 1 path per level is correct
    tower_structure = []
    for level in range(8):
        correct_path = random.randint(0, difficulty - 1)
        tower_structure.append(correct_path)

    def get_tower_multiplier(level, difficulty):
        # Higher levels and higher difficulty = higher multiplier (reduced for higher house edge)
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
                # Won the game!
                return

            # Add path buttons for current level (max 4 to fit in one row)
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

            # Add cash out button if not on first level
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
                # Correct path! Move to next level
                self.current_level += 1
                self.current_multiplier = get_tower_multiplier(self.current_level, self.difficulty)

                if self.current_level >= 8:
                    # Won the entire tower!
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
                    # Continue to next level
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
                # Wrong path! Game over
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

            # Check cooldown
            can_proceed, remaining_time = check_cooldown(self.user_id)
            if not can_proceed:
                await interaction.response.send_message(f"⏱️ Please wait {remaining_time:.1f} seconds before another action.", ephemeral=True)
                return

            # Cash out
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
    await ctx.respond(embed=embed, view=view)

# LEADERBOARD
@bot.slash_command(name="leaderboard", description="View leaderboards for different categories")
async def leaderboard(ctx, category: discord.Option(str, "Choose leaderboard category", choices=["balance", "wagered", "deposited", "withdrawn", "profit"])):
    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(ctx.author.id))
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    # Load current balances
    current_balances = load_balances()
    
    if not current_balances:
        await ctx.respond("❌ No user data found!", ephemeral=True)
        return

    # Calculate data based on category
    leaderboard_data = []
    
    for user_id, data in current_balances.items():
        try:
            # Get user object for display name
            user = bot.get_user(int(user_id))
            display_name = user.display_name if user else f"User #{user_id[-4:]}"
            
            if category == "balance":
                value = data.get("balance", 0.0)
                leaderboard_data.append((display_name, value))
            elif category == "wagered":
                value = data.get("wagered", 0.0)
                leaderboard_data.append((display_name, value))
            elif category == "deposited":
                value = data.get("deposited", 0.0)
                leaderboard_data.append((display_name, value))
            elif category == "withdrawn":
                value = data.get("withdrawn", 0.0)
                leaderboard_data.append((display_name, value))
            elif category == "profit":
                # Calculate profit/loss
                current_balance = data.get("balance", 0.0)
                total_withdrawn = data.get("withdrawn", 0.0)
                total_deposited = data.get("deposited", 0.0)
                profit_loss = current_balance + total_withdrawn - total_deposited
                leaderboard_data.append((display_name, profit_loss))
        except:
            continue

    # Sort by value (highest first, except for losses in profit category)
    leaderboard_data.sort(key=lambda x: x[1], reverse=True)
    
    # Take top 10
    top_10 = leaderboard_data[:10]
    
    if not top_10:
        await ctx.respond("❌ No data available for this category!", ephemeral=True)
        return

    # Create embed based on category
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
    
    await ctx.respond(embed=embed)

# GENERATE DEPOSIT ADDRESS
@bot.slash_command(name="deposit", description="Generate a Litecoin deposit address")
async def generate_deposit(ctx):
    user_id = str(ctx.author.id)
    
    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return
    
    if not ltc_handler:
        await ctx.respond("❌ Litecoin deposits are currently unavailable. Please contact an admin.", ephemeral=True)
        return
    
    init_user(user_id)
    
    # Generate deposit address
    deposit_address = await ltc_handler.generate_deposit_address(user_id)
    
    if deposit_address:
        # Send detailed DM with deposit instructions
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
            value=f"`{deposit_address}`",
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
            value="Deposits are converted to USD at current market rates",
            inline=False
        )
        
        embed.set_footer(text="⚡ All deposits are processed automatically • Keep this address safe")
        
        try:
            # Try to send DM first
            await ctx.author.send(embed=embed)
            # Confirm in channel that DM was sent
            await ctx.respond("📨 I've sent you a DM with your deposit address and instructions!", ephemeral=True)
        except discord.Forbidden:
            # If DM fails, send as ephemeral response
            await ctx.respond("❌ I couldn't send you a DM. Please enable DMs from server members.", ephemeral=True)
            await ctx.followup.send(embed=embed, ephemeral=True)
    else:
        await ctx.respond("❌ Failed to generate deposit address. Please try again later.", ephemeral=True)

# WITHDRAW
@bot.slash_command(name="withdraw", description="Withdraw your balance to your Litecoin address")
async def withdraw(ctx, amount_usd: float, ltc_address: str):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(user_id)
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    if balances[user_id]["balance"] < amount_usd:
        current_balance_usd = balances[user_id]["balance"]
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to withdraw ${amount_usd:.2f} USD.")
        return

    # Basic Litecoin address validation
    if not ltc_address.startswith(('L', 'M', '3')) or len(ltc_address) < 26:
        await ctx.respond("❌ Invalid Litecoin address format!", ephemeral=True)
        return

    if not ltc_handler:
        await ctx.respond("❌ Automatic withdrawals are currently unavailable. Please try again later.", ephemeral=True)
        return

    # Automatic withdrawal process
    try:
        # Get current LTC price (you'd want to implement a proper price feed)
        ltc_price_usd = await get_ltc_price()  # Implement this function
        ltc_amount = amount_usd / ltc_price_usd

        # Minimum withdrawal check
        if ltc_amount < 0.001:
            await ctx.respond(f"❌ Minimum withdrawal is $1.00 USD (approximately 0.001 LTC)", ephemeral=True)
            return

        # Process withdrawal
        tx_hash = await ltc_handler.send_litecoin(ltc_address, ltc_amount, "master_private_key")  # Use your master wallet

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
            embed.set_footer(text="⚡ Withdrawal processed automatically!")

            await ctx.respond(embed=embed)
            await log_withdraw(ctx.author, amount_usd, ltc_address)
        else:
            await ctx.respond("❌ Withdrawal failed. Please try again later or contact an admin.", ephemeral=True)

    except Exception as e:
        print(f"Withdrawal error: {e}")
        await ctx.respond("❌ Withdrawal failed due to technical error. Please contact an admin.", ephemeral=True)

# HELP
@bot.slash_command(name="help", description="View all available game modes and commands")
async def help_command(ctx):
    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(ctx.author.id))
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎮 VaultBet - Game Modes & Commands",
        description="Welcome to VaultBet! Here are all the available games and commands:",
        color=0x00ff00
    )
    
    # Game Modes Section
    games_text = """
🪙 **Coinflip** - `/coinflip [heads/tails] [amount]`
Call heads or tails and double your money! (80% RTP)

🎲 **Dice Roll** - `/dice [amount]`
Roll a dice and win if it's over 3! (75% RTP)

🤜 **Rock Paper Scissors** - `/rps [choice] [amount]`
Classic game against the bot! (78% RTP)

🎰 **Slots** - `/slots [amount]`
Spin the reels for jackpots and multipliers!

🃏 **Blackjack** - `/blackjack [amount]`
Beat the dealer with strategy! Hit, Stand, Double Down, or Split pairs.

💎 **Mines** - `/mines [amount] [mine_count]`
Find diamonds while avoiding mines! Cash out anytime.

🏗️ **Towers** - `/towers [amount] [difficulty]`
Climb 8 levels by choosing correct paths! Higher risk = higher reward.
    """
    
    embed.add_field(name="🎯 Available Games", value=games_text, inline=False)
    
    # Account Commands Section
    account_text = """
💰 `/balance` - Check your account stats and balance
💸 `/tip [user] [amount]` - Send money to another player
🎁 `/claimrakeback` - Claim 0.5% of your total wagered
📤 `/withdraw [amount] [address]` - Withdraw to crypto address
🏆 `/leaderboard [category]` - View top players in different categories
    """
    
    embed.add_field(name="💳 Account Commands", value=account_text, inline=False)
    
    # Game Info Section
    info_text = """
💡 **Tips:**
• All games have built-in house edge for fair play
• Earn 0.5% rakeback on everything you wager
• Blackjack pays 1.5x for natural blackjack
• Use splitting and doubling strategies in Blackjack
• Mines and Towers let you cash out anytime for current winnings

⚡ **RTP (Return to Player):**
Coinflip: 80% | Dice: 75% | RPS: 78% | Blackjack: 82%+ | Slots: Variable
    """
    
    embed.add_field(name="ℹ️ Game Information", value=info_text, inline=False)
    
    embed.set_footer(text="🎲 Good luck and gamble responsibly! | All amounts in USD")
    embed.set_thumbnail(url="https://i.imgur.com/placeholder.png")  # You can replace with an actual image URL
    
    await ctx.respond(embed=embed)

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

# TEST COMMAND
@bot.slash_command(name="test", description="Test if the bot is working")
async def test(ctx):
    await ctx.respond("Bot is working! ✅")

# ADMIN: SYNC COMMANDS
@bot.slash_command(name="sync", description="Admin command to manually sync slash commands")
async def sync(ctx):
    if not is_admin(ctx.author.id):
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        return

    # Check cooldown
    can_proceed, remaining_time = check_cooldown(str(ctx.author.id))
    if not can_proceed:
        await ctx.respond(f"⏱️ Please wait {remaining_time:.1f} seconds before using another command.", ephemeral=True)
        return

    try:
        # Sync globally first
        synced = await bot.sync_commands(force=True)
        guild_count = 0

        # Sync to current guild specifically
        if ctx.guild:
            guild_synced = await bot.sync_commands(guild=ctx.guild, force=True)
            guild_count = 1

        response = f"Successfully synced commands globally"
        if guild_count > 0:
            response += f" and to this guild"
        response += "! Commands should appear in Discord within a few minutes."

        await ctx.respond(response, ephemeral=True)
    except Exception as e:
        await ctx.respond(f"Failed to sync commands: {e}", ephemeral=True)

bot.run(TOKEN)
