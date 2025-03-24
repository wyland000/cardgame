import discord
import os
import random
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from typing import Dict, List, Set, Tuple, Optional
import glob
import sys

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# If token is not found, prompt for it
if TOKEN is None:
    print("Discord token not found in .env file.")
    print("Please enter your Discord bot token:")
    TOKEN = input("> ").strip()
    
    # Save token to .env file for future use
    try:
        with open(".env", "w") as f:
            f.write(f"DISCORD_TOKEN={TOKEN}")
        print("Token saved to .env file for future use.")
    except Exception as e:
        print(f"Warning: Could not save token to .env file: {e}")
        print("You'll need to enter your token again next time you run the bot.")

# Verify token is not empty
if not TOKEN:
    print("ERROR: No Discord token provided. Bot cannot start.")
    print("Please create a .env file with your token or enter it when prompted.")
    sys.exit(1)

# Bot configuration - Try to use privileged intents if available, otherwise fall back to basic intents
print("\n=== DISCORD INTENTS CONFIGURATION ===")
print("Privileged intents are required for certain bot features.")
print("1. We'll try to use privileged intents first.")
print("2. If that fails, we'll fall back to basic intents (some features may not work).")
print("To enable privileged intents:")
print("   1. Go to https://discord.com/developers/applications/")
print("   2. Select your application")
print("   3. Go to 'Bot' tab")
print("   4. Enable 'Message Content Intent' and 'Server Members Intent'")
print("   5. Save changes and restart the bot")
print("=======================================\n")

# Start with full intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
intents.reactions = True

# Create bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Game state
class GameState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.players = {}  # Maps player name to Player object
        self.losers = {}   # Maps player name to Player object for those who surrendered
        self.deck = []     # List of card paths that are still in the deck
        self.dealt_cards = []  # List of card paths that have been dealt
        self.hidden_cards = []  # List of card paths that have been hidden
        self.discarded_cards = []  # List of card paths that have been discarded
        self.is_game_active = False
        self.victory_counter = {}  # Maps player name to number of victories

    def load_deck(self):
        # Get all card images
        try:
            card_files = glob.glob("card/*.jpg")
            if not card_files:
                print("WARNING: No card images found in card/*.jpg")
                # Check if the directory exists
                if not os.path.exists("card"):
                    print("ERROR: 'card' directory not found!")
                    print("Current directory:", os.getcwd())
                    print("Contents of current directory:", os.listdir("."))
                else:
                    print("The 'card' directory exists but no .jpg files were found")
                    print("Contents of 'card' directory:", os.listdir("card"))
            
            random.shuffle(card_files)
            self.deck = card_files
            print(f"Loaded {len(card_files)} cards into the deck")
        except Exception as e:
            print(f"ERROR loading deck: {e}")
            import traceback
            traceback.print_exc()
            # Create an empty deck as fallback
            self.deck = []
        
class Player:
    def __init__(self, name, user_id):
        self.name = name
        self.user_id = user_id
        self.hand = []  # List of card paths
        self.selected_cards = []  # List of card paths that are selected
        self.thread = None  # Discord thread for this player

# Initialize game state
game = GameState()

@bot.event
async def on_ready():
    print(f'Success! {bot.user} has connected to Discord!')
    print(f'Bot is connected to {len(bot.guilds)} guild(s):')
    for guild in bot.guilds:
        print(f'- {guild.name} (ID: {guild.id})')
    print('Bot is ready to receive commands. Try !join to start!')

@bot.event
async def on_error(event, *args, **kwargs):
    print(f'Error in event {event}:')
    import traceback
    traceback.print_exc()

