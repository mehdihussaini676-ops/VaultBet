import discord
from discord.ext import commands
import os
import random
import json
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_ID").split(",")]

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

# Load withdraw queue
def load_withdraw_queue():
    if not os.path.exists("withdraw_queue.json"):
        return []
    with open("withdraw_queue.json", "r") as f:
        return json.load(f)

# Save withdraw queue
def save_withdraw_queue(queue):
    with open("withdraw_queue.json", "w") as f:
        json.dump(queue, f)

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

balances = load_balances()
withdraw_queue = load_withdraw_queue()
rakeback_data = load_rakeback_data()

# Rakeback system constants
RAKEBACK_PERCENTAGE = 0.005  # 0.5%

# Add rakeback to a user's total wagered amount
def add_rakeback(user_id, wager_amount_ltc):
    init_user(user_id)
    rakeback_data[user_id]["total_wagered"] += wager_amount_ltc
    rakeback_data[user_id]["rakeback_earned"] += wager_amount_ltc * RAKEBACK_PERCENTAGE
    save_rakeback_data(rakeback_data)

# Get LTC to USD exchange rate
async def get_ltc_to_usd():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd') as response:
                data = await response.json()
                return data['litecoin']['usd']
    except:
        # Fallback rate if API fails
        return 100.0  # Default LTC price

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

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()

    user_data = balances[user_id]
    current_balance_ltc = user_data["balance"]
    total_deposited_ltc = user_data["deposited"]
    total_withdrawn_ltc = user_data["withdrawn"]
    total_wagered_ltc = user_data["wagered"]

    # Convert to USD
    current_balance_usd = current_balance_ltc * ltc_price
    total_deposited_usd = total_deposited_ltc * ltc_price
    total_withdrawn_usd = total_withdrawn_ltc * ltc_price
    total_wagered_usd = total_wagered_ltc * ltc_price

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

    embed.set_footer(text=f"Use /coinflip, /dice, /rps, or /slots to gamble! • LTC Price: ${ltc_price:.2f}")

    await ctx.respond(embed=embed)

# ADMIN: ADD BALANCE
@bot.slash_command(name="addbalance", description="Admin command to add balance to a user (in USD)")
async def addbalance(ctx, member: discord.Member, amount_usd: float):
    if not is_admin(ctx.author.id):
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        return

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    amount_ltc = amount_usd / ltc_price

    user_id = str(member.id)
    init_user(user_id)
    balances[user_id]["balance"] += amount_ltc
    # balances[user_id]["deposited"] += amount_ltc # This line is commented out to implement the feature request for "confirm deposit"
    save_balances(balances)

    embed = discord.Embed(
        title="💰 Balance Added Successfully",
        color=0x00ff00
    )
    embed.add_field(name="👤 User", value=member.display_name, inline=True)
    embed.add_field(name="💵 Amount Added", value=f"${amount_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${(balances[user_id]['balance'] * ltc_price):.2f} USD", inline=True)
    embed.set_footer(text=f"LTC Price: ${ltc_price:.2f}")

    await ctx.respond(embed=embed)

# COINFLIP
@bot.slash_command(name="coinflip", description="Flip a coin to win or lose your wager (in USD)")
async def coinflip(ctx, choice: discord.Option(str, "Choose heads or tails", choices=["heads", "tails"]), wager_usd: float):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    wager_ltc = wager_usd / ltc_price

    if balances[user_id]["balance"] < wager_ltc:
        current_balance_usd = balances[user_id]["balance"] * ltc_price
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    coin_flip = random.choice(["heads", "tails"])
    won = coin_flip == choice

    if won:
        # 95% RTP - pay out 0.95x for wins (5% house edge)
        winnings_ltc = wager_ltc * 0.95
        balances[user_id]["balance"] += winnings_ltc
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0x00ff00
        title = "🪙 Coinflip - YOU WON! 🎉"
        result_text = f"The coin landed on **{coin_flip}** and you called **{choice}**!"
    else:
        balances[user_id]["balance"] -= wager_ltc
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0xff0000
        title = "🪙 Coinflip - You Lost 😔"
        result_text = f"The coin landed on **{coin_flip}** but you called **{choice}**."

    balances[user_id]["wagered"] += wager_ltc
    add_rakeback(user_id, wager_ltc)  # Add rakeback
    save_balances(balances)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
    embed.set_footer(text=f"LTC Price: ${ltc_price:.2f}")

    await ctx.respond(embed=embed)

# DICE
@bot.slash_command(name="dice", description="Roll a dice and win if it's over 3 (in USD)")
async def dice(ctx, wager_usd: float):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    wager_ltc = wager_usd / ltc_price

    if balances[user_id]["balance"] < wager_ltc:
        current_balance_usd = balances[user_id]["balance"] * ltc_price
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    roll = random.randint(1, 6)
    won = roll > 3

    if won:
        # 92% RTP - pay out 0.92x for wins (8% house edge)
        winnings_ltc = wager_ltc * 0.92
        balances[user_id]["balance"] += winnings_ltc
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0x00ff00
        title = "🎲 Dice Roll - YOU WON! 🎉"
        result_text = f"You rolled a **{roll}** (needed >3 to win)!"
    else:
        balances[user_id]["balance"] -= wager_ltc
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0xff0000
        title = "🎲 Dice Roll - You Lost 😔"
        result_text = f"You rolled a **{roll}** (needed >3 to win)."

    balances[user_id]["wagered"] += wager_ltc
    add_rakeback(user_id, wager_ltc)  # Add rakeback
    save_balances(balances)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
    embed.set_footer(text=f"LTC Price: ${ltc_price:.2f}")

    await ctx.respond(embed=embed)

