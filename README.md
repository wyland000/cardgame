# Discord Card Game Bot

A Discord bot for playing card games, featuring private card hands, card selection, and various game commands.

## Features

- Card dealing and management with reaction-based interactions
- Private thread-based card display for each player
- Commands for game management: join, leave, start, end, etc.
- Card interaction: draw, discard, swap, give, and more
- Player management: surrender, revive, victory tracking

## Setup

1. **Clone the repository**

2. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

3. **Create a Discord Bot**
   - Go to the [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Navigate to the "Bot" tab and add a bot
   - Enable the following Privileged Gateway Intents:
     - Message Content Intent
     - Server Members Intent
   - Copy your bot token

4. **Configure Environment Variables**
   - Create a `.env` file based on the provided `.env.example`
   - Add your bot token to the `.env` file:
     ```
     DISCORD_TOKEN=your_bot_token_here
     ```

5. **Invite the Bot to Your Server**
   - Go to the OAuth2 URL Generator in the Discord Developer Portal
   - Select the scopes: `bot` and `applications.commands`
   - Select bot permissions: 
     - Send Messages
     - Manage Messages
     - Embed Links
     - Attach Files
     - Read Message History
     - Add Reactions
     - Create Public Threads
     - Create Private Threads
     - Send Messages in Threads
     - Manage Threads
   - Copy and visit the generated URL to invite the bot to your server

6. **Run the Bot**
   ```
   python card_game_bot.py
   ```

## Game Commands

- `!join [name]` - Join the game with the specified name (or your Discord display name if no name is provided)
- `!leave` - Leave the game
- `!list` - List all players in the game
- `!start` - Start the game
- `!end` - End the current game
- `!surrender` - Surrender and move to the losing group
- `!draw [number]` - Draw cards from the deck (default: 1)
- `!discard [number]` - Discard cards from your hand (default: 1)
- `!swap <name1> <name2> [name3]` - Swap hands between players
- `!give <name>` - Transfer all selected cards to another player
- `!revive <name>` - Revive a player from the losing group, giving them two cards

## Card Interactions

Cards in your hand will have reaction buttons:
- ⬆️ - Play the card
- 🗑️ - Discard the card
- ✅ - Select/Deselect the card (for transferring to other players)

Cards played on the table have these reactions:
- ❌ - Take back the card (only available to the player who played it)
- 🗑️ - Hide the card

## Game Rules

- When the game starts, each player is dealt two cards in their private thread
- Players can draw, discard, swap hands, and give cards to other players
- Players who surrender are moved to a "losing group"
- At the end of each game, players not in the losing group are declared winners
- The bot maintains a victory counter for each player 