@bot.command(name='join')
async def join_game(ctx, name=None):
    """Join the game with the given name"""
    if game.is_game_active:
        await ctx.send(f"Cannot join: A game is already in progress.")
        return
    
    user_id = ctx.author.id
    
    # If no name is provided, use the author's display name
    if name is None:
        name = ctx.author.display_name
    
    # Check if player already exists
    for player_name, player in game.players.items():
        if player.user_id == user_id:
            await ctx.send(f"You have already joined as {player_name}.")
            return
        if player_name.lower() == name.lower():
            await ctx.send(f"Someone has already taken the name {name}.")
            return
    
    # Create a new player
    player = Player(name, user_id)
    game.players[name] = player
    
    # Initialize victory counter for new player if not already present
    if name not in game.victory_counter:
        game.victory_counter[name] = 0
    
    await ctx.send(f"{name} has joined the game!")

@bot.command(name='leave')
async def leave_game(ctx):
    """Leave the game"""
    user_id = ctx.author.id
    
    # Find the player
    player_name = None
    for name, player in game.players.items():
        if player.user_id == user_id:
            player_name = name
            break
    
    if player_name is None:
        for name, player in game.losers.items():
            if player.user_id == user_id:
                player_name = name
                break
    
    if player_name is None:
        await ctx.send("You are not in the game.")
        return
    
    # Remove the player
    if player_name in game.players:
        player = game.players.pop(player_name)
        
        # Return cards to discard pile
        game.discarded_cards.extend(player.hand)
        
        # Close the thread if it exists
        if player.thread:
            await player.thread.delete()
        
        await ctx.send(f"{player_name} has left the game.")
    elif player_name in game.losers:
        player = game.losers.pop(player_name)
        
        # Return cards to discard pile
        game.discarded_cards.extend(player.hand)
        
        # Close the thread if it exists
        if player.thread:
            await player.thread.delete()
        
        await ctx.send(f"{player_name} has left the game.")

@bot.command(name='list')
async def list_players(ctx):
    """List all players in the game"""
    if not game.players and not game.losers:
        await ctx.send("No players have joined the game yet.")
        return
    
    msg = "Players in the game:\n"
    for name in game.players:
        msg += f"- {name} (Cards: {len(game.players[name].hand)})\n"
    
    if game.losers:
        msg += "\nPlayers who have surrendered:\n"
        for name in game.losers:
            msg += f"- {name} (Cards: {len(game.losers[name].hand)})\n"
    
    await ctx.send(msg)

@bot.command(name='start')
async def start_game(ctx):
    """Start the game"""
    if game.is_game_active:
        await ctx.send("A game is already in progress.")
        return
    
    if len(game.players) < 1:
        await ctx.send("Not enough players to start a game. At least 1 player is required.")
        return
    
    # Load and shuffle the deck
    game.reset()
    game.load_deck()
    game.is_game_active = True
    
    await ctx.send("Game is starting!")
    
    # Deal 2 cards to each player
    for name, player in game.players.items():
        # Create a thread for the player if it doesn't exist
        if not player.thread:
            member = ctx.guild.get_member(player.user_id)
            if member:
                thread = await ctx.channel.create_thread(
                    name=f"{name}'s hand",
                    type=discord.ChannelType.private_thread,
                    auto_archive_duration=1440  # 1 day
                )
                await thread.add_user(member)
                player.thread = thread
                await thread.send(f"This is your private thread, {name}. Your cards will be sent here.")
        
        # Deal 2 cards
        await draw_cards(ctx, name, 2, True)
    
    await ctx.send("Each player has been dealt 2 cards. Good luck!")

async def deal_card_to_player(player, card_path):
    """Deal a card to a player and set up reactions"""
    if not player.thread:
        return False
    
    # Check if the card file exists
    if not os.path.exists(card_path):
        print(f"ERROR: Card file not found: {card_path}")
        return False
    
    try:
        # Send the card as a file to the player's thread
        card_file = discord.File(card_path)
        card_msg = await player.thread.send(file=card_file)
        
        # Add reactions for card actions
        await card_msg.add_reaction("⬆️")  # play card
        await card_msg.add_reaction("🗑️")  # discard card
        await card_msg.add_reaction("✅")  # select card
        
        # Add card to player's hand
        player.hand.append(card_path)
        
        # Add card to dealt cards list
        game.dealt_cards.append(card_path)
        
        return True
    except Exception as e:
        print(f"ERROR dealing card {card_path}: {e}")
        return False