# ROCK PAPER SCISSORS
@bot.slash_command(name="rps", description="Play Rock Paper Scissors (in USD)")
async def rps(ctx, choice: discord.Option(str, "Your choice", choices=["rock", "paper", "scissors"]), wager_usd: float):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    wager_ltc = wager_usd / ltc_price

    if balances[user_id]["balance"] < wager_ltc:
        current_balance_usd = balances[user_id]["balance"] * ltc_price
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    choices = ["rock", "paper", "scissors"]
    bot_choice = random.choice(choices)

    # Emojis for choices
    choice_emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

    win_map = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

    if bot_choice == choice:
        # Tie - no money changes hands
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0xffff00
        title = "🤝 Rock Paper Scissors - It's a Tie!"
        result_text = f"You both chose **{choice}** {choice_emojis[choice]}!"
    elif win_map[choice] == bot_choice:
        # Player wins - 94% RTP (6% house edge)
        winnings_ltc = wager_ltc * 0.94
        balances[user_id]["balance"] += winnings_ltc
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0x00ff00
        title = "🤜 Rock Paper Scissors - YOU WON! 🎉"
        result_text = f"Your **{choice}** {choice_emojis[choice]} beats **{bot_choice}** {choice_emojis[bot_choice]}!"
    else:
        # Player loses
        balances[user_id]["balance"] -= wager_ltc
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0xff0000
        title = "🤛 Rock Paper Scissors - You Lost 😔"
        result_text = f"**{bot_choice}** {choice_emojis[bot_choice]} beats your **{choice}** {choice_emojis[choice]}."

    balances[user_id]["wagered"] += wager_ltc
    add_rakeback(user_id, wager_ltc)  # Add rakeback
    save_balances(balances)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
    embed.set_footer(text=f"LTC Price: ${ltc_price:.2f}")

    await ctx.respond(embed=embed)

# SLOTS
@bot.slash_command(name="slots", description="Spin the slot machine! (in USD)")
async def slots(ctx, wager_usd: float):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    wager_ltc = wager_usd / ltc_price

    if balances[user_id]["balance"] < wager_ltc:
        current_balance_usd = balances[user_id]["balance"] * ltc_price
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    symbols = ["🍒", "🍋", "🍊", "🔔", "⭐"]
    result = [random.choice(symbols) for _ in range(3)]
    result_display = " ".join(result)

    if len(set(result)) == 1:
        # JACKPOT - all 3 match (reduced from 5x to 4x for house edge)
        multiplier = 4.0
        winnings_ltc = wager_ltc * multiplier
        balances[user_id]["balance"] += winnings_ltc
        winnings_usd = winnings_ltc * ltc_price
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0xffd700  # Gold
        title = "🎰 JACKPOT! 💰🎉"
        result_text = f"**{result_display}**\n\nAll three match! You won **${winnings_usd:.2f} USD** (4x multiplier)!"
    elif len(set(result)) == 2:
        # Two symbols match (reduced from 2x to 1.5x for house edge)
        multiplier = 1.5
        winnings_ltc = wager_ltc * multiplier
        balances[user_id]["balance"] += winnings_ltc
        winnings_usd = winnings_ltc * ltc_price
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0x00ff00
        title = "🎰 Nice Win! 🎉"
        result_text = f"**{result_display}**\n\nTwo symbols match! You won **${winnings_usd:.2f} USD** (1.5x multiplier)!"
    else:
        # No match - player loses
        balances[user_id]["balance"] -= wager_ltc
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0xff0000
        title = "🎰 No Match 😔"
        result_text = f"**{result_display}**\n\nNo symbols match. You lost **${wager_usd:.2f} USD**."

    balances[user_id]["wagered"] += wager_ltc
    add_rakeback(user_id, wager_ltc)  # Add rakeback
    save_balances(balances)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
    embed.set_footer(text=f"LTC Price: ${ltc_price:.2f} • Jackpot: 4x | Two Match: 1.5x")

    await ctx.respond(embed=embed)

# WITHDRAW
@bot.slash_command(name="withdraw", description="Withdraw your balance to your LTC address")
async def withdraw(ctx, amount_usd: float, ltc_address: str):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    amount_ltc = amount_usd / ltc_price

    if balances[user_id]["balance"] < amount_ltc:
        current_balance_usd = balances[user_id]["balance"] * ltc_price
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to withdraw ${amount_usd:.2f} USD.")
        return

    # Basic LTC address validation (starts with L, M, or ltc1)
    if not (ltc_address.startswith(('L', 'M', 'ltc1')) and len(ltc_address) >= 26):
        await ctx.respond("❌ Invalid LTC address format!", ephemeral=True)
        return

    # Add to withdraw queue
    import datetime
    withdraw_request = {
        "user_id": user_id,
        "username": ctx.author.display_name,
        "amount_ltc": amount_ltc,
        "amount_usd": amount_usd,
        "ltc_address": ltc_address,
        "timestamp": datetime.datetime.now().isoformat()
    }

    withdraw_queue.append(withdraw_request)
    save_withdraw_queue(withdraw_queue)

    # Deduct from balance
    balances[user_id]["balance"] -= amount_ltc
    balances[user_id]["withdrawn"] += amount_ltc
    save_balances(balances)

    embed = discord.Embed(
        title="📤 Withdrawal Request Submitted",
        color=0x00ff00
    )
    embed.add_field(name="💵 Amount", value=f"${amount_usd:.2f} USD ({amount_ltc:.8f} LTC)", inline=True)
    embed.add_field(name="📍 Address", value=f"`{ltc_address}`", inline=False)
    embed.add_field(name="⏰ Status", value="Pending admin approval", inline=True)
    embed.set_footer(text="Your withdrawal will be processed by an admin shortly.")

    await ctx.respond(embed=embed)

# ADMIN: QUEUE
@bot.slash_command(name="queue", description="Admin command to view pending withdrawals")
async def queue(ctx):
    if not is_admin(ctx.author.id):
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        return

    if not withdraw_queue:
        await ctx.respond("✅ No pending withdrawals!")
        return

    embed = discord.Embed(
        title="📋 Pending Withdrawal Queue",
        color=0xffaa00
    )

    for i, request in enumerate(withdraw_queue, 1):
        embed.add_field(
            name=f"#{i} - {request['username']}",
            value=f"**Amount:** ${request['amount_usd']:.2f} USD ({request['amount_ltc']:.8f} LTC)\n"
                  f"**Address:** `{request['ltc_address']}`\n"
                  f"**Time:** {request['timestamp'][:19]}",
            inline=False
        )

    embed.set_footer(text=f"Total requests: {len(withdraw_queue)}")
    await ctx.respond(embed=embed)

