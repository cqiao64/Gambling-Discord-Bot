import os
import random
import aiosqlite
import discord
import asyncio
from dotenv import load_dotenv
from discord.ext import commands
from discord import Intents
from discord.ext.commands import BucketType, cooldown, CommandOnCooldown
from datetime import datetime, timedelta
from collections import defaultdict

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = Intents.all()
intents.typing = False
intents.presences = False

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

async def get_user_score(user_id: int):
    async with aiosqlite.connect('leaderboard.db') as db:
        cursor = await db.execute('SELECT score FROM scores WHERE user_id = ?', (user_id,))
        result = await cursor.fetchone()
        await cursor.close()
        return result[0] if result else None

async def update_user_score(user_id: int, new_score: int):
    async with aiosqlite.connect('leaderboard.db') as db:
        await db.execute('INSERT OR REPLACE INTO scores (user_id, score) VALUES (?, ?)', (user_id, new_score))
        await db.commit()

async def get_balance(user_id: int):
    async with aiosqlite.connect('leaderboard.db') as db:
        cursor = await db.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
        result = await cursor.fetchone()
        await cursor.close()
        return result[0] if result else None

async def add_balance(user_id: int, amount: int):
    async with aiosqlite.connect('leaderboard.db') as db:
        current_balance = await get_balance(user_id) or 0
        await db.execute('INSERT OR REPLACE INTO balances (user_id, balance) VALUES (?, ?)', (user_id, current_balance + amount))
        await db.commit()

async def subtract_balance(user_id: int, amount: int):
    async with aiosqlite.connect('leaderboard.db') as db:
        current_balance = await get_balance(user_id) or 0
        await db.execute('INSERT OR REPLACE INTO balances (user_id, balance) VALUES (?, ?)', (user_id, current_balance - amount))
        await db.commit()

async def create_tables():
    async with aiosqlite.connect('leaderboard.db') as db:
        await db.execute('CREATE TABLE IF NOT EXISTS scores (user_id INTEGER PRIMARY KEY, score INTEGER)')
        await db.execute('CREATE TABLE IF NOT EXISTS balances (user_id INTEGER PRIMARY KEY, balance INTEGER)')
        await db.commit()