@bot.command(name='end')
async def end_game(ctx):
    """End the current game"""
    if not game.is_game_active:
        await ctx.send("No game is currently in progress.")
        return
    
    # Determine winners (players not in losers)
    winners = [name for name in game.players]
    
    # Update victory counter
    for winner in winners:
        game.victory_counter[winner] = game.victory_counter.get(winner, 0) + 1
    
    # Display results
    result_msg = "Game Over!\n\n"
    
    if winners:
        result_msg += "Winners:\n"
        for winner in winners:
            victories = game.victory_counter.get(winner, 0)
            result_msg += f"- {winner} (Total Victories: {victories})\n"
    
    if game.losers:
        result_msg += "\nLosers:\n"
        for loser in game.losers:
            victories = game.victory_counter.get(loser, 0)
            result_msg += f"- {loser} (Total Victories: {victories})\n"
    
    # Display victory counts for all players
    result_msg += "\nOverall Standings:\n"
    sorted_players = sorted(game.victory_counter.items(), key=lambda x: x[1], reverse=True)
    for player, victories in sorted_players:
        result_msg += f"- {player}: {victories} victories\n"
    
    await ctx.send(result_msg)
    
    # Reset game state but keep victory counter
    victory_counter = game.victory_counter.copy()
    game.reset()
    game.victory_counter = victory_counter
    
    # Delete all player threads
    for name, player in list(game.players.items()):
        if player.thread:
            await player.thread.delete()
            player.thread = None
    
    for name, player in list(game.losers.items()):
        if player.thread:
            await player.thread.delete()
            player.thread = None
    
    await ctx.send("All player threads have been deleted. Start a new game with !start.")

@bot.command(name='surrender')
async def surrender(ctx):
    """Surrender and move to the losing group"""
    if not game.is_game_active:
        await ctx.send("No game is currently in progress.")
        return
    
    user_id = ctx.author.id
    
    # Find the player
    player_name = None
    for name, player in game.players.items():
        if player.user_id == user_id:
            player_name = name
            break
    
    if player_name is None:
        await ctx.send("You are not in the game or have already surrendered.")
        return
    
    # Move player to losers
    player = game.players.pop(player_name)
    game.losers[player_name] = player
    
    await ctx.send(f"{player_name} has surrendered and moved to the losing group.")

async def draw_cards(ctx, target_name, num_cards, silent=False):
    """Draw cards for a player"""
    if not game.is_game_active:
        if not silent:
            await ctx.send("No game is currently in progress.")
        return
    
    if target_name not in game.players:
        if not silent:
            await ctx.send(f"Player {target_name} is not in the game or has surrendered.")
        return
    
    player = game.players[target_name]
    
    # Check if there are enough cards in the deck
    if len(game.deck) < num_cards:
        if not silent:
            await ctx.send(f"Not enough cards in the deck. Only {len(game.deck)} cards remain.")
        num_cards = len(game.deck)
    
    if num_cards <= 0:
        if not silent:
            await ctx.send("No cards left in the deck.")
        return
    
    # Draw the cards
    for _ in range(num_cards):
        if not game.deck:
            break
        
        card = game.deck.pop(0)
        success = await deal_card_to_player(player, card)
        
        if not success:
            game.deck.append(card)  # Put the card back if dealing failed
            if not silent:
                await ctx.send(f"Failed to deal a card to {target_name}.")
            break
    
    if not silent:
        await ctx.send(f"{target_name} drew {num_cards} cards.")