# ADMIN: CONFIRM DEPOSIT
@bot.slash_command(name="confirmdeposit", description="Admin command to confirm a user's deposit")
async def confirmdeposit(ctx, member: discord.Member, amount_usd: float):
    if not is_admin(ctx.author.id):
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        return

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    amount_ltc = amount_usd / ltc_price

    user_id = str(member.id)
    init_user(user_id)
    balances[user_id]["deposited"] += amount_ltc
    save_balances(balances)

    embed = discord.Embed(
        title="✅ Deposit Confirmed",
        color=0x00ff00
    )
    embed.add_field(name="👤 User", value=member.display_name, inline=True)
    embed.add_field(name="💵 Deposit Amount", value=f"${amount_usd:.2f} USD", inline=True)
    embed.add_field(name="📊 Total Deposited", value=f"${(balances[user_id]['deposited'] * ltc_price):.2f} USD", inline=True)
    embed.set_footer(text=f"LTC Price: ${ltc_price:.2f}")

    await ctx.respond(embed=embed)

# ADMIN: CONFIRM WITHDRAW
@bot.slash_command(name="confirmwithdraw", description="Admin command to confirm a withdrawal (remove from queue)")
async def confirmwithdraw(ctx, queue_number: int):
    if not is_admin(ctx.author.id):
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        return

    if not withdraw_queue or queue_number < 1 or queue_number > len(withdraw_queue):
        await ctx.respond("❌ Invalid queue number!", ephemeral=True)
        return

    # Remove from queue (convert to 0-based index)
    confirmed_request = withdraw_queue.pop(queue_number - 1)
    save_withdraw_queue(withdraw_queue)

    embed = discord.Embed(
        title="✅ Withdrawal Confirmed & Processed",
        color=0x00ff00
    )
    embed.add_field(name="👤 User", value=confirmed_request['username'], inline=True)
    embed.add_field(name="💵 Amount", value=f"${confirmed_request['amount_usd']:.2f} USD", inline=True)
    embed.add_field(name="📍 Address", value=f"`{confirmed_request['ltc_address']}`", inline=False)
    embed.set_footer(text="Withdrawal has been processed and removed from queue.")

    await ctx.respond(embed=embed)

# CANCEL WITHDRAW
@bot.slash_command(name="cancelwithdraw", description="Cancel your pending withdrawal")
async def cancelwithdraw(ctx):
    user_id = str(ctx.author.id)

    # Find user's withdrawal in queue
    user_request = None
    user_index = None

    for i, request in enumerate(withdraw_queue):
        if request['user_id'] == user_id:
            user_request = request
            user_index = i
            break

    if not user_request:
        await ctx.respond("❌ You don't have any pending withdrawals!", ephemeral=True)
        return

    # Remove from queue
    withdraw_queue.pop(user_index)
    save_withdraw_queue(withdraw_queue)

    # Return balance to user and adjust stats
    init_user(user_id)
    balances[user_id]["balance"] += user_request['amount_ltc']
    balances[user_id]["withdrawn"] -= user_request['amount_ltc']
    save_balances(balances)

    # Get current LTC price for display
    ltc_price = await get_ltc_to_usd()

    embed = discord.Embed(
        title="🚫 Withdrawal Cancelled",
        color=0xffaa00
    )
    embed.add_field(name="💵 Amount Returned", value=f"${user_request['amount_usd']:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${(balances[user_id]['balance'] * ltc_price):.2f} USD", inline=True)
    embed.set_footer(text="Your withdrawal has been cancelled and balance restored.")

    await ctx.respond(embed=embed)

# ADMIN: RESET STATS
@bot.slash_command(name="resetstats", description="Admin command to reset everything about a user including balance")
async def resetstats(ctx, member: discord.Member):
    if not is_admin(ctx.author.id):
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
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

    # Also remove any pending withdrawals for this user
    global withdraw_queue
    original_queue_length = len(withdraw_queue)
    withdraw_queue = [req for req in withdraw_queue if req['user_id'] != user_id]
    removed_withdrawals = original_queue_length - len(withdraw_queue)

    if removed_withdrawals > 0:
        save_withdraw_queue(withdraw_queue)

    embed = discord.Embed(
        title="🔄 Complete Account Reset",
        color=0xff6600
    )
    embed.add_field(name="👤 User", value=member.display_name, inline=True)
    embed.add_field(name="💳 New Balance", value="$0.00 USD", inline=True)
    embed.add_field(name="📊 Statistics", value="All reset to 0", inline=True)
    embed.add_field(name="📤 Withdrawals", value=f"{removed_withdrawals} pending withdrawals cancelled", inline=True)
    embed.add_field(name="⚠️ Action", value="**COMPLETE ACCOUNT WIPE**", inline=False)
    embed.set_footer(text="Balance, statistics, and pending withdrawals have been completely reset.")

    await ctx.respond(embed=embed)