@bot.event
async def on_ready():
    await create_tables()
    print(f'{bot.user.name} has connected to Discord!')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandOnCooldown):
        seconds_left = int(error.retry_after)
        minutes, seconds = divmod(seconds_left, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        if days > 0:
            remaining_time = f'{days}d {hours}h {minutes}m {seconds}s'
        elif hours > 0:
            remaining_time = f'{hours}h {minutes}m {seconds}s'
        elif minutes > 0:
            remaining_time = f'{minutes}m {seconds}s'
        else:
            remaining_time = f'{seconds}s'

        await ctx.send(f'{ctx.author.mention}, you can use this command again in {remaining_time}.')
    else:
        raise error


@bot.command(name='slots', help='Play the slot machine')
async def slots(ctx, wager: int = None):
    if wager is None:
        await ctx.send(f"{ctx.author.mention}, please specify a wager! Usage: !slots <wager>")
        return

    user_id = ctx.author.id
    current_balance = await get_balance(user_id) or 0

    if current_balance < wager or wager <= 0:
        await ctx.send(f'{ctx.author.mention}, you do not have enough tokens to wager {wager}!')
        return

    await subtract_balance(user_id, wager)

    slot_items = ['💰', '💵', '🍉', '🔔', '🍑', '🍎', '🍒']
    weights = [1, 3, 2, 1, 7, 5, 2]
    total_weight = sum(weights)

    grid = [random.choices(slot_items, weights, k=3) for _ in range(3)]

    slot_output = f'''
-====:|$|:====-
[{grid[0][0]} : {grid[0][1]} : {grid[0][2]}]
[{grid[1][0]} : {grid[1][1]} : {grid[1][2]}]
[{grid[2][0]} : {grid[2][1]} : {grid[2][2]}]
'''

    await ctx.send(slot_output)

    row = grid[1]

    def calculate_payout(symbols, wager):
        if symbols[0] == symbols[1] == symbols[2]:
            if symbols[0] == '💰':
                return wager * 200
            elif symbols[0] == '💵':
                return wager * 100
            elif symbols[0] == '🍉':
                return wager * 100
            elif symbols[0] == '🔔':
                return wager * 18
            elif symbols[0] == '🍑':
                return wager * 14
            elif symbols[0] == '🍎':
                return wager * 10
        elif symbols[0] == symbols[1] == '🍉' and symbols[2] == '💵':
            return wager * 100
        elif symbols[0] == symbols[1] == '🔔' and symbols[2] == '💵':
            return wager * 18
        elif symbols[0] == symbols[1] == '🍑' and symbols[2] == '💵':
            return wager * 14
        elif symbols[0] == symbols[1] == '🍎' and symbols[2] == '💵':
            return wager * 10
        elif symbols[0] == symbols[1] == '🍒':
            return wager * 5
        elif symbols[0] == '🍒' and symbols[1] != symbols[2]:
            return wager * 2
        else:
            return 0
        
    def calculate_odds(roll, weights, slot_items):
        odds = 1
        for symbol in roll:
            symbol_weight = weights[slot_items.index(symbol)]
            total_weight = sum(weights)
            odds *= symbol_weight / total_weight
        return odds


    payout = calculate_payout(row, wager)
    roll_odds = calculate_odds(row, weights, slot_items)
    new_balance = current_balance - wager + payout

    if payout > 0:
        await add_balance(user_id, payout)
        await ctx.send(f'{ctx.author.mention} has won {payout} tokens! Your new balance is {new_balance} tokens.')
    else:
        lost_amount = wager
        await ctx.send(f'{ctx.author.mention} has lost {lost_amount} tokens. Your new balance is {new_balance} tokens.')

    await ctx.send(f"The odds of this roll were 1 in {1/roll_odds:.2f}.")

@bot.command(name='leaderboard', help='Display the leaderboard')
async def leaderboard(ctx):
    async with aiosqlite.connect('leaderboard.db') as db:
        cursor = await db.execute('SELECT user_id, balance FROM balances WHERE balance > 0 ORDER BY balance DESC')
        rows = await cursor.fetchall()
        await cursor.close()

    if not rows:
        await ctx.send('No balances found on the leaderboard.')
        return

    leaderboard_text = 'Leaderboard:\n'
    for index, row in enumerate(rows[:10], start=1):
        user_id, balance = row
        user = await bot.fetch_user(user_id)
        leaderboard_text += f'{index}. {user.name}: {balance}\n'

    await ctx.send(leaderboard_text)

# Add alias for balance command
@bot.command(name='balance', aliases=['bal'], help='Check your current token balance')
async def balance(ctx):
    user_id = ctx.author.id
    current_balance = await get_balance(user_id) or 0
    await ctx.send(f'{ctx.author.mention}, your current balance is {current_balance} tokens.')

@bot.command(name='daily', help='Claim daily reward')
@cooldown(1, 86400, BucketType.user)  # Allow one claim per user every 24 hours (86400 seconds)
async def daily(ctx):
    user_id = ctx.author.id
    daily_reward = 100
    await add_balance(user_id, daily_reward)
    await ctx.send(f"{ctx.author.mention} has claimed {daily_reward} tokens as their daily reward!")

@bot.command(name='hourly', help='Claim hourly reward')
@cooldown(1, 3600, BucketType.user)  # Allow one claim per user every hour (3600 seconds)
async def hourly(ctx):
    user_id = ctx.author.id
    hourly_reward = 10
    await add_balance(user_id, hourly_reward)
    await ctx.send(f"{ctx.author.mention} has claimed {hourly_reward} tokens as their hourly reward!")

@bot.command(name='monthly', help='Claim monthly reward')
@cooldown(1, 2592000, BucketType.user)  # Allow one claim per user every 30 days (2592000 seconds)
async def monthly(ctx):
    user_id = ctx.author.id
    monthly_reward = 5000
    await add_balance(user_id, monthly_reward)
    await ctx.send(f"{ctx.author.mention} has claimed {monthly_reward} tokens as their monthly reward!")

@bot.command(name='helps', help='Display the help menu')
async def helps(ctx):
    help_text = '''
Commands:
!slots <wager>       - Play the slot machine. Win the jackpot with 3 💰
!roulette <wager> <color>  - Roulette pick b/w Black, Red, and Green or choose a number & up to three bets using "," as a seperator
!rps <move>          - Free to play, win 100 tokens!
!crash               - Start a Crash Game
!crash <wager>       - Wager on an active Crash Game react with a "🛑" to the multiplier message to exit the game
!leaderboard         - Display the leaderboard
!balance             - Check your current token balance
!daily               - Claim your daily tokens
!hourly              - Claim your hourly tokens
!monthly             - Claim your monthly tokens
!distribution        - Display the winning combinations and multipliers
!shop                - View available items in the shop
!buy <item_name>     - Buy an item from the shop
!inventory           - View your inventory
!pay <user> <amount> - Give tokens to another user
!helps               - Display the help menu
'''
    await ctx.send(help_text)

@bot.command(name='pay', help='Give tokens to another user: !pay <user> <amount>')
async def pay(ctx, recipient: discord.Member, amount: int):
    sender_id = ctx.author.id
    recipient_id = recipient.id

    sender_balance = await get_balance(sender_id) or 0
    if sender_balance < amount or amount <= 0:
        await ctx.send(f"{ctx.author.mention}, you do not have enough tokens to give {amount} tokens.")
        return

    await subtract_balance(sender_id, amount)
    await add_balance(recipient_id, amount)

    sender_new_balance = sender_balance - amount
    recipient_new_balance = await get_balance(recipient_id) or 0

    await ctx.send(f"{ctx.author.mention} has given {recipient.mention} {amount} tokens. "
                   f"Your new balance is {sender_new_balance} tokens. "
                   f"{recipient.mention}'s new balance is {recipient_new_balance} tokens.")

winning_combinations = {
    "💰💰💰": "200x",
    "💵💵💵": "100x",
    "🍉🍉🍉": "100x",
    "🍉🍉💵": "100x",
    "🔔🔔🔔": "18x",
    "🔔🔔💵": "18x",
    "🍑🍑🍑": "14x",
    "🍑🍑💵": "14x",
    "🍎🍎🍎": "10x",
    "🍎🍎💵": "10x",
}

inventories = {}  # Dictionary to store user inventories
shop = {  # Dictionary to store available items in the shop
    "rock": 1000000,
    "plastic_cup": 100000,
    "paperclip": 10000,
}

@bot.command(name="shop", help="View available items in the shop")
async def view_shop(ctx):
    shop_text = "Shop items:\n"
    for item, price in shop.items():
        shop_text += f"{item}: {price} tokens\n"

    await ctx.send(shop_text)

@bot.command(name="buy", help="Buy an item from the shop: !buy <item_name>")
async def buy_item(ctx, item_name: str):
    user_id = ctx.author.id
    current_balance = await get_balance(user_id) or 0

    if item_name not in shop:
        await ctx.send(f"{ctx.author.mention}, the item '{item_name}' is not available in the shop.")
        return

    item_price = shop[item_name]
    if current_balance < item_price:
        await ctx.send(f"{ctx.author.mention}, you do not have enough tokens to buy '{item_name}'.")
        return

    await subtract_balance(user_id, item_price)

    # Update the user's inventory
    if user_id not in inventories:
        inventories[user_id] = {}

    if item_name not in inventories[user_id]:
        inventories[user_id][item_name] = 0

    inventories[user_id][item_name] += 1

    await ctx.send(f"{ctx.author.mention} has bought '{item_name}'. Your new balance is {current_balance - item_price} tokens.")

@bot.command(name="inventory", help="View your inventory", aliases=["inv"])
async def view_inventory(ctx):
    user_id = ctx.author.id

    if user_id not in inventories or not inventories[user_id]:
        await ctx.send(f"{ctx.author.mention}, your inventory is empty.")
        return

    inventory_text = f"{ctx.author.mention}'s Inventory:\n"
    for item, quantity in inventories[user_id].items():
        inventory_text += f"{item}: {quantity}\n"

    await ctx.send(inventory_text)


partial_combinations = {
    "🍒🍒 ANY": "5x",
    "🍒 ANY ANY": "2x",
}

@bot.command(name="distribution", help="Display the winning combinations and multipliers", aliases=["dist"])
async def distribution(ctx):
    combinations_text = "Winning Combinations:\n"

    for combination, multiplier in winning_combinations.items():
        combinations_text += f"{combination}: {multiplier}\n"

    combinations_text += "\nPartial Winning Combinations:\n"

    for combination, multiplier in partial_combinations.items():
        combinations_text += f"{combination}: {multiplier}\n"

    await ctx.send(combinations_text)

async def spin_wheel(ctx):
    spin_message = await ctx.send("Spinning...")
    emoji_colors = {
        "green": "🟢",
        "red": "🟥",
        "black": "⬛"
    }
    roulette_wheel = ["green"] + ["red", "black"] * 18
    random.shuffle(roulette_wheel)

    for i in range(10):  # Adjust this value to change the number of spins
        spin_sequence = [random.choice(roulette_wheel) for _ in range(5)]
        spin_result = spin_sequence[2]
        spin_display = "".join([emoji_colors[color] for color in spin_sequence])
        await spin_message.edit(content=f"{spin_display}")
        await asyncio.sleep(0.5)  # Adjust this value to change the spin speed

    return spin_result

@bot.command(name="roulette", help="Play roulette. Example: !roulette <wager1> <color1 or number1>, <wager2> <color2 or number2>, <wager3> <color3 or number3>")
async def roulette(ctx, *args):
    bet_string = " ".join(args)
    bet_parts = bet_string.split(",")

    if len(bet_parts) > 3:
        await ctx.send(f"{ctx.author.mention}, you can only place up to 3 bets!")
        return

    bet_list = []

    for bet_part in bet_parts:
        bet_split = bet_part.strip().split()
        if len(bet_split) != 2:
            await ctx.send(f"{ctx.author.mention}, invalid bet format! Usage: !roulette <wager1> <color1 or number1>, <wager2> <color2 or number2>, <wager3> <color3 or number3>")
            return
        wager, bet = int(bet_split[0]), bet_split[1]
        bet_list.append((wager, bet))

    user_id = ctx.author.id
    current_balance = await get_balance(user_id) or 0
    total_wager = sum(wager for wager, _ in bet_list)

    if current_balance < total_wager or total_wager <= 0:
        await ctx.send(f'{ctx.author.mention}, you do not have enough tokens to make these wagers!')
        return

    await subtract_balance(user_id, total_wager)

    emoji_colors = {
        "green": "🟢",
        "red": "🟥",
        "black": "⬛"
    }

    roulette_wheel = ["green"] + ["red", "black"] * 18
    random.shuffle(roulette_wheel)

    spin_result = await spin_wheel(ctx)

    def calculate_payout(bet, spin_result):
        if bet.lower() == "red" and spin_result == "red":
            return wager * 2
        elif bet.lower() == "black" and spin_result == "black":
            return wager * 2
        elif bet.lower() == "green" and spin_result == "green":
            return wager * 36
        elif bet.isdigit() and int(bet) in range(1, 37) and spin_result != "green":
            if (int(bet) % 2 == 0 and spin_result == "red") or (int(bet) % 2 == 1 and spin_result == "black"):
                return wager * 36
        return 0

    payout = calculate_payout(bet, spin_result)
    new_balance = current_balance - wager + payout

    payouts = []

    for wager, bet in bet_list:
        payout = calculate_payout(bet, spin_result)
        payouts.append(payout)
        new_balance = current_balance - wager + payout

        if payout > 0:
            await add_balance(user_id, payout)
            await ctx.send(f"{ctx.author.mention}, the ball landed on {emoji_colors[spin_result]}! You won {payout} tokens on {bet}! Your new balance is {new_balance} tokens.")
        else:
            lost_amount = wager
            await ctx.send(f"{ctx.author.mention}, the ball landed on {emoji_colors[spin_result]}! You lost {lost_amount} tokens on {bet}. Your new balance is {new_balance} tokens.")


@bot.command(name="rps", help="Play Rock, Paper, Scissors. Example: !rps rock")
async def rps(ctx, player_move: str):
    if player_move.lower() not in ["rock", "paper", "scissors"] or None:
        await ctx.send(f"{ctx.author.mention}, please choose a valid move: rock, paper, or scissors.")
        return

    moves = ["rock", "paper", "scissors"]
    bot_move = random.choice(moves)
    user_id = ctx.author.id

    winning_moves = {
        "rock": "scissors",
        "paper": "rock",
        "scissors": "paper"
    }

    if player_move.lower() == bot_move:
        await ctx.send(f"{ctx.author.mention}, it's a draw! You both chose {player_move}.")
    elif winning_moves[player_move.lower()] == bot_move:
        await add_balance(user_id, 100)
        new_balance = await get_balance(user_id)
        await ctx.send(f"{ctx.author.mention}, you won! Your move: {player_move}, bot's move: {bot_move}. You've been awarded 100 tokens! Your new balance is {new_balance} tokens.")
    else:
        await ctx.send(f"{ctx.author.mention}, you lost. Your move: {player_move}, bot's move: {bot_move}. Better luck next time!")

class CrashGame:
    def __init__(self, ctx):
        self.ctx = ctx
        self.game_in_progress = False
        self.players = {}
        self.crash_multiplier = 1.0
        self.crash_threshold = self.calculate_crash_threshold()

    def calculate_crash_threshold(self):
        if random.random() < 0.03:
            return 1.0
        return random.uniform(1.0, 5.0)

    async def start_game(self):
        self.game_in_progress = True
        crash_message = await self.ctx.send("Crash game starting in 15 seconds...")
        await crash_message.add_reaction("🛑")
        await self.start_countdown(crash_message)

        while self.crash_multiplier < self.crash_threshold:
            self.crash_multiplier += 0.05
            await crash_message.edit(content=f"Crash game: The multiplier is {self.crash_multiplier:.2f}x")
            await asyncio.sleep(0.1)

        await crash_message.edit(content=f"Crash game: The multiplier crashed at {self.crash_multiplier:.2f}x")
        for player in self.players.values():
            if not player.pulled_out:
                lost_amount = player.wager
                await self.ctx.send(f"{player.user.mention}, the multiplier crashed! You have lost {lost_amount} tokens.")
        self.game_in_progress = False

    async def add_player(self, user, wager):
        if user.id not in self.players:
            self.players[user.id] = Player(user, wager)

    async def start_countdown(self, crash_message):
        for i in range(15, 0, -1):
            await crash_message.edit(content=f"Crash game starting in {i} seconds...")
            await asyncio.sleep(1)

class Player:
    def __init__(self, user, wager):
        self.user = user
        self.wager = wager
        self.pulled_out = False

    def pull_out(self):
        self.pulled_out = True

crash_game = None

@bot.command(name='crash', help='Start a crash game or join an ongoing game with !crash wager <amount>.')
async def crash(ctx, wager: str = None, amount: int = None):
    global crash_game
    if wager is None:
        if crash_game is not None and crash_game.game_in_progress:
            await ctx.send("There is already an ongoing crash game. Please wait until the current game is finished.")
            return
        crash_game = CrashGame(ctx)
        await crash_game.start_game()
    elif wager.lower() == 'wager' and amount is not None:
        if crash_game is None or not crash_game.game_in_progress:
            await ctx.send("There is no ongoing crash game. Please start a new game with !crash.")
            return
        await crash_game.add_player(ctx.author, amount)
        await ctx.send(f"{ctx.author.mention}, you have joined the crash game with a wager of {amount} tokens.")

@bot.event
async def on_reaction_add(reaction, user):
    if user == bot.user:
        return

    if reaction.emoji == "🛑":
        await handle_reaction(reaction, user)

async def handle_reaction(reaction, user):
    if not crash_game or not crash_game.game_in_progress:
        return

    if user.id in crash_game.players and crash_game.players[user.id] and not crash_game.players[user.id].pulled_out:
        player = crash_game.players[user.id]
        player.pull_out()
        payout = int(player.wager * crash_game.crash_multiplier)
        await crash_game.ctx.send(f"{user.mention}, you have pulled out at {crash_game.crash_multiplier:.2f}x! You won {payout} tokens.")

DECK = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
blackjack_games = {}

def calculate_hand_value(hand):
    if isinstance(hand[0], list):
        return [calculate_hand_value(h) for h in hand]
    value = sum(hand)
    if value > 21 and 11 in hand:
        hand[hand.index(11)] = 1
        value = sum(hand)
    return value

def is_pair(hand):
    return len(hand) == 2 and hand[0] == hand[1]

async def check_game_status(user_id):
    if blackjack_games[user_id]['status'] != 'ongoing':
        return None

    dealer_hand = blackjack_games[user_id]['dealer_hand']
    dealer_hand[1] = random.choice(DECK)  # Second card revealed here
    dealer_value = calculate_hand_value(dealer_hand)

    for hand in blackjack_games[user_id]['hands']:
        if hand['status'] != 'ended':
            return None

    game_status = ""
    for i, hand in enumerate(blackjack_games[user_id]['hands'], start=1):
        player_value = calculate_hand_value(hand['cards'])
        if player_value > 21:
            result = "Dealer WINS!"
            winnings = -hand['bet']
        elif dealer_value > 21 or player_value > dealer_value:
            result = 'You WIN!'
            winnings = int(hand['bet'] * 2.5)
            await add_balance(user_id, winnings)
        elif player_value == dealer_value:
            result = "It's a DRAW!"
            winnings = hand['bet']
            await add_balance(user_id, winnings)
        else:
            result = "Dealer WINS!"
            winnings = -hand['bet']

        game_status += f"Hand {i}: {result} {winnings > 0 and 'Won' or 'Lost'} {abs(winnings)} tokens.\n"
        game_status += f"Your cards: {hand['cards']} (Total: {player_value}). Dealer's cards: {dealer_hand} (Total: {dealer_value}).\n"

    del blackjack_games[user_id]  # Deleting the game instance

    return game_status


@bot.command(name="blackjack", help="Start a game of blackjack.")
async def blackjack(ctx, bet: int):
    user_id = str(ctx.author.id)
    
    if user_id in blackjack_games and blackjack_games[user_id]['status'] == 'ongoing':
        await ctx.send("Your current game of blackjack is still ongoing.")
        return

    current_balance = await get_balance(user_id)
    if not current_balance or current_balance < bet:
        await ctx.send("You don't have enough tokens to place this bet.")
        return

    await subtract_balance(user_id, bet)

    player_hand = [{'cards': [random.choice(DECK) for _ in range(2)], 'bet': bet, 'status': 'ongoing'}]
    dealer_hand = [random.choice(DECK), "?"]

    blackjack_games[user_id] = {
        'status': 'ongoing',
        'hands': player_hand,
        'dealer_hand': dealer_hand
    }

    player_value = calculate_hand_value(player_hand[0]['cards'])
    dealer_value = calculate_hand_value([dealer_hand[0]])

    options = "`!hit`, `!stand`"
    if is_pair(player_hand[0]['cards']):
        options += ", `!split`"
    await ctx.send(f"Your hand: {player_hand[0]['cards']} (Total: {player_value}). Dealer's card: {dealer_hand[0]} (Total: {dealer_value}). Your options: {options}.")


@bot.command(name="hit", help="Draw another card.")
async def blackjack_hit(ctx, hand_index: int = 1):
    user_id = str(ctx.author.id)

    if user_id not in blackjack_games:
        await ctx.send("You're not currently in a game of blackjack.")
        return

    if blackjack_games[user_id]['status'] != 'ongoing':
        await ctx.send("Your current game of blackjack is not ongoing.")
        return

    hand = blackjack_games[user_id]['hands'][hand_index - 1]
    hand['cards'].append(random.choice(DECK))

    player_value = calculate_hand_value(hand['cards'])
    dealer_value = calculate_hand_value([blackjack_games[user_id]['dealer_hand'][0]])

    if player_value > 21:
        hand['status'] = 'ended'
        game_status = await check_game_status(user_id)
        if game_status:
            await ctx.send(f"You've busted with hand {hand_index}: {hand['cards']} (Total: {player_value}). {game_status}")
            return
        else:
            await ctx.send(f"You've busted with hand {hand_index}: {hand['cards']} (Total: {player_value}). Dealer's card: {blackjack_games[user_id]['dealer_hand'][0]} (Total: {dealer_value}).")
            return

    options = "`!hit`, `!stand`"
    if is_pair(hand['cards']):
        options += ", `!split`"
    await ctx.send(f"Your hand {hand_index}: {hand['cards']} (Total: {player_value}). Dealer's card: {blackjack_games[user_id]['dealer_hand'][0]} (Total: {dealer_value}). Your options: {options}.")

@bot.command(name="stand", help="End your turn and let the dealer play")
async def blackjack_stand(ctx, hand_index: int = 1):
    user_id = str(ctx.author.id)
    if user_id not in blackjack_games or blackjack_games[user_id]['status'] != 'ongoing':
        await ctx.send("You are not currently in a game of blackjack.")
        return

    if hand_index > len(blackjack_games[user_id]['hands']):
        await ctx.send("Invalid hand index.")
        return

    blackjack_games[user_id]['hands'][hand_index - 1]['status'] = 'ended'
    game_status = await check_game_status(user_id)
    if game_status:
        if user_id in blackjack_games:  # Check if the game instance still exists
            await ctx.send(f"Your hand {hand_index} ended. Dealer's hand: {blackjack_games[user_id]['dealer_hand']} (Total: {calculate_hand_value(blackjack_games[user_id]['dealer_hand'])}). {game_status}")
        else:
            await ctx.send(game_status)


@bot.command(name="double", help="Double your bet and take exactly one more card.")
async def blackjack_double(ctx, hand_index: int = 1):
    user_id = str(ctx.author.id)
    if user_id not in blackjack_games or blackjack_games[user_id]['status'] != 'ongoing':
        await ctx.send("You are not currently in a game of blackjack.")
        return

    if hand_index > len(blackjack_games[user_id]['hands']):
        await ctx.send("Invalid hand index.")
        return

    hand = blackjack_games[user_id]['hands'][hand_index - 1]
    current_balance = await get_balance(user_id)
    if current_balance < hand['bet']:
        await ctx.send("You don't have enough tokens to double your bet.")
        return

    await subtract_balance(user_id, hand['bet'])
    hand['bet'] *= 2
    hand['cards'].append(random.choice(DECK))

    player_value = calculate_hand_value(hand['cards'])
    dealer_value = calculate_hand_value([blackjack_games[user_id]['dealer_hand'][0]])

    if player_value > 21:
        hand['status'] = 'ended'
        game_status = await check_game_status(user_id)
        if game_status:
            blackjack_games[user_id]['dealer_hand'][1] = random.choice(DECK)
            await ctx.send(f"You've busted with hand {hand_index}: {hand['cards']} (Total: {player_value}). Dealer's hand: {blackjack_games[user_id]['dealer_hand']} (Total: {calculate_hand_value(blackjack_games[user_id]['dealer_hand'])}). Dealer wins. {game_status}")
        else:
            await ctx.send(f"You've busted with hand {hand_index}: {hand['cards']} (Total: {player_value}). Dealer's card: {blackjack_games[user_id]['dealer_hand'][0]} (Total: {dealer_value}).")
    else:
        await blackjack_stand(ctx, hand_index)

@bot.command(name="split", help="Split your hand into two if you have a pair.")
async def blackjack_split(ctx):
    user_id = str(ctx.author.id)
    if user_id not in blackjack_games or blackjack_games[user_id]['status'] != 'ongoing':
        await ctx.send("You're not currently in a game of blackjack.")
        return

    if len(blackjack_games[user_id]['hands']) != 1:
        await ctx.send("You can only split on your first turn.")
        return

    hand = blackjack_games[user_id]['hands'][0]
    if not is_pair(hand['cards']):
        await ctx.send("You can only split if your first two cards form a pair.")
        return

    current_balance = await get_balance(user_id)
    if current_balance < hand['bet']:
        await ctx.send("You don't have enough tokens to split your hand.")
        return

    await subtract_balance(user_id, hand['bet'])
    new_hand = hand.copy()
    hand['cards'][1] = random.choice(DECK)
    new_hand['cards'][0] = random.choice(DECK)  # Draw a new card for the second hand
    blackjack_games[user_id]['hands'].append(new_hand)

    dealer_value = calculate_hand_value([blackjack_games[user_id]['dealer_hand'][0]])
    for i, hand in enumerate(blackjack_games[user_id]['hands'], start=1):
        player_value = calculate_hand_value(hand['cards'])
        options = "`!hit`, `!stand`"
        if is_pair(hand['cards']):
            options += ", `!split`"
        await ctx.send(f"Your hand {i}: {hand['cards']} (Total: {player_value}). Dealer's card: {blackjack_games[user_id]['dealer_hand'][0]} (Total: {dealer_value}). Your options: {options}.")

@bot.command(name="bet1", help="Place your bet for the first hand after splitting.")
async def blackjack_bet1(ctx, bet: int):
    user_id = str(ctx.author.id)
    if user_id not in blackjack_games or blackjack_games[user_id]['status'] != 'ongoing':
        await ctx.send("You're not currently in a game of blackjack.")
        return

    if len(blackjack_games[user_id]['hands']) < 2:
        await ctx.send("You can only place separate bets after splitting.")
        return

    current_balance = await get_balance(user_id)
    if current_balance < bet:
        await ctx.send("You don't have enough tokens to place this bet.")
        return

    await subtract_balance(user_id, bet)
    blackjack_games[user_id]['hands'][0]['bet'] = bet

    await ctx.send(f"You've placed a bet of {bet} tokens for your first hand.")

@bot.command(name="bet2", help="Place your bet for the second hand after splitting.")
async def blackjack_bet2(ctx, bet: int):
    user_id = str(ctx.author.id)
    if user_id not in blackjack_games or blackjack_games[user_id]['status'] != 'ongoing':
        await ctx.send("You're not currently in a game of blackjack.")
        return

    if len(blackjack_games[user_id]['hands']) < 2:
        await ctx.send("You can only place separate bets after splitting.")
        return

    current_balance = await get_balance(user_id)
    if current_balance < bet:
        await ctx.send("You don't have enough tokens to place this bet.")
        return

    await subtract_balance(user_id, bet)
    blackjack_games[user_id]['hands'][1]['bet'] = bet

    await ctx.send(f"You've placed a bet of {bet} tokens for your second hand.")

bot.run(TOKEN)