@bot.command(name='draw')
async def draw_command(ctx, num_cards: int = 1):
    """Draw cards from the deck"""
    user_id = ctx.author.id
    
    # Find the player
    player_name = None
    for name, player in game.players.items():
        if player.user_id == user_id:
            player_name = name
            break
    
    if player_name is None:
        await ctx.send("You are not in the game or have surrendered.")
        return
    
    await draw_cards(ctx, player_name, num_cards)

@bot.command(name='discard')
async def discard_command(ctx, num_cards: int = 1):
    """Discard cards from your hand"""
    if not game.is_game_active:
        await ctx.send("No game is currently in progress.")
        return
    
    user_id = ctx.author.id
    
    # Find the player
    player_name = None
    for name, player in game.players.items():
        if player.user_id == user_id:
            player_name = name
            break
    
    if player_name is None:
        await ctx.send("You are not in the game or have surrendered.")
        return
    
    player = game.players[player_name]
    
    if len(player.hand) < num_cards:
        await ctx.send(f"You only have {len(player.hand)} cards in your hand.")
        return
    
    # Discard selected cards first
    discarded = 0
    
    while discarded < num_cards and player.selected_cards:
        card = player.selected_cards.pop(0)
        if card in player.hand:
            player.hand.remove(card)
            game.discarded_cards.append(card)
            discarded += 1
    
    # If we still need to discard more, take from unselected cards
    while discarded < num_cards and player.hand:
        card = player.hand.pop(0)
        game.discarded_cards.append(card)
        if card in player.selected_cards:
            player.selected_cards.remove(card)
        discarded += 1
    
    await ctx.send(f"{player_name} discarded {discarded} cards.")

@bot.command(name='swap')
async def swap_command(ctx, name1=None, name2=None, name3=None):
    """Swap hands between players"""
    if not game.is_game_active:
        await ctx.send("No game is currently in progress.")
        return
    
    # Check if enough names are provided
    if name1 is None or name2 is None:
        await ctx.send("Please provide at least two player names to swap hands.")
        return
    
    # Check if all players exist and are in the game
    players_to_swap = []
    for name in [name1, name2, name3]:
        if name is None:
            continue
        
        if name not in game.players:
            await ctx.send(f"Player {name} is not in the game or has surrendered.")
            return
        
        players_to_swap.append(game.players[name])
    
    # Swap hands
    if len(players_to_swap) == 2:
        # Swap between two players
        players_to_swap[0].hand, players_to_swap[1].hand = players_to_swap[1].hand, players_to_swap[0].hand
        players_to_swap[0].selected_cards, players_to_swap[1].selected_cards = [], []
        
        await ctx.send(f"Hands swapped between {name1} and {name2}.")
        
        # Notify players
        if players_to_swap[0].thread:
            await players_to_swap[0].thread.send(f"Your hand has been swapped with {name2}. You now have {len(players_to_swap[0].hand)} cards.")
            
            # Send new cards as whispers
            for card_path in players_to_swap[0].hand:
                card_file = discord.File(card_path)
                card_msg = await players_to_swap[0].thread.send(file=card_file)
                await card_msg.add_reaction("⬆️")  # play card
                await card_msg.add_reaction("🗑️")  # discard card
                await card_msg.add_reaction("✅")  # select card
        
        if players_to_swap[1].thread:
            await players_to_swap[1].thread.send(f"Your hand has been swapped with {name1}. You now have {len(players_to_swap[1].hand)} cards.")
            
            # Send new cards as whispers
            for card_path in players_to_swap[1].hand:
                card_file = discord.File(card_path)
                card_msg = await players_to_swap[1].thread.send(file=card_file)
                await card_msg.add_reaction("⬆️")  # play card
                await card_msg.add_reaction("🗑️")  # discard card
                await card_msg.add_reaction("✅")  # select card
    
    elif len(players_to_swap) == 3:
        # Swap between three players (cyclically)
        hand1 = players_to_swap[0].hand
        hand2 = players_to_swap[1].hand
        hand3 = players_to_swap[2].hand
        
        players_to_swap[0].hand = hand3
        players_to_swap[1].hand = hand1
        players_to_swap[2].hand = hand2
        
        players_to_swap[0].selected_cards = []
        players_to_swap[1].selected_cards = []
        players_to_swap[2].selected_cards = []
        
        await ctx.send(f"Hands swapped cyclically between {name1}, {name2}, and {name3}.")
        
        # Notify players
        if players_to_swap[0].thread:
            await players_to_swap[0].thread.send(f"Your hand has been swapped with {name3}. You now have {len(players_to_swap[0].hand)} cards.")
            
            # Send new cards as whispers
            for card_path in players_to_swap[0].hand:
                card_file = discord.File(card_path)
                card_msg = await players_to_swap[0].thread.send(file=card_file)
                await card_msg.add_reaction("⬆️")  # play card
                await card_msg.add_reaction("🗑️")  # discard card
                await card_msg.add_reaction("✅")  # select card
        
        if players_to_swap[1].thread:
            await players_to_swap[1].thread.send(f"Your hand has been swapped with {name1}. You now have {len(players_to_swap[1].hand)} cards.")
            
            # Send new cards as whispers
            for card_path in players_to_swap[1].hand:
                card_file = discord.File(card_path)
                card_msg = await players_to_swap[1].thread.send(file=card_file)
                await card_msg.add_reaction("⬆️")  # play card
                await card_msg.add_reaction("🗑️")  # discard card
                await card_msg.add_reaction("✅")  # select card
        
        if players_to_swap[2].thread:
            await players_to_swap[2].thread.send(f"Your hand has been swapped with {name2}. You now have {len(players_to_swap[2].hand)} cards.")
            
            # Send new cards as whispers
            for card_path in players_to_swap[2].hand:
                card_file = discord.File(card_path)
                card_msg = await players_to_swap[2].thread.send(file=card_file)
                await card_msg.add_reaction("⬆️")  # play card
                await card_msg.add_reaction("🗑️")  # discard card
                await card_msg.add_reaction("✅")  # select card