# BLACKJACK
@bot.slash_command(name="blackjack", description="Play Blackjack against the dealer (in USD)")
async def blackjack(ctx, wager_usd: float):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    wager_ltc = wager_usd / ltc_price

    if balances[user_id]["balance"] < wager_ltc:
        current_balance_usd = balances[user_id]["balance"] * ltc_price
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
            balances[user_id]["balance"] += wager_ltc
            new_balance_usd = balances[user_id]["balance"] * ltc_price
            color = 0xffff00
            title = "🃏 Blackjack - Push! 🤝"
            result_text = "Both you and the dealer have Blackjack!"
        elif player_blackjack:
            # Player wins with blackjack (1.2x payout + return wager for house edge)
            total_payout = wager_ltc + (wager_ltc * 1.2)
            balances[user_id]["balance"] += total_payout
            new_balance_usd = balances[user_id]["balance"] * ltc_price
            winnings_usd = (wager_ltc * 1.2) * ltc_price
            color = 0x00ff00
            title = "🃏 BLACKJACK! 🎉"
            result_text = f"You got Blackjack! Won ${winnings_usd:.2f} USD (1.2x payout)!"
        else:
            # Dealer has blackjack, player loses (wager already deducted)
            new_balance_usd = balances[user_id]["balance"] * ltc_price
            color = 0xff0000
            title = "🃏 Blackjack - Dealer Wins 😔"
            result_text = "Dealer has Blackjack!"

        balances[user_id]["wagered"] += wager_ltc
        add_rakeback(user_id, wager_ltc)  # Add rakeback
        save_balances(balances)

        embed = discord.Embed(title=title, color=color)
        embed.add_field(name="🃏 Your Hand", value=f"{format_hand(player_hand)} = {player_value}", inline=True)
        embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(dealer_hand)} = {dealer_value}", inline=True)
        embed.add_field(name="🎯 Result", value=result_text, inline=False)
        embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
        embed.set_footer(text=f"LTC Price: ${ltc_price:.2f} • Blackjack pays 1.2x")

        await ctx.respond(embed=embed)
        return

    # Deduct the initial wager when starting the game
    balances[user_id]["balance"] -= wager_ltc
    save_balances(balances)

    # Interactive blackjack game
    class BlackjackView(discord.ui.View):
        def __init__(self, player_hand, dealer_hand, deck, wager_ltc, wager_usd, ltc_price, user_id):
            super().__init__(timeout=180)
            self.player_hand = player_hand
            self.dealer_hand = dealer_hand
            self.deck = deck
            self.wager_ltc = wager_ltc
            self.wager_usd = wager_usd
            self.ltc_price = ltc_price
            self.user_id = user_id
            self.game_over = False
            self.can_double_down = True # Flag to track if double down is allowed

        @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, emoji="🃏")
        async def hit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            # Player hits
            self.player_hand.append(self.deck.pop())
            player_value = hand_value(self.player_hand)

            # Once player hits, double down is no longer an option
            self.can_double_down = False

            # Update the buttons to remove double down option if no longer available
            if not self.can_double_down:
                # Find and disable the double down button instead of recreating everything
                for item in self.children:
                    if hasattr(item, 'label') and item.label == "Double Down":
                        item.disabled = True
                        item.style = discord.ButtonStyle.gray
                        break

            if player_value > 21:
                # Player busts (wager already deducted when game started)
                balances[self.user_id]["wagered"] += self.wager_ltc
                add_rakeback(self.user_id, self.wager_ltc)  # Add rakeback
                save_balances(balances)

                new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price

                embed = discord.Embed(title="🃏 Blackjack - BUST! 💥", color=0xff0000)
                embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand, hide_first=True)} = ?", inline=True)
                embed.add_field(name="🎯 Result", value=f"You busted with {player_value}! You lose.", inline=False)
                embed.add_field(name="💰 Wagered", value=f"${self.wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
                embed.set_footer(text=f"LTC Price: ${self.ltc_price:.2f}")

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

            # Player stands, dealer plays
            player_value = hand_value(self.player_hand)

            # Dealer hits until 17 or higher
            while hand_value(self.dealer_hand) < 17:
                self.dealer_hand.append(self.deck.pop())

            dealer_value = hand_value(self.dealer_hand)

            # Determine winner
            if dealer_value > 21:
                # Dealer busts, player wins (96% RTP - 4% house edge)
                winnings = self.wager_ltc + (self.wager_ltc * 0.96)
                balances[self.user_id]["balance"] += winnings
                color = 0x00ff00
                title = "🃏 Blackjack - YOU WON! 🎉"
                result_text = f"Dealer busted with {dealer_value}!"
            elif player_value > dealer_value:
                # Player wins (96% RTP - 4% house edge)
                winnings = self.wager_ltc + (self.wager_ltc * 0.96)
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
                balances[self.user_id]["balance"] += self.wager_ltc
                color = 0xffff00
                title = "🃏 Blackjack - Push! 🤝"
                result_text = f"Both have {player_value} - it's a tie!"

            balances[self.user_id]["wagered"] += self.wager_ltc
            add_rakeback(self.user_id, self.wager_ltc)  # Add rakeback
            save_balances(balances)
            new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price

            embed = discord.Embed(title=title, color=color)
            embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
            embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand)} = {dealer_value}", inline=True)
            embed.add_field(name="🎯 Result", value=result_text, inline=False)
            embed.add_field(name="💰 Wagered", value=f"${self.wager_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
            embed.set_footer(text=f"LTC Price: ${self.ltc_price:.2f}")

            self.game_over = True
            self.clear_items()
            await interaction.response.edit_message(embed=embed, view=self)

        @discord.ui.button(label="Double Down", style=discord.ButtonStyle.blurple, emoji="💸")
        async def double_down_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if not self.can_double_down:
                await interaction.response.send_message("You can only double down on your first turn!", ephemeral=True)
                return

            # Check if user has enough balance for the additional wager (original wager already deducted when game started)
            if balances[self.user_id]["balance"] < self.wager_ltc:
                current_balance_usd = balances[self.user_id]["balance"] * self.ltc_price
                needed_usd = self.wager_usd
                await interaction.response.send_message(f"❌ Insufficient balance! You have ${current_balance_usd:.2f} USD but need ${needed_usd:.2f} USD to double down.", ephemeral=True)
                return

            # Player doubles down
            doubled_wager_ltc = self.wager_ltc * 2
            doubled_wager_usd = self.wager_usd * 2

            balances[self.user_id]["balance"] -= self.wager_ltc # Remove the additional wager amount for double down
            self.player_hand.append(self.deck.pop())
            player_value = hand_value(self.player_hand)

            # Player hit only once, now dealer plays
            self.can_double_down = False # Prevent further double downs
            self.clear_items() # Remove buttons

            if player_value > 21:
                # Player busts after doubling down (both wagers already deducted)
                balances[self.user_id]["wagered"] += doubled_wager_ltc
                add_rakeback(self.user_id, doubled_wager_ltc)  # Add rakeback
                save_balances(balances)
                new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price

                embed = discord.Embed(title="🃏 Blackjack - BUST After Double Down! 💥", color=0xff0000)
                embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand, hide_first=True)} = ?", inline=True)
                embed.add_field(name="🎯 Result", value=f"You busted with {player_value} after doubling down! You lose ${doubled_wager_usd:.2f} USD.", inline=False)
                embed.add_field(name="💰 Wagered", value=f"${doubled_wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
                embed.set_footer(text=f"LTC Price: ${self.ltc_price:.2f}")

                self.game_over = True
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                # Player stands after doubling down, dealer plays
                while hand_value(self.dealer_hand) < 17:
                    self.dealer_hand.append(self.deck.pop())

                dealer_value = hand_value(self.dealer_hand)

                # Determine winner
                if dealer_value > 21:
                    # Dealer busts, player wins (96% RTP on double down)
                    winnings = doubled_wager_ltc + (doubled_wager_ltc * 0.96)
                    balances[self.user_id]["balance"] += winnings
                    color = 0x00ff00
                    title = "🃏 Blackjack - YOU WON After Double Down! 🎉"
                    result_text = f"Dealer busted with {dealer_value}! You win ${doubled_wager_usd:.2f} USD."
                elif player_value > dealer_value:
                    # Player wins (96% RTP on double down)
                    winnings = doubled_wager_ltc + (doubled_wager_ltc * 0.96)
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
                    balances[self.user_id]["balance"] += doubled_wager_ltc
                    color = 0xffff00
                    title = "🃏 Blackjack - Push After Double Down! 🤝"
                    result_text = f"Both have {player_value} - it's a tie! Your bet is returned."

                balances[self.user_id]["wagered"] += doubled_wager_ltc
                add_rakeback(self.user_id, doubled_wager_ltc)  # Add rakeback
                save_balances(balances)
                new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price

                embed = discord.Embed(title=title, color=color)
                embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand)} = {dealer_value}", inline=True)
                embed.add_field(name="🎯 Result", value=result_text, inline=False)
                embed.add_field(name="💰 Wagered", value=f"${doubled_wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
                embed.set_footer(text=f"LTC Price: ${self.ltc_price:.2f}")

                self.game_over = True
                await interaction.response.edit_message(embed=embed, view=self)


    # Create initial embed
    embed = discord.Embed(title="🃏 Blackjack - Your Turn", color=0x0099ff)
    embed.add_field(name="🃏 Your Hand", value=f"{format_hand(player_hand)} = {player_value}", inline=True)
    embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(dealer_hand, hide_first=True)} = ?", inline=True)
    embed.add_field(name="💰 Wager", value=f"${wager_usd:.2f} USD", inline=True)
    embed.set_footer(text="Hit: take another card | Stand: keep hand | Double Down: double bet + 1 card") # Updated footer

    view = BlackjackView(player_hand, dealer_hand, deck, wager_ltc, wager_usd, ltc_price, user_id)
    await ctx.respond(embed=embed, view=view)

