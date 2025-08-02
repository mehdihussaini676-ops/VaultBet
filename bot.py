import discord
from discord.ext import commands
from discord.commands import slash_command, option
import os
import random
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

intents = discord.Intents.default()
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

balances = load_balances()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.sync_commands()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# BALANCE
@slash_command(name="balance", description="Check your LTC balance")
async def balance(ctx):
    user_id = str(ctx.author.id)
    user_balance = balances.get(user_id, {}).get("balance", 0.0)
    await ctx.respond(f"Your balance is {user_balance:.8f} LTC")

# ADMIN: ADD BALANCE
@slash_command(name="addbalance", description="Admin command to add balance to a user")
@option("member", description="User to add balance to", input_type=discord.Member)
@option("amount", description="Amount to add", input_type=float)
async def addbalance(ctx, member: discord.Member, amount: float):
    if ctx.author.id != ADMIN_ID:
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        return

    user_id = str(member.id)
    if user_id not in balances:
        balances[user_id] = {"balance": 0.0, "deposited": 0.0, "withdrawn": 0.0, "wagered": 0.0}
    balances[user_id]["balance"] += amount
    balances[user_id]["deposited"] += amount
    save_balances(balances)
    await ctx.respond(f"Added {amount:.8f} LTC to {member.display_name}'s balance.")

# COINFLIP
@slash_command(name="coinflip", description="Flip a coin to win or lose your wager")
@option("wager", description="Amount to wager", input_type=float)
async def coinflip(ctx, wager: float):
    user_id = str(ctx.author.id)
    if user_id not in balances or balances[user_id].get("balance", 0.0) < wager:
        await ctx.respond("You don't have enough balance to wager this amount.")
        return

    result = random.choice(["win", "lose"])
    if result == "win":
        balances[user_id]["balance"] += wager
        outcome = f"You won! Your new balance is {balances[user_id]['balance']:.8f} LTC"
    else:
        balances[user_id]["balance"] -= wager
        outcome = f"You lost! Your new balance is {balances[user_id]['balance']:.8f} LTC"

    balances[user_id]["wagered"] += wager
    save_balances(balances)
    await ctx.respond(outcome)

# DICE
@slash_command(name="dice", description="Roll a dice and win if it’s over 3")
@option("wager", description="Amount to wager", input_type=float)
async def dice(ctx, wager: float):
    user_id = str(ctx.author.id)
    if user_id not in balances or balances[user_id].get("balance", 0.0) < wager:
        await ctx.respond("You don't have enough balance to wager this amount.")
        return

    roll = random.randint(1, 6)
    if roll > 3:
        balances[user_id]["balance"] += wager
        result = f"🎲 You rolled a {roll} and won! New balance: {balances[user_id]['balance']:.8f} LTC"
    else:
        balances[user_id]["balance"] -= wager
        result = f"🎲 You rolled a {roll} and lost. New balance: {balances[user_id]['balance']:.8f} LTC"

    balances[user_id]["wagered"] += wager
    save_balances(balances)
    await ctx.respond(result)

# ROCK PAPER SCISSORS
@slash_command(name="rps", description="Play Rock Paper Scissors")
@option("choice", description="Your choice", choices=["rock", "paper", "scissors"])
@option("wager", description="Amount to wager", input_type=float)
async def rps(ctx, choice: str, wager: float):
    user_id = str(ctx.author.id)
    if user_id not in balances or balances[user_id].get("balance", 0.0) < wager:
        await ctx.respond("You don't have enough balance to wager this amount.")
        return

    choices = ["rock", "paper", "scissors"]
    bot_choice = random.choice(choices)

    win_map = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    if bot_choice == choice:
        result = f"It's a tie! You both chose {choice}."
    elif win_map[choice] == bot_choice:
        balances[user_id]["balance"] += wager
        result = f"You won! {choice} beats {bot_choice}. New balance: {balances[user_id]['balance']:.8f} LTC"
    else:
        balances[user_id]["balance"] -= wager
        result = f"You lost! {bot_choice} beats {choice}. New balance: {balances[user_id]['balance']:.8f} LTC"

    balances[user_id]["wagered"] += wager
    save_balances(balances)
    await ctx.respond(result)

# SLOTS
@slash_command(name="slots", description="Spin the slot machine!")
@option("wager", description="Amount to wager", input_type=float)
async def slots(ctx, wager: float):
    user_id = str(ctx.author.id)
    if user_id not in balances or balances[user_id]["balance"] < wager:
        await ctx.respond("You don't have enough balance to wager this amount.")
        return

    symbols = ["🍒", "🍋", "🍊", "🔔", "⭐"]
    result = [random.choice(symbols) for _ in range(3)]

    if len(set(result)) == 1:
        winnings = wager * 5
        balances[user_id]["balance"] += winnings
        msg = f"🎰 {' '.join(result)} — JACKPOT! You won {winnings:.8f} LTC"
    elif len(set(result)) == 2:
        winnings = wager * 2
        balances[user_id]["balance"] += winnings
        msg = f"🎰 {' '.join(result)} — Nice! You won {winnings:.8f} LTC"
    else:
        balances[user_id]["balance"] -= wager
        msg = f"🎰 {' '.join(result)} — You lost {wager:.8f} LTC"

    balances[user_id]["wagered"] += wager
    save_balances(balances)
    await ctx.respond(msg)

bot.run(TOKEN)