@bot.command(name='give')
async def give_command(ctx, target_name=None):
    """Transfer selected cards to another player"""
    if not game.is_game_active:
        await ctx.send("No game is currently in progress.")
        return
    
    if target_name is None:
        await ctx.send("Please provide a player name to give cards to.")
        return
    
    user_id = ctx.author.id
    
    # Find the sender
    sender_name = None
    for name, player in game.players.items():
        if player.user_id == user_id:
            sender_name = name
            break
    
    if sender_name is None:
        await ctx.send("You are not in the game or have surrendered.")
        return
    
    # Check if target player exists
    if target_name not in game.players:
        await ctx.send(f"Player {target_name} is not in the game or has surrendered.")
        return
    
    sender = game.players[sender_name]
    target = game.players[target_name]
    
    # Check if sender has selected any cards
    if not sender.selected_cards:
        await ctx.send(f"You haven't selected any cards to give. Use the ✅ reaction to select cards.")
        return
    
    # Transfer selected cards
    cards_given = []
    for card in sender.selected_cards:
        if card in sender.hand:
            sender.hand.remove(card)
            target.hand.append(card)
            cards_given.append(card)
    
    sender.selected_cards = []
    
    await ctx.send(f"{sender_name} gave {len(cards_given)} cards to {target_name}.")
    
    # Send the cards to the target player's thread
    if target.thread and cards_given:
        await target.thread.send(f"{sender_name} gave you {len(cards_given)} cards:")
        
        for card_path in cards_given:
            card_file = discord.File(card_path)
            card_msg = await target.thread.send(file=card_file)
            await card_msg.add_reaction("⬆️")  # play card
            await card_msg.add_reaction("🗑️")  # discard card
            await card_msg.add_reaction("✅")  # select card

