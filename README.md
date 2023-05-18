This repository contains the code for a Discord bot that provides a variety of interactive games and features for users. The bot is built using Python and the discord.py library. Here's a brief overview of the main features:

Shop and Inventory Management: Users can view available items in a virtual shop, purchase items using tokens, and view their inventory. The bot keeps track of each user's balance and inventory.

Games: The bot offers several games for users to play, including roulette, rock-paper-scissors, crash, blackjack, and slots. In each game, users can place bets using their tokens, and winnings are added to their balance.

Blackjack: The bot provides a fully-featured game of blackjack. Users can place bets, be dealt cards, and choose to hit, stand, double their bet, or split their hand if they have a pair. The bot keeps track of the game state, calculates hand values, and determines the winner of each game.

Crash Game: In the crash game, users place a wager and try to pull out before the multiplier crashes. The game is interactive and uses reactions to allow users to pull out of the game.

Roulette: Users can play a game of roulette, placing up to three bets on colors or numbers. The bot spins the wheel and calculates the payout for each bet.

Rock, Paper, Scissors: Users can play a simple game of rock-paper-scissors against the bot.

Slots: Users can play a slot machine game, where they spin the wheel and win tokens based on the resulting combination.

Combination	Payout
💰💰💰	200x
💵💵💵	100x
🍉🍉🍉	100x
🍉🍉💵	100x
🔔🔔🔔	18x
🔔🔔💵	18x
🍑🍑🍑	14x
🍑🍑💵	14x
🍎🍎🍎	10x
🍎🍎💵	10x

Token System: The bot uses a token system for purchasing items and placing bets. Users can earn tokens by winning games.

Data Persistence: The bot uses SQLite for data persistence, storing user token balances and scores in a local database.

Command Handling: The bot uses the discord.py library's commands extension for command handling. It also handles command errors and rate limits certain commands to prevent spam.

The bot uses SQLite for data persistence, storing user token balances and scores in a local database. It also handles command errors and rate limits certain commands to prevent spam.

The bot uses the discord.py library's commands extension for command handling, and the aiosqlite library for asynchronous SQLite database interaction. It also uses the dotenv library to load the bot's token from a .env file.

To use this bot, you need to have Python installed and a Discord bot token. After cloning the repository, you can run the bot with your token. The bot will then be active in your Discord server and respond to the implemented commands.

