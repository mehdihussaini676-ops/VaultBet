import discord
from discord.ext import commands
import os
import random
import json
import aiohttp
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

# Initialize user
def init_user(user_id):
    if user_id not in balances:
        balances[user_id] = {"balance": 0.0, "deposited": 0.0, "withdrawn": 0.0, "wagered": 0.0}

# Check if user is admin
def is_admin(user_id):
    return user_id in ADMIN_IDS

balances = load_balances()
withdraw_queue = load_withdraw_queue()

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
        balances[user_id]["balance"] += wager_ltc
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
        balances[user_id]["balance"] += wager_ltc
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
        # Player wins
        balances[user_id]["balance"] += wager_ltc
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
        # JACKPOT - all 3 match
        multiplier = 5
        winnings_ltc = wager_ltc * multiplier
        balances[user_id]["balance"] += winnings_ltc
        winnings_usd = winnings_ltc * ltc_price
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0xffd700  # Gold
        title = "🎰 JACKPOT! 💰🎉"
        result_text = f"**{result_display}**\n\nAll three match! You won **${winnings_usd:.2f} USD** (5x multiplier)!"
    elif len(set(result)) == 2:
        # Two symbols match
        multiplier = 2
        winnings_ltc = wager_ltc * multiplier
        balances[user_id]["balance"] += winnings_ltc
        winnings_usd = winnings_ltc * ltc_price
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0x00ff00
        title = "🎰 Nice Win! 🎉"
        result_text = f"**{result_display}**\n\nTwo symbols match! You won **${winnings_usd:.2f} USD** (2x multiplier)!"
    else:
        # No match - player loses
        balances[user_id]["balance"] -= wager_ltc
        new_balance_usd = balances[user_id]["balance"] * ltc_price
        color = 0xff0000
        title = "🎰 No Match 😔"
        result_text = f"**{result_display}**\n\nNo symbols match. You lost **${wager_usd:.2f} USD**."

    balances[user_id]["wagered"] += wager_ltc
    save_balances(balances)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="🎯 Result", value=result_text, inline=False)
    embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
    embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
    embed.set_footer(text=f"LTC Price: ${ltc_price:.2f} • Jackpot: 5x | Two Match: 2x")

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
            # Push - no money changes
            new_balance_usd = balances[user_id]["balance"] * ltc_price
            color = 0xffff00
            title = "🃏 Blackjack - Push! 🤝"
            result_text = "Both you and the dealer have Blackjack!"
        elif player_blackjack:
            # Player wins with blackjack (1.5x payout)
            winnings_ltc = wager_ltc * 1.5
            balances[user_id]["balance"] += winnings_ltc
            new_balance_usd = balances[user_id]["balance"] * ltc_price
            winnings_usd = winnings_ltc * ltc_price
            color = 0x00ff00
            title = "🃏 BLACKJACK! 🎉"
            result_text = f"You got Blackjack! Won ${winnings_usd:.2f} USD (1.5x payout)!"
        else:
            # Dealer has blackjack, player loses
            balances[user_id]["balance"] -= wager_ltc
            new_balance_usd = balances[user_id]["balance"] * ltc_price
            color = 0xff0000
            title = "🃏 Blackjack - Dealer Wins 😔"
            result_text = "Dealer has Blackjack!"

        balances[user_id]["wagered"] += wager_ltc
        save_balances(balances)

        embed = discord.Embed(title=title, color=color)
        embed.add_field(name="🃏 Your Hand", value=f"{format_hand(player_hand)} = {player_value}", inline=True)
        embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(dealer_hand)} = {dealer_value}", inline=True)
        embed.add_field(name="🎯 Result", value=result_text, inline=False)
        embed.add_field(name="💰 Wagered", value=f"${wager_usd:.2f} USD", inline=True)
        embed.add_field(name="💳 New Balance", value=f"${new_balance_usd:.2f} USD", inline=True)
        embed.set_footer(text=f"LTC Price: ${ltc_price:.2f} • Blackjack pays 1.5x")

        await ctx.respond(embed=embed)
        return

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
            self.clear_items() # Remove buttons to prevent further interaction after hit/stand/double down

            if player_value > 21:
                # Player busts
                balances[self.user_id]["balance"] -= self.wager_ltc
                balances[self.user_id]["wagered"] += self.wager_ltc
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
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                # Update the embed with new hand
                embed = discord.Embed(title="🃏 Blackjack - Your Turn", color=0x0099ff)
                embed.add_field(name="🃏 Your Hand", value=f"{format_hand(self.player_hand)} = {player_value}", inline=True)
                embed.add_field(name="🤖 Dealer Hand", value=f"{format_hand(self.dealer_hand, hide_first=True)} = ?", inline=True)
                embed.add_field(name="💰 Wager", value=f"${self.wager_usd:.2f} USD", inline=True)
                embed.set_footer(text="Hit: take another card | Stand: keep hand | Double Down: double bet + 1 card") # Updated footer

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
                # Dealer busts, player wins
                balances[self.user_id]["balance"] += self.wager_ltc
                color = 0x00ff00
                title = "🃏 Blackjack - YOU WON! 🎉"
                result_text = f"Dealer busted with {dealer_value}!"
            elif player_value > dealer_value:
                # Player wins
                balances[self.user_id]["balance"] += self.wager_ltc
                color = 0x00ff00
                title = "🃏 Blackjack - YOU WON! 🎉"
                result_text = f"Your {player_value} beats dealer's {dealer_value}!"
            elif dealer_value > player_value:
                # Dealer wins
                balances[self.user_id]["balance"] -= self.wager_ltc
                color = 0xff0000
                title = "🃏 Blackjack - Dealer Wins 😔"
                result_text = f"Dealer's {dealer_value} beats your {player_value}."
            else:
                # Push - no money changes
                color = 0xffff00
                title = "🃏 Blackjack - Push! 🤝"
                result_text = f"Both have {player_value} - it's a tie!"

            balances[self.user_id]["wagered"] += self.wager_ltc
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

            if balances[self.user_id]["balance"] < self.wager_ltc:
                await interaction.response.send_message("You don't have enough balance to double down!", ephemeral=True)
                return

            # Player doubles down
            doubled_wager_ltc = self.wager_ltc * 2
            doubled_wager_usd = self.wager_usd * 2

            balances[self.user_id]["balance"] -= self.wager_ltc # Remove the original wager
            self.player_hand.append(self.deck.pop())
            player_value = hand_value(self.player_hand)

            # Player hit only once, now dealer plays
            self.can_double_down = False # Prevent further double downs
            self.clear_items() # Remove buttons

            if player_value > 21:
                # Player busts after doubling down
                balances[self.user_id]["balance"] -= doubled_wager_ltc # Lose the doubled bet
                balances[self.user_id]["wagered"] += doubled_wager_ltc
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
                    # Dealer busts, player wins
                    balances[self.user_id]["balance"] += doubled_wager_ltc
                    color = 0x00ff00
                    title = "🃏 Blackjack - YOU WON After Double Down! 🎉"
                    result_text = f"Dealer busted with {dealer_value}! You win ${doubled_wager_usd:.2f} USD."
                elif player_value > dealer_value:
                    # Player wins
                    balances[self.user_id]["balance"] += doubled_wager_ltc
                    color = 0x00ff00
                    title = "🃏 Blackjack - YOU WON After Double Down! 🎉"
                    result_text = f"Your {player_value} beats dealer's {dealer_value}! You win ${doubled_wager_usd:.2f} USD."
                elif dealer_value > player_value:
                    # Dealer wins
                    balances[self.user_id]["balance"] -= doubled_wager_ltc
                    color = 0xff0000
                    title = "🃏 Blackjack - Dealer Wins After Double Down 😔"
                    result_text = f"Dealer's {dealer_value} beats your {player_value}! You lose ${doubled_wager_usd:.2f} USD."
                else:
                    # Push - no money changes
                    color = 0xffff00
                    title = "🃏 Blackjack - Push After Double Down! 🤝"
                    result_text = f"Both have {player_value} - it's a tie! Your bet is returned."

                balances[self.user_id]["wagered"] += doubled_wager_ltc
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