@bot.command(name='revive')
async def revive_command(ctx, target_name=None):
    """Revive a player from the losing group"""
    if not game.is_game_active:
        await ctx.send("No game is currently in progress.")
        return
    
    if target_name is None:
        await ctx.send("Please provide a player name to revive.")
        return
    
    # Check if target player exists in losers
    if target_name not in game.losers:
        await ctx.send(f"Player {target_name} is not in the losing group.")
        return
    
    # Revive player
    player = game.losers.pop(target_name)
    game.players[target_name] = player
    
    await ctx.send(f"{target_name} has been revived and added back to the game.")
    
    # Deal 2 cards to the revived player
    await draw_cards(ctx, target_name, 2)

# Handle reactions for both main channel and player threads
@bot.event
async def on_reaction_add(reaction, user):
    """Handle reactions on cards"""
    if user.bot:
        return  # Ignore reactions from bots
    
    if not game.is_game_active:
        return
    
    # Check if the reaction is in a player's thread
    if isinstance(reaction.message.channel, discord.Thread):
        # This is a player thread
        await handle_player_thread_reaction(reaction, user)
    else:
        # This is the main channel
        await handle_main_channel_reaction(reaction, user)

async def handle_main_channel_reaction(reaction, user):
    """Handle reactions on cards in the main channel"""
    # Check if the message has attachments (card)
    if not reaction.message.attachments:
        return
    
    attachment = reaction.message.attachments[0]
    
    # Find the player who played the card
    player_name = None
    if reaction.message.content.startswith("🎮"):
        # Extract player name from content
        content_parts = reaction.message.content.split(" ")
        if len(content_parts) >= 2:
            player_name = content_parts[1]
    
    if player_name is None or player_name not in game.players:
        return
    
    player = game.players[player_name]
    
    # Handle different reactions in main channel
    if str(reaction.emoji) == "❌" and player.user_id == user.id:  # Take back (original player only)
        # Find corresponding card in played cards
        for card_path in game.dealt_cards:
            filename = os.path.basename(card_path)
            if filename in attachment.filename:
                # Return card to player's hand
                player.hand.append(card_path)
                game.dealt_cards.remove(card_path)
                
                # Send card back to player's thread
                if player.thread:
                    card_file = discord.File(card_path)
                    card_msg = await player.thread.send("Card returned to your hand:", file=card_file)
                    await card_msg.add_reaction("⬆️")  # play card
                    await card_msg.add_reaction("🗑️")  # discard card
                    await card_msg.add_reaction("✅")  # select card
                
                await reaction.message.delete()
                break
    
    elif str(reaction.emoji) == "🗑️":  # Hide card
        # Find corresponding card
        for card_path in game.dealt_cards:
            filename = os.path.basename(card_path)
            if filename in attachment.filename:
                # Move card to hidden cards
                game.dealt_cards.remove(card_path)
                game.hidden_cards.append(card_path)
                
                await reaction.message.delete()
                await reaction.message.channel.send(f"A card has been hidden by {user.display_name}.")
                break

