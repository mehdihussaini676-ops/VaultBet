import discord
from discord import option
from discord.ext import commands
import os
import random
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

# Load balances from file
def load_balances():
    if not os.path.exists("balances.json"):
        return {}
    with open("balances.json", "r") as f:
        return json.load(f)

# Save balances to file
def save_balances(balances):
    with open("balances.json", "w") as f:
        json.dump(balances, f)

balances = load_balances()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.sync_commands()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.slash_command(description="Check your LTC balance")
async def balance(ctx):
    user_id = str(ctx.author.id)
    user_balance = balances.get(user_id, {}).get("balance", 0.0)
    await ctx.respond(f"Your balance is {user_balance:.8f} LTC")

@bot.slash_command(description="Admin command to add balance to a user")
@option("member", description="User to add balance to")
@option("amount", description="Amount to add", min_value=0.00000001)
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

@bot.slash_command(description="Flip a coin to win or lose your wager")
@option("wager", description="Amount to wager", min_value=0.00000001)
async def coinflip(ctx, wager: float):
    user_id = str(ctx.author.id)
    if user_id not in balances or balances[user_id].get("balance", 0.0) < wager:
        await ctx.respond("You don't have enough balance to wager this amount.")
        return

    result = random.choice(["win", "lose"])
    if result == "win":
        balances[user_id]["balance"] += wager
        outcome = f"You won! New balance: {balances[user_id]['balance']:.8f} LTC"
    else:
        balances[user_id]["balance"] -= wager
        outcome = f"You lost! New balance: {balances[user_id]['balance']:.8f} LTC"

    balances[user_id]["wagered"] += wager
    save_balances(balances)
    await ctx.respond(outcome)

@bot.slash_command(description="Roll a dice. Win if you roll 4 or higher!")
@option("wager", description="Amount to wager", min_value=0.00000001)
async def dice(ctx, wager: float):
    user_id = str(ctx.author.id)
    if user_id not in balances or balances[user_id]["balance"] < wager:
        await ctx.respond("You don't have enough balance.")
        return

    roll = random.randint(1, 6)
    if roll >= 4:
        balances[user_id]["balance"] += wager
        result = f"You rolled a {roll} and won!"
    else:
        balances[user_id]["balance"] -= wager
        result = f"You rolled a {roll} and lost."

    balances[user_id]["wagered"] += wager
    save_balances(balances)
    await ctx.respond(f"{result} Your new balance: {balances[user_id]['balance']:.8f} LTC")

@bot.slash_command(description="Withdraw LTC from your account (simulated)")
@option("amount", description="Amount to withdraw", min_value=0.00000001)
async def withdraw(ctx, amount: float):
    user_id = str(ctx.author.id)
    if user_id not in balances or balances[user_id]["balance"] < amount:
        await ctx.respond("You don't have enough balance.")
        return

    balances[user_id]["balance"] -= amount
    balances[user_id]["withdrawn"] += amount
    save_balances(balances)
    await ctx.respond(f"Withdrew {amount:.8f} LTC. New balance: {balances[user_id]['balance']:.8f} LTC")

@bot.slash_command(description="View your full gambling stats")
async def stats(ctx):
    user_id = str(ctx.author.id)
    stats = balances.get(user_id)
    if not stats:
        await ctx.respond("You have no stats yet.")
        return

    msg = (
        f"**Your Stats:**\n"
        f"> 💰 Balance: `{stats['balance']:.8f} LTC`\n"
        f"> 📥 Deposited: `{stats['deposited']:.8f} LTC`\n"
        f"> 📤 Withdrawn: `{stats['withdrawn']:.8f} LTC`\n"
        f"> 🎲 Wagered: `{stats['wagered']:.8f} LTC`"
    )
    await ctx.respond(msg)

@bot.slash_command(description="List all available commands")
async def help(ctx):
    cmds = [
        "/balance - Check your LTC balance",
        "/addbalance - Admin command to add LTC",
        "/coinflip - Flip a coin and wager LTC",
        "/dice - Roll a die, win if 4+",
        "/withdraw - Simulate a withdrawal",
        "/stats - View your lifetime gambling stats",
    ]
    await ctx.respond("**Available Commands:**\n" + "\n".join(cmds))

bot.run(TOKEN)
