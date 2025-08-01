import discord
from discord.ext import commands
from discord import app_commands
import os
import random
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

BALANCE_FILE = "balances.json"

def load_balances():
    if not os.path.exists(BALANCE_FILE):
        return {}
    with open(BALANCE_FILE, "r") as f:
        return json.load(f)

def save_balances(balances):
    with open(BALANCE_FILE, "w") as f:
        json.dump(balances, f, indent=4)

balances = load_balances()

def ensure_user(user_id):
    if user_id not in balances:
        balances[user_id] = {
            "balance": 0.0,
            "deposited": 0.0,
            "withdrawn": 0.0,
            "wagered": 0.0
        }

@bot.event
async def on_ready():
    try:
        await tree.sync()
        print("Synced slash commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print(f"Logged in as {bot.user}")

@tree.command(name="balance", description="Check your LTC balance and stats")
async def balance(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    ensure_user(user_id)
    user = balances[user_id]
    msg = (f"💰 **Balance**: {user['balance']:.8f} LTC\n"
           f"📥 **Deposited**: {user['deposited']:.8f} LTC\n"
           f"📤 **Withdrawn**: {user['withdrawn']:.8f} LTC\n"
           f"🎲 **Wagered**: {user['wagered']:.8f} LTC\n"
           f"📊 **Profit/Loss**: {(user['balance'] + user['withdrawn'] - user['deposited']):.8f} LTC")
    await interaction.response.send_message(msg)

@tree.command(name="addbalance", description="Admin: Add LTC to a user's balance")
@app_commands.describe(user="The user to credit", amount="Amount to add")
async def addbalance(interaction: discord.Interaction, user: discord.User, amount: float):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("🚫 You don't have permission.", ephemeral=True)
        return
    user_id = str(user.id)
    ensure_user(user_id)
    balances[user_id]["balance"] += amount
    balances[user_id]["deposited"] += amount
    save_balances(balances)
    await interaction.response.send_message(f"✅ Added {amount:.8f} LTC to {user.mention}")

@tree.command(name="coinflip", description="Wager on a coin flip")
@app_commands.describe(amount="Amount to wager")
async def coinflip(interaction: discord.Interaction, amount: float):
    user_id = str(interaction.user.id)
    ensure_user(user_id)
    if balances[user_id]["balance"] < amount:
        await interaction.response.send_message("Insufficient balance.")
        return

    result = random.choice(["win", "lose"])
    if result == "win":
        balances[user_id]["balance"] += amount
        msg = f"🪙 Heads! You won {amount:.8f} LTC"
    else:
        balances[user_id]["balance"] -= amount
        msg = f"🪙 Tails! You lost {amount:.8f} LTC"

    balances[user_id]["wagered"] += amount
    save_balances(balances)
    await interaction.response.send_message(msg)

@tree.command(name="roulette", description="Bet on red, black, or green")
@app_commands.describe(color="Choose red, black or green", amount="Amount to wager")
async def roulette(interaction: discord.Interaction, color: str, amount: float):
    user_id = str(interaction.user.id)
    ensure_user(user_id)
    if balances[user_id]["balance"] < amount:
        await interaction.response.send_message("Not enough balance.")
        return

    valid_colors = ["red", "black", "green"]
    if color.lower() not in valid_colors:
        await interaction.response.send_message("Choose red, black, or green.")
        return

    result = random.choices(["red", "black", "green"], weights=[47.5, 47.5, 5])[0]
    payout = 0
    if color == result:
        payout = 2 if result in ["red", "black"] else 14
        win_amt = amount * payout
        balances[user_id]["balance"] += win_amt
        msg = f"🎯 It landed on {result}! You won {win_amt:.8f} LTC"
    else:
        balances[user_id]["balance"] -= amount
        msg = f"🎯 It landed on {result}. You lost {amount:.8f} LTC"

    balances[user_id]["wagered"] += amount
    save_balances(balances)
    await interaction.response.send_message(msg)

bot.run(TOKEN)