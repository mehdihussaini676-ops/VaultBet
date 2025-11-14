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