# MINES
@bot.slash_command(name="mines", description="Play Mines - find diamonds while avoiding mines! (in USD)")
async def mines(ctx, wager_usd: float, mine_count: discord.Option(int, "Number of mines (1-24)", min_value=1, max_value=24)):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    wager_ltc = wager_usd / ltc_price

    if balances[user_id]["balance"] < wager_ltc:
        current_balance_usd = balances[user_id]["balance"] * ltc_price
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    # Deduct the wager when starting the game
    balances[user_id]["balance"] -= wager_ltc
    balances[user_id]["wagered"] += wager_ltc
    add_rakeback(user_id, wager_ltc)  # Add rakeback
    save_balances(balances)

    # Generate mine positions (0-24 for 5x5 grid)
    mine_positions = set(random.sample(range(25), min(mine_count, 24)))

    # Calculate multipliers based on mines and diamonds found
    def get_multiplier(diamonds_found, total_mines):
        # Base multiplier increases with more mines and more diamonds found
        if diamonds_found == 0:
            return 0

        # More mines = higher risk = higher multiplier (further reduced for house edge)
        mine_multiplier = 1 + (total_mines * 0.03)

        # Each diamond found increases multiplier (further reduced for house edge)
        diamond_multiplier = 1 + (diamonds_found * 0.08)

        return round(mine_multiplier * diamond_multiplier, 2)

    class MinesView(discord.ui.View):
        def __init__(self, mine_positions, wager_ltc, wager_usd, ltc_price, user_id, mine_count):
            super().__init__(timeout=300)
            self.mine_positions = mine_positions
            self.wager_ltc = wager_ltc
            self.wager_usd = wager_usd
            self.ltc_price = ltc_price
            self.user_id = user_id
            self.mine_count = mine_count
            self.revealed_tiles = set()
            self.diamonds_found = 0
            self.game_over = False
            self.current_multiplier = 1.0

            # Create a 5x5 grid (25 tiles)
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
                        new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price

                        embed = discord.Embed(title="💣 Mines - BOOM! 💥", color=0xff0000)
                        embed.add_field(name="💎 Diamonds Found", value=str(self.diamonds_found), inline=True)
                        embed.add_field(name="💣 Mines", value=str(self.mine_count), inline=True)
                        embed.add_field(name="💸 Result", value=f"You hit a mine! Lost ${self.wager_usd:.2f} USD", inline=True)
                        embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
                        embed.set_footer(text=f"LTC Price: ${self.ltc_price:.2f}")

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
                winnings_ltc = self.wager_ltc * self.current_multiplier
                balances[self.user_id]["balance"] += winnings_ltc
                save_balances(balances)

                new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price
                winnings_usd = winnings_ltc * self.ltc_price

                embed = discord.Embed(title="💎 Mines - PERFECT GAME! 🎉", color=0xffd700)
                embed.add_field(name="💎 Diamonds Found", value=f"{self.diamonds_found}/{safe_tiles}", inline=True)
                embed.add_field(name="💣 Mines", value=str(self.mine_count), inline=True)
                embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
                embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
                embed.set_footer(text=f"LTC Price: ${self.ltc_price:.2f} • Perfect Game Bonus!")

                await interaction.response.edit_message(embed=embed, view=self)
                return

            # Update the game embed
            current_winnings_ltc = self.wager_ltc * self.current_multiplier
            current_winnings_usd = current_winnings_ltc * self.ltc_price

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
            winnings_ltc = self.wager_ltc * self.current_multiplier
            balances[self.user_id]["balance"] += winnings_ltc
            save_balances(balances)

            new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price
            winnings_usd = winnings_ltc * self.ltc_price

            embed = discord.Embed(title="💰 Mines - Cashed Out! 🎉", color=0x00ff00)
            embed.add_field(name="💎 Diamonds Found", value=str(self.diamonds_found), inline=True)
            embed.add_field(name="💣 Mines", value=str(self.mine_count), inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
            embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
            embed.set_footer(text=f"LTC Price: ${self.ltc_price:.2f} • Smart move!")

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

    view = MinesView(mine_positions, wager_ltc, wager_usd, ltc_price, user_id, mine_count)
    await ctx.respond(embed=embed, view=view)

# TOWERS
@bot.slash_command(name="towers", description="Climb towers by choosing the correct path! (in USD)")
async def towers(ctx, wager_usd: float, difficulty: discord.Option(int, "Difficulty level (2-4 paths per level)", min_value=2, max_value=4, default=3)):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    wager_ltc = wager_usd / ltc_price

    if balances[user_id]["balance"] < wager_ltc:
        current_balance_usd = balances[user_id]["balance"] * ltc_price
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    # Deduct the wager when starting the game
    balances[user_id]["balance"] -= wager_ltc
    balances[user_id]["wagered"] += wager_ltc
    add_rakeback(user_id, wager_ltc)  # Add rakeback
    save_balances(balances)

    # Generate tower structure - 8 levels, each with 'difficulty' number of paths
    # Only 1 path per level is correct
    tower_structure = []
    for level in range(8):
        correct_path = random.randint(0, difficulty - 1)
        tower_structure.append(correct_path)

    def get_tower_multiplier(level, difficulty):
        # Higher levels and higher difficulty = higher multiplier (reduced for house edge)
        base_multiplier = 1.0
        level_bonus = level * (0.2 + (difficulty - 2) * 0.05)
        return round(base_multiplier + level_bonus, 2)

    class TowersView(discord.ui.View):
        def __init__(self, tower_structure, wager_ltc, wager_usd, ltc_price, user_id, difficulty):
            super().__init__(timeout=300)
            self.tower_structure = tower_structure
            self.wager_ltc = wager_ltc
            self.wager_usd = wager_usd
            self.ltc_price = ltc_price
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
                    winnings_ltc = self.wager_ltc * final_multiplier
                    balances[self.user_id]["balance"] += winnings_ltc
                    save_balances(balances)

                    new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price
                    winnings_usd = winnings_ltc * self.ltc_price

                    embed = discord.Embed(title="🏗️ Towers - TOWER COMPLETED! 🎉", color=0xffd700)
                    embed.add_field(name="🏢 Level Reached", value="8/8 (TOP!)", inline=True)
                    embed.add_field(name="⚡ Difficulty", value=f"{self.difficulty} paths", inline=True)
                    embed.add_field(name="📈 Final Multiplier", value=f"{final_multiplier:.2f}x", inline=True)
                    embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
                    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
                    embed.set_footer(text=f"LTC Price: ${self.ltc_price:.2f} • Congratulations!")

                    self.clear_items()
                    await interaction.response.edit_message(embed=embed, view=self)
                    return
                else:
                    # Continue to next level
                    self.setup_level()

                    current_winnings_ltc = self.wager_ltc * self.current_multiplier
                    current_winnings_usd = current_winnings_ltc * self.ltc_price

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
                new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price

                embed = discord.Embed(title="🏗️ Towers - Wrong Path! ❌", color=0xff0000)
                embed.add_field(name="🏢 Level Reached", value=f"{self.current_level}/8", inline=True)
                embed.add_field(name="⚡ Difficulty", value=f"{self.difficulty} paths", inline=True)
                embed.add_field(name="🚪 Chosen Path", value=f"Path {chosen_path + 1}", inline=True)
                embed.add_field(name="✅ Correct Path", value=f"Path {correct_path + 1}", inline=True)
                embed.add_field(name="💸 Result", value=f"Lost ${self.wager_usd:.2f} USD", inline=True)
                embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
                embed.set_footer(text=f"LTC Price: ${self.ltc_price:.2f}")

                self.clear_items()
                await interaction.response.edit_message(embed=embed, view=self)

        async def cashout_callback(self, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id) or self.game_over:
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            if self.current_level == 0:
                await interaction.response.send_message("You need to climb at least one level before cashing out!", ephemeral=True)
                return

            # Cash out
            self.game_over = True
            winnings_ltc = self.wager_ltc * self.current_multiplier
            balances[self.user_id]["balance"] += winnings_ltc
            save_balances(balances)

            new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price
            winnings_usd = winnings_ltc * self.ltc_price

            embed = discord.Embed(title="💰 Towers - Cashed Out! 🎉", color=0x00ff00)
            embed.add_field(name="🏢 Level Reached", value=f"{self.current_level}/8", inline=True)
            embed.add_field(name="⚡ Difficulty", value=f"{self.difficulty} paths", inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{self.current_multiplier:.2f}x", inline=True)
            embed.add_field(name="💰 Winnings", value=f"${winnings_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
            embed.set_footer(text=f"LTC Price: ${self.ltc_price:.2f} • Smart move!")

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

    view = TowersView(tower_structure, wager_ltc, wager_usd, ltc_price, user_id, difficulty)
    await ctx.respond(embed=embed, view=view)

# PLINKO
@bot.slash_command(name="plinko", description="Drop a ball down the Plinko board for multipliers! (in USD)")
async def plinko(ctx, wager_usd: float, risk: discord.Option(str, "Risk level", choices=["low", "medium", "high"], default="medium"), rows: discord.Option(int, "Number of rows (8-16)", min_value=8, max_value=16, default=12)):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    wager_ltc = wager_usd / ltc_price

    if balances[user_id]["balance"] < wager_ltc:
        current_balance_usd = balances[user_id]["balance"] * ltc_price
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    # Calculate number of slots based on rows (rows + 1 slots)
    num_slots = rows + 1

    # Define multiplier patterns for different risk levels based on number of slots
    def generate_multipliers(risk_level, slots):
        if risk_level == "low":
            # Low risk: more consistent, smaller multipliers
            center = slots // 2
            mults = []
            for i in range(slots):
                distance = abs(i - center)
                if distance == 0:
                    mults.append(1.5)
                elif distance <= 1:
                    mults.append(1.2)
                elif distance <= 2:
                    mults.append(1.0)
                elif distance <= 3:
                    mults.append(0.8)
                else:
                    mults.append(0.5)
            return mults
        elif risk_level == "medium":
            # Medium risk: balanced
            edge_multiplier = min(100, slots * 8)
            center = slots // 2
            mults = []
            for i in range(slots):
                distance = abs(i - center)
                if distance >= slots // 2:
                    mults.append(edge_multiplier)
                elif distance >= slots // 3:
                    mults.append(max(2, slots // 2))
                elif distance >= 2:
                    mults.append(max(1, distance))
                else:
                    mults.append(0.2)
            return mults
        else:  # high risk
            # High risk: extreme multipliers
            edge_multiplier = min(1000, slots * 15)
            center = slots // 2
            mults = []
            for i in range(slots):
                distance = abs(i - center)
                if distance >= slots // 2:
                    mults.append(edge_multiplier)
                elif distance >= slots // 3:
                    mults.append(max(10, slots))
                elif distance >= 2:
                    mults.append(max(2, distance * 2))
                elif distance == 1:
                    mults.append(0.5)
                else:
                    mults.append(0.1)
            return mults

    multipliers = generate_multipliers(risk, num_slots)

    # Create weighted probabilities (center slots more likely)
    weights = []
    center = num_slots // 2
    for i in range(num_slots):
        distance = abs(i - center)
        weight = max(1, 10 - distance)
        weights.append(weight)

    # Choose random slot based on weights
    slot = random.choices(range(num_slots), weights=weights)[0]
    multiplier = multipliers[slot]

    # Simulate ball path for animation
    ball_path = [rows // 2]  # Start at center of top row
    for row in range(rows):
        current_pos = ball_path[-1]
        # Ball can move left or right, but stay within bounds
        if current_pos <= 0:
            next_pos = random.choice([0, 1])
        elif current_pos >= row:
            next_pos = random.choice([row, row + 1])
        else:
            next_pos = random.choice([current_pos, current_pos + 1])
        ball_path.append(next_pos)

    # Final position should match our calculated slot
    ball_path[-1] = slot

    class PlinkoAnimationView(discord.ui.View):
        def __init__(self, ball_path, multipliers, rows, num_slots, wager_ltc, wager_usd, ltc_price, user_id, risk):
            super().__init__(timeout=60)
            self.ball_path = ball_path
            self.multipliers = multipliers
            self.rows = rows
            self.num_slots = num_slots
            self.wager_ltc = wager_ltc
            self.wager_usd = wager_usd
            self.ltc_price = ltc_price
            self.user_id = user_id
            self.risk = risk
            self.current_row = 0
            self.animation_complete = False

        def create_board_visual(self, current_row, ball_position):
            board = "```\n🏀 PLINKO TRIANGLE\n\n"

            # Create triangle plinko board
            for row in range(self.rows + 1):
                line = ""
                pegs_in_row = row + 1
                leading_spaces = " " * (self.rows - row + 2)  # Extra padding for better centering

                if row == 0:
                    # Top row - single peg with ball drop point
                    if current_row == 0:
                        line = leading_spaces + "🏀"
                    else:
                        line = leading_spaces + "●"
                elif row < current_row and row < len(self.ball_path):
                    # Past rows - show only pegs (ball has passed)
                    line = leading_spaces + " ".join("●" for _ in range(pegs_in_row))
                elif row == current_row and row < len(self.ball_path):
                    # Current row - replace the peg at ball position with ball
                    line = leading_spaces
                    for pos in range(pegs_in_row):
                        if pos == self.ball_path[row]:
                            line += "🏀"  # Ball replaces the peg
                        else:
                            line += "●"  # Normal peg
                        if pos < pegs_in_row - 1:
                            line += " "
                else:
                    # Future rows - just show pegs structure
                    line = leading_spaces + " ".join("●" for _ in range(pegs_in_row))

                board += line + "\n"

            # Add multiplier slots at bottom (properly centered)
            board += "\n"
            # Center the multipliers under the triangle
            multiplier_padding = " " * 2
            slot_line = multiplier_padding
            for i, mult in enumerate(self.multipliers):
                mult_str = f"{mult}x"
                if len(mult_str) < 4:  # Pad shorter multipliers
                    mult_str = mult_str.center(4)

                if i == self.ball_path[-1] and self.animation_complete:
                    slot_line += f"[{mult_str}]"
                else:
                    slot_line += f" {mult_str} "

            board += slot_line + "\n```"
            return board

        @discord.ui.button(label="Drop Ball!", style=discord.ButtonStyle.primary, emoji="🏀")
        async def drop_ball(self, button: discord.ui.Button, interaction: discord.Interaction):
            if interaction.user.id != int(self.user_id):
                await interaction.response.send_message("This is not your game!", ephemeral=True)
                return

            button.disabled = True

            # Animate the ball dropping
            for row in range(self.rows + 1):
                self.current_row = row

                embed = discord.Embed(title="🏀 Plinko - Ball Dropping!", color=0x0099ff)
                embed.add_field(name="💰 Wager", value=f"${self.wager_usd:.2f} USD", inline=True)
                embed.add_field(name="🎲 Risk Level", value=self.risk.title(), inline=True)
                embed.add_field(name="📏 Rows", value=f"{self.rows}", inline=True)
                embed.add_field(name="🎯 Current Row", value=f"{row}/{self.rows}", inline=True)

                board_visual = self.create_board_visual(row, self.ball_path[row] if row < len(self.ball_path) else 0)
                embed.add_field(name="🏀 Plinko Board", value=board_visual, inline=False)
                embed.set_footer(text="Ball is dropping...")

                if row == 0:
                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    await interaction.edit_original_response(embed=embed, view=self)
                await asyncio.sleep(0.8)  # Animation delay

            # Animation complete, show final result
            self.animation_complete = True
            final_slot = self.ball_path[-1]
            final_multiplier = self.multipliers[final_slot]

            # Calculate winnings
            if final_multiplier >= 1.0:
                winnings_ltc = self.wager_ltc * final_multiplier
                balances[self.user_id]["balance"] += winnings_ltc
                new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price
                profit_ltc = winnings_ltc - self.wager_ltc
                profit_usd = profit_ltc * self.ltc_price
                color = 0x00ff00
                title = "🏀 Plinko - YOU WON! 🎉"
                result_text = f"Ball landed in slot {final_slot + 1} with {final_multiplier}x multiplier!\nProfit: ${profit_usd:.2f} USD"
            else:
                loss_ltc = self.wager_ltc - (self.wager_ltc * final_multiplier)
                balances[self.user_id]["balance"] -= loss_ltc
                new_balance_usd = balances[self.user_id]["balance"] * self.ltc_price
                loss_usd = loss_ltc * self.ltc_price
                color = 0xff0000
                title = "🏀 Plinko - Partial Loss 😔"
                result_text = f"Ball landed in slot {final_slot + 1} with {final_multiplier}x multiplier.\nLoss: ${loss_usd:.2f} USD"

            balances[self.user_id]["wagered"] += self.wager_ltc
            add_rakeback(self.user_id, self.wager_ltc)  # Add rakeback
            save_balances(balances)

            embed = discord.Embed(title=title, color=color)
            embed.add_field(name="🎯 Result", value=result_text, inline=False)
            embed.add_field(name="🎲 Risk Level", value=self.risk.title(), inline=True)
            embed.add_field(name="📏 Rows", value=f"{self.rows}", inline=True)
            embed.add_field(name="📍 Final Slot", value=f"{final_slot + 1}/{self.num_slots}", inline=True)
            embed.add_field(name="📈 Multiplier", value=f"{final_multiplier}x", inline=True)
            embed.add_field(name="💰 Wagered", value=f"${self.wager_usd:.2f} USD", inline=True)
            embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

            final_board = self.create_board_visual(self.rows, final_slot)
            embed.add_field(name="🏀 Final Board", value=final_board, inline=False)
            embed.set_footer(text=f"LTC Price: ${self.ltc_price:.2f}")

            self.clear_items()
            await interaction.edit_original_response(embed=embed, view=self)

    # Deduct wager
    balances[user_id]["balance"] -= wager_ltc
    save_balances(balances)

    # Create initial embed
    embed = discord.Embed(title="🏀 Plinko - Ready to Drop!", color=0x0099ff)
    embed.add_field(name="💰 Wager", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="🎲 Risk Level", value=risk.title(), inline=True)
    embed.add_field(name="📏 Rows", value=f"{rows}", inline=True)
    embed.add_field(name="🎯 Slots", value=f"{num_slots}", inline=True)

    # Show multiplier preview
    mult_preview = " ".join(f"{mult}x" for mult in multipliers[:8])
    if len(multipliers) > 8:
        mult_preview += "..."
    embed.add_field(name="📈 Multipliers", value=mult_preview, inline=True)
    embed.add_field(name="🎮 Instructions", value="Click 'Drop Ball!' to start the animation!", inline=False)
    embed.set_footer(text=f"LTC Price: ${ltc_price:.2f} • Higher risk = higher potential rewards!")

    view = PlinkoAnimationView(ball_path, multipliers, rows, num_slots, wager_ltc, wager_usd, ltc_price, user_id, risk)
    await ctx.respond(embed=embed, view=view)

# KENO
@bot.slash_command(name="keno", description="Pick numbers and see how many match! (in USD)")
async def keno(ctx, wager_usd: float, numbers: str):
    user_id = str(ctx.author.id)
    init_user(user_id)

    # Get current LTC price
    ltc_price = await get_ltc_to_usd()
    wager_ltc = wager_usd / ltc_price

    if balances[user_id]["balance"] < wager_ltc:
        current_balance_usd = balances[user_id]["balance"] * ltc_price
        await ctx.respond(f"❌ You don't have enough balance! You have ${current_balance_usd:.2f} USD but tried to wager ${wager_usd:.2f} USD.")
        return

    # Parse user numbers
    try:
        user_numbers = [int(x.strip()) for x in numbers.split(',')]
        user_numbers = list(set(user_numbers))  # Remove duplicates

        # Validate numbers
        if not all(1 <= num <= 40 for num in user_numbers):
            await ctx.respond("❌ Numbers must be between 1 and 40!", ephemeral=True)
            return

        if len(user_numbers) < 1 or len(user_numbers) > 10:
            await ctx.respond("❌ You must pick between 1 and 10 numbers!", ephemeral=True)
            return

    except ValueError:
        await ctx.respond("❌ Invalid format! Use: `/keno 5.00 1,5,10,15,20`", ephemeral=True)
        return

    # Generate 20 random winning numbers from 1-40
    winning_numbers = random.sample(range(1, 41), 20)

    # Find matches
    matches = set(user_numbers) & set(winning_numbers)
    match_count = len(matches)

    # Keno payout table based on numbers picked and matches (reduced for house edge)
    payout_table = {
        1: {1: 2.5},
        2: {2: 10.0},
        3: {2: 0.8, 3: 35.0},
        4: {2: 0.8, 3: 3.0, 4: 85.0},
        5: {3: 0.8, 4: 9.0, 5: 600.0},
        6: {3: 0.8, 4: 2.5, 5: 28.0, 6: 1200.0},
        7: {3: 0.4, 4: 0.8, 5: 5.0, 6: 150.0, 7: 5000.0},
        8: {4: 1.5, 5: 9.0, 6: 75.0, 7: 1200.0, 8: 7500.0},
        9: {4: 0.8, 5: 3.0, 6: 35.0, 7: 250.0, 8: 3500.0, 9: 7500.0},
        10: {5: 1.5, 6: 18.0, 7: 100.0, 8: 750.0, 9: 3200.0, 10: 7500.0}
    }

    numbers_picked = len(user_numbers)
    multiplier = payout_table.get(numbers_picked, {}).get(match_count, 0.0)

    if multiplier > 0:
        # Player wins
        winnings_ltc = wager_ltc * multiplier
        balances[user_id]["balance"] += winnings_ltc
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        profit_ltc = winnings_ltc - wager_ltc
        profit_usd = profit_ltc * ltc_price
        color = 0x00ff00
        title = "🎱 Keno - YOU WON! 🎉"
        result_text = f"You matched {match_count} out of {numbers_picked} numbers!\nProfit: ${profit_usd:.2f} USD"
    else:
        # Player loses
        balances[user_id]["balance"] -= wager_ltc
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0xff0000
        title = "🎱 Keno - No Win 😔"
        result_text = f"You matched {match_count} out of {numbers_picked} numbers.\nNot enough matches for a payout."

    balances[user_id]["wagered"] += wager_ltc
    add_rakeback(user_id, wager_ltc)  # Add rakeback
    save_balances(balances)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="🔢 Your Numbers", value=', '.join(map(str, sorted(user_numbers))), inline=True)
    embed.add_field(name="✅ Matches", value=', '.join(map(str, sorted(matches))) if matches else "None", inline=True)
    embed.add_field(name="🎲 Match Count", value=f"{match_count}/{numbers_picked}", inline=True)

    if multiplier > 0:
        embed.add_field(name="📈 Multiplier", value=f"{multiplier}x", inline=True)

    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)

    # Show some winning numbers
    winning_display = ', '.join(map(str, sorted(winning_numbers[:10]))) + f"... (+{len(winning_numbers)-10} more)"
    embed.add_field(name="🏆 Winning Numbers", value=winning_display, inline=False)
    embed.set_footer(text=f"LTC Price: ${ltc_price:.2f} • Pick 1-10 numbers from 1-40")

    await ctx.respond(embed=embed)

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