async def handle_player_thread_reaction(reaction, user):
    """Handle reactions on cards in player threads"""
    # Find the player
    player_name = None
    player = None
    
    for name, p in game.players.items():
        if p.thread and p.thread.id == reaction.message.channel.id:
            player_name = name
            player = p
            break
    
    if player is None:
        return  # Not a player thread
    
    # Check if it's the player's reaction
    if player.user_id != user.id:
        return  # Not the player's reaction
    
    # Check if the message has attachments (card)
    if not reaction.message.attachments:
        return
    
    attachment = reaction.message.attachments[0]
    
    # Find the corresponding card in the player's hand
    card_path = None
    for card in player.hand:
        filename = os.path.basename(card)
        if filename in attachment.filename:
            card_path = card
            break
    
    if card_path is None:
        return  # Card not found in player's hand
    
    # Handle different reactions
    if str(reaction.emoji) == "⬆️":  # Play card
        # Remove card from hand
        player.hand.remove(card_path)
        if card_path in player.selected_cards:
            player.selected_cards.remove(card_path)
        
        # Send card to main channel
        main_channel = reaction.message.channel.parent
        
        # Get the file again
        card_file = discord.File(card_path)
        
        # Send to main channel
        play_msg = await main_channel.send(f"🎮 {player_name} plays a card:", file=card_file)
        
        # Add reactions for played card
        await play_msg.add_reaction("❌")  # take back
        await play_msg.add_reaction("🗑️")  # hide
        
        await reaction.message.delete()
        
        await player.thread.send(f"You played {os.path.basename(card_path)}.")
    
    elif str(reaction.emoji) == "🗑️":  # Discard card
        # Remove card from hand
        player.hand.remove(card_path)
        if card_path in player.selected_cards:
            player.selected_cards.remove(card_path)
        
        # Add to discarded cards
        game.discarded_cards.append(card_path)
        
        await reaction.message.delete()
        
        await player.thread.send(f"You discarded {os.path.basename(card_path)}.")
    
    elif str(reaction.emoji) == "✅":  # Select card
        if card_path not in player.selected_cards:
            player.selected_cards.append(card_path)
            await reaction.message.add_reaction("🔘")  # Mark as selected
            await player.thread.send(f"You selected {os.path.basename(card_path)}.")
        else:
            player.selected_cards.remove(card_path)
            # Remove selection mark
            for r in reaction.message.reactions:
                if str(r.emoji) == "🔘":
                    async for u in r.users():
                        if u.id == bot.user.id:
                            await r.remove(u)
                            break
            await player.thread.send(f"You deselected {os.path.basename(card_path)}.")

# Run the bot with error handling and intent fallback
if __name__ == "__main__":
    print(f"Starting Discord Card Game Bot...")
    print(f"Using token: {TOKEN[:5]}...{TOKEN[-4:]} (hidden for security)")
    
    # First attempt with full intents
    try:
        bot.run(TOKEN)
    except discord.errors.PrivilegedIntentsRequired:
        print("\n===================================================")
        print("ERROR: Privileged intents are not enabled for this bot token.")
        print("The bot requires the following privileged intents:")
        print("  - Message Content Intent")
        print("  - Server Members Intent")
        print("\nYou need to enable these in the Discord Developer Portal:")
        print("1. Go to https://discord.com/developers/applications/")
        print("2. Select your application")
        print("3. Go to 'Bot' tab")
        print("4. Under 'Privileged Gateway Intents', enable both options")
        print("5. Save changes and restart the bot")
        print("\nWould you like to try running with limited functionality? (yes/no)")
        response = input("> ").strip().lower()
        
        if response in ["y", "yes"]:
            print("Trying again with limited functionality...")
            # Create new bot with minimal intents
            minimal_intents = discord.Intents.default()
            minimal_intents.reactions = True
            bot = commands.Bot(command_prefix='!', intents=minimal_intents)
            
            # Redefine on_ready for the new bot instance
            @bot.event
            async def on_ready():
                print(f'Bot connected with LIMITED FUNCTIONALITY!')
                print(f'Connected as: {bot.user} to {len(bot.guilds)} guild(s)')
                print('WARNING: Some features will not work without privileged intents!')
                print('Please enable privileged intents in the Discord Developer Portal.')
            
            # Try again with minimal intents
            try:
                bot.run(TOKEN)
            except Exception as e:
                print(f"ERROR: Failed to start bot even with minimal intents: {e}")
                sys.exit(1)
        else:
            print("Bot startup cancelled. Please enable the required intents and try again.")
            sys.exit(1)
    except discord.errors.LoginFailure:
        print("ERROR: Invalid Discord token. Please check your token and try again.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to start bot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 