import os
import discord
from dotenv import load_dotenv
from discord.ext import commands
import random
import asyncio
import datetime
import json
import shutil
import traceback

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="S", intents=intents, case_insensitive=True)

# Load Stand Data from JSON File
def load_stands():
    try:
        with open("stands.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading stands: {e}")
        return {}

# Initialize items storage
user_items = {}

def load_items():
    global user_items
    try:
        if os.path.exists("user_items.json"):
            with open("user_items.json", "r") as file:
                user_items = json.load(file)
        else:
            user_items = {}
    except Exception as e:
        print(f"Error loading items: {e}")
        user_items = {}

def save_items():
    try:
        with open("user_items.json", "w") as file:
            json.dump(user_items, file, indent=4)
    except Exception as e:
        print(f"Error saving items: {e}")

def add_item(user_id, item_name, amount=1):
    if user_id not in user_items:
        user_items[user_id] = {}
    
    user_items[user_id][item_name] = user_items[user_id].get(item_name, 0) + amount
    save_items()

def remove_item(user_id, item_name, amount=1):
    if user_id not in user_items or item_name not in user_items[user_id]:
        return False
    
    user_items[user_id][item_name] -= amount
    if user_items[user_id][item_name] <= 0:
        del user_items[user_id][item_name]
    
    save_items()
    return True

def get_item_count(user_id, item_name):
    return user_items.get(user_id, {}).get(item_name, 0)


# Load the stands into the bot
part_stands = load_stands()

rarity_weights = {
    "mythical": 0,
    "Legendary": 5,
    "Epic": 15,
    "Rare": 30,
    "Common": 50
}

# User inventories
user_inventories = {}

def normalize_stand_name(name):
    normalized = name.lower().replace(" ", "")
    return normalized

class StandDropdown(discord.ui.Select):
    def __init__(self, stands_on_page, user_id):
        options = []
        used_names = set()
        
        for stand_name, stand_data, _ in stands_on_page:
            normalized = normalize_stand_name(stand_name)
            if normalized in used_names:
                continue
                
            used_names.add(normalized)
            
            # Find highest seen stars for this user
            user_stand = get_user_stand(user_id, stand_name)
            highest_seen = user_stand.get("highest_seen", 1) if user_stand else 1
            
            # Show highest unlocked version
            option_label = f"{stand_name} ★{highest_seen}"
            
            options.append(discord.SelectOption(
                label=option_label,
                value=f"{stand_name}_{highest_seen}",
                description=f"{stand_data['rarity']} Stand (up to ★{highest_seen})"
            ))
        
        super().__init__(
            placeholder="Select a Stand...",
            options=options,
            min_values=1,
            max_values=1
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        stand_name = selected_value.split('_')[0]
        
        stand_data = next(
            (data for part in part_stands.values() 
             for name, data in part.items() if name == stand_name),
            None
        )
        
        if not stand_data:
            await interaction.response.send_message("Stand data not found.", ephemeral=True)
            return

        # Get highest seen stars
        user_stand = get_user_stand(self.user_id, stand_name)
        highest_seen = user_stand.get("highest_seen", 1) if user_stand else 1
        
        # Get all star levels up to highest seen
        star_levels = sorted(
            [int(k) for k in stand_data["stars"].keys() 
             if int(k) <= highest_seen]
        )
        
        view = StandImageView(stand_name, stand_data, highest_seen)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

def find_stand_data(stand_name):
    normalized = normalize_stand_name(stand_name)
    for part in part_stands.values():
        for name, data in part.items():
            if normalize_stand_name(name) == normalized:
                return name, data
    return None, None

def load_inventory():
    global user_inventories
    try:
        if os.path.exists("user_inventories.json"):
            with open("user_inventories.json", "r") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    user_inventories = {}
                    for user_id, entries in data.items():
                        inventory = []
                        for entry in entries:
                            if isinstance(entry, dict):
                                # Validate stand data
                                if "name" in entry and isinstance(entry["name"], str):
                                    inventory.append({
                                        "name": entry["name"],
                                        "stars": entry.get("stars", 1)
                                    })
                            elif isinstance(entry, str):
                                # Convert old items to new item system
                                if entry in ["rareRoll", "epicRoll", "Requiem Arrow", "arrow_fragment", "actStone"]:
                                    add_item(user_id, entry)
                                else:
                                    # Assume it's a stand with default stars
                                    inventory.append({"name": entry, "stars": 1})
                        user_inventories[user_id] = inventory
                else:
                    print("Error: Loaded data is not a dictionary")
                    restore_inventory_backup()
    except Exception as e:
        print(f"Error loading inventory: {e}")
        traceback.print_exc()
        restore_inventory_backup()

def is_valid_stand(stand_name, all_stands):
    """Check if a name represents a valid stand (not an item)"""
    valid_items = ["rareRoll", "epicRoll", "Requiem Arrow", "arrow_fragment", "actStone"]
    if stand_name in valid_items:
        return False
    return normalize_stand_name(stand_name) in all_stands

def get_user_stand(user_id, stand_name):
    normalized = normalize_stand_name(stand_name)
    inventory = user_inventories.get(str(user_id), [])
    for stand in inventory:
        if isinstance(stand, dict) and normalize_stand_name(stand["name"]) == normalized:
            return stand
        elif isinstance(stand, str) and normalize_stand_name(stand) == normalized:
            # Convert old format to new format
            stand_obj = {"name": stand, "stars": 1}
            inventory.remove(stand)
            inventory.append(stand_obj)
            return stand_obj
    return None

def restore_inventory_backup():
    """Restores inventory from backup if the main file is corrupted."""
    if os.path.exists("user_inventories_backup.json"):
        shutil.copy("user_inventories_backup.json", "user_inventories.json")
        with open("user_inventories.json", "r") as file:
            global user_inventories
            user_inventories = json.load(file)
        print("✅ Inventory restored from backup.")
    else:
        print("❌ No backup found. Inventory data may be lost.")

# Save user data to a JSON file
def save_inventory():
    if not user_inventories:
        print("⚠️ Warning: Attempted to save an empty inventory. Skipping save to prevent data loss.")
        return

    temp_filename = "user_inventories_temp.json"
    try:
        # Create backup
        if os.path.exists("user_inventories.json"):
            shutil.copy("user_inventories.json", "user_inventories_backup.json")

        # Convert stands to proper format while keeping items as strings
        save_data = {}
        for user_id, inventory in user_inventories.items():
            save_data[user_id] = []
            for entry in inventory:
                if isinstance(entry, dict):
                    save_data[user_id].append({
                        "name": entry["name"],
                        "stars": entry.get("stars", 1)
                    })
                else:
                    save_data[user_id].append(entry)

        # Write to temp file
        with open(temp_filename, "w") as file:
            json.dump(save_data, file, indent=4)

        # Replace original
        shutil.move(temp_filename, "user_inventories.json")
    except Exception as e:
        print(f"❌ Error saving inventory: {e}")

@client.command(name="cd", aliases=["cooldown", "scd"])
async def check_cooldown(ctx):
    """Check your current cooldowns"""
    user_id = str(ctx.author.id)
    messages = []
    
    # Check roll cooldown
    roll_cooldown = roll_stand.get_cooldown_retry_after(ctx)
    if roll_cooldown > 0:
        minutes = int(roll_cooldown // 60)
        seconds = int(roll_cooldown % 60)
        messages.append(f"Roll: {minutes}m {seconds}s")
    
    # Check daily cooldown
    daily_cooldown = daily_reward.get_cooldown_retry_after(ctx)
    if daily_cooldown > 0:
        hours = int(daily_cooldown // 3600)
        remaining_seconds = daily_cooldown % 3600
        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)
        messages.append(f"Daily: {hours}h {minutes}m {seconds}s")
    
    # Check darby cooldown (only if user has Osiris ★2)
    has_osiris = any(
        isinstance(stand, dict) and 
        normalize_stand_name(stand["name"]) == "osiris" and 
        stand.get("stars", 1) >= 2
        for stand in user_inventories.get(user_id, [])
    )
    
    if has_osiris:
        if hasattr(darbysoul, '_cd'):
            bucket = darbysoul._cd.get_bucket(ctx.message)
            darby_cooldown = bucket.get_retry_after()
            
            if darby_cooldown and darby_cooldown > 0:
                minutes = int(darby_cooldown // 60)
                seconds = int(darby_cooldown % 60)
                messages.append(f"D'Arby: {minutes}m {seconds}s")
    
    if messages:
        await ctx.send("\n".join(messages))
    else:
        await ctx.send("No active cooldowns!")

@client.command(name="roll", aliases=["r", "rol"])
@commands.cooldown(1, 600, commands.BucketType.user)
async def roll_stand(ctx):
    user_id = str(ctx.author.id)

    # Create weighted stands list
    weighted_stands = []
    for stands in part_stands.values():
        for stand_name, stand_data in stands.items():
            if stand_data.get("rollable", True):
                weight = rarity_weights.get(stand_data["rarity"], 0)
                weighted_stands.extend([stand_name] * weight)

    # Roll random stand
    chosen_stand = random.choice(weighted_stands)

    # Add stand to inventory
    if user_id not in user_inventories:
        user_inventories[user_id] = []
    user_inventories[user_id].append({"name": chosen_stand, "stars": 1})

    # Get stand data
    stand_data = next(
        (data for stands in part_stands.values() 
         for name, data in stands.items() if name == chosen_stand),
        None
    )
    if not stand_data:
        await ctx.send(f"Error: Stand data for {chosen_stand} not found.")
        return

    # Animation setup
    rarity = stand_data["rarity"]
    rarity_progression = {
        "Common": discord.Color.green(),
        "Rare": discord.Color.blue(),
        "Epic": discord.Color.purple(),
        "Legendary": discord.Color.gold(),
    }

    # Rolling animation
    embed = discord.Embed(
        title=f"{ctx.author.name} is rolling...",
        description="🔄 Rolling for a Stand...",
        color=discord.Color.dark_gray()
    )
    animation_message = await ctx.send(embed=embed)

    for rarity_stage in ["Common", "Rare", "Epic", "Legendary"]:
        embed.color = rarity_progression[rarity_stage]
        embed.description = f"🎲 Rolling for a Stand... {rarity_stage}"
        await animation_message.edit(embed=embed)
        await asyncio.sleep(0.6)

    # Build final embed
    final_embed = discord.Embed(
        title=f"{ctx.author.name} rolled {chosen_stand}!",
        description=f"**Rarity:** {rarity}",
        color=rarity_progression[rarity]
    )
    final_embed.set_image(url=stand_data["image"])
    final_embed.set_footer(text="Stand rolled successfully!")

    # Check for Requiem Arrow drop (1/350)
    if random.randint(1, 350) == 1:
        add_item(user_id, "Requiem Arrow")
        final_embed.add_field(
            name="???", 
            value=f"What's this on the ground? You picked up <:Requiemarrow:1353089709580091454> **Requiem Arrow**!", 
            inline=False
        )

    # Only drop bizarre items on weekends (Saturday/Sunday)
    today = datetime.datetime.today().weekday()
    if today >= 5:  # 5 = Saturday, 6 = Sunday
        if random.randint(1, 100) <= 15:
            await drop_bizarre_item(ctx)
            save_items()  # Explicitly save after adding bizarre item

    # Special animation for high rarity stands
    if rarity in ["Legendary", "mythical"]:
        flashy_title = f"{ctx.author.mention} rolled {chosen_stand} ({rarity})!"
        for _ in range(3):
            await animation_message.edit(content=flashy_title, embed=final_embed)
            await asyncio.sleep(0.5)

    await animation_message.edit(embed=final_embed)
    
    # Save all data
    save_inventory()
    save_items()  # Explicitly save items in case any were added

    # Special flashing animation for Legendary/Mythical
    if rarity in ["Legendary", "mythical"]:
        flashy_title = f"{ctx.author.mention} rolled {chosen_stand} ({rarity})!"
        for i in range(3):
            await animation_message.edit(content=flashy_title if i % 2 == 0 else "", embed=final_embed)
            await asyncio.sleep(0.5)

    await animation_message.edit(embed=final_embed)

    save_inventory()

@client.command(name="daily")
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily_reward(ctx):
    user_id = str(ctx.author.id)
    add_item(user_id, "rareRoll")
    
    embed = discord.Embed(
        title="Daily Reward Claimed!",
        description="You have received 1 Rare Roll! Use `Srollrare` to roll with a guaranteed Rare or higher stand.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@client.command(name="merge", aliases=["m", "mer"])
async def smerge(ctx, *, args: str = None):
    if not args:
        await ctx.send("Please specify a stand to merge. Example: `Smerge Silver Chariot` or `Smerge Silver Chariot 4`")
        return

    # Split arguments into stand name and optional target stars
    parts = args.split()
    if not parts:
        await ctx.send("Please specify a stand name.")
        return

    # Try to parse target stars (default to next star level)
    target_stars = None
    stand_name_parts = parts.copy()
    
    if parts[-1].isdigit():
        target_stars = int(parts[-1])
        stand_name_parts = parts[:-1]
    
    stand_name = " ".join(stand_name_parts)
    user_id = str(ctx.author.id)
    
    # Find the stand in user's inventory
    user_stand = get_user_stand(user_id, stand_name)
    if not user_stand:
        await ctx.send(f"You don't have {stand_name} in your inventory!")
        return
    
    original_name, stand_data = find_stand_data(stand_name)
    if not stand_data:
        await ctx.send(f"Stand data for {stand_name} not found!")
        return
    
    if "stars" not in stand_data:
        await ctx.send(f"{original_name} cannot be merged!")
        return
    
    # Get all copies of this stand
    inventory = user_inventories.get(user_id, [])
    all_copies = [s for s in inventory if isinstance(s, dict) and normalize_stand_name(s["name"]) == normalize_stand_name(stand_name)]
    
    # If target not specified, find next possible merge
    if target_stars is None:
        # Find all star levels with 5+ copies
        star_counts = {}
        for stand in all_copies:
            stars = stand.get("stars", 1)
            star_counts[stars] = star_counts.get(stars, 0) + 1
        
        possible_merges = []
        for stars, count in star_counts.items():
            if stars < 5 and count >= 5:  # Can merge this level
                possible_merges.append(stars + 1)
        
        if not possible_merges:
            await ctx.send(f"You don't have 5 copies of any mergeable version of {original_name}!")
            return
        
        target_stars = min(possible_merges)  # Merge the lowest possible first
    
    # Validate target stars (1-5)
    if target_stars < 1 or target_stars > 5:
        await ctx.send(f"Star level must be between 1 and 5!")
        return
    
    # Calculate required previous level
    required_previous = target_stars - 1
    if required_previous < 1:  # Should never happen since target_stars >= 2
        await ctx.send(f"Cannot merge to ★{target_stars}!")
        return
    
    # Count copies of the required previous level
    required_copies = 5
    available_copies = sum(
        1 for stand in all_copies 
        if stand.get("stars", 1) == required_previous
    )
    
    if available_copies < required_copies:
        await ctx.send(f"You need {required_copies} copies of {original_name} (★{required_previous}) to merge to ★{target_stars}!")
        return
    
    # Perform the merge
    removed = 0
    for stand in inventory[:]:  # Create copy to modify while iterating
        if (isinstance(stand, dict) and 
            normalize_stand_name(stand["name"]) == normalize_stand_name(stand_name) and 
            stand.get("stars", 1) == required_previous):
            inventory.remove(stand)
            removed += 1
            if removed == required_copies:
                break

    if original_name == DARBY_STAND and target_stars == 2:
        unlock_embed = discord.Embed(
            title="🎰 New Command Unlocked!",
            description=f"`Sdarby` gambling now available!",
            color=0xFFD700
        )
        await ctx.send(embed=unlock_embed)
    
    # Add the merged stand
    user_inventories[user_id].append({"name": original_name, "stars": target_stars})
    save_inventory()
    
    # Get the new image
    new_image = stand_data["stars"].get(str(target_stars), stand_data["stars"].get("1"))
    
    embed = discord.Embed(
        title=f"🌟 {original_name} has ascended!",
        description=f"Successfully merged to ★{target_stars}!\nUsed {required_copies} ★{required_previous} copies.",
        color=discord.Color.gold()
    )
    if new_image:
        embed.set_image(url=new_image)
    await ctx.send(embed=embed)

@client.command(name="darby")
async def darbysoul(ctx, *, bet: str = None):
    """Gamble with D'Arby (requires ★2 Osiris)"""
    user_id = str(ctx.author.id)
    
    # Initialize cooldown if not exists
    if not hasattr(darbysoul, '_cd'):
        darbysoul._cd = commands.CooldownMapping.from_cooldown(1, 1800, commands.BucketType.user)
    
    # Osiris verification
    has_osiris = any(
        isinstance(stand, dict) and 
        normalize_stand_name(stand["name"]) == "osiris" and 
        stand.get("stars", 1) >= 2
        for stand in user_inventories.get(user_id, [])
    )
    
    if not has_osiris:
        embed = discord.Embed(
            title="🚫 Gambling Parlor Locked",
            description="*\"You're not worthy to face me yet!\"*",
            color=0xFF0000
        )
        embed.add_field(
            name="Requirements",
            value="• Own ★2 Osiris\n• Something to wager",
            inline=False
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1354650264916852736/1357902139539849306/toss-coin-flip-ezgif.com-optimize.gif")
        return await ctx.send(embed=embed)

    # Help menu - NO COOLDOWN
    if not bet or bet.lower() in ["help", "menu", "info"]:
        embed = discord.Embed(
            title="🎴 D'Arby's HIGH-ROLLER Parlor",
            color=0x8B0000
        )
        embed.add_field(
            name="💰 Boosted Win Rates 💰",
            value=(
                "```diff\n"
                "+ Common: 30% win chance\n"
                "+ Rare:   40 win chance\n"
                "+ Epic:   50% win chance\n"
                "+ Legendary: 60% win chance\n"
                "+ MYTHICAL: 80% win chance\n"
                "```"
            ),
            inline=False
        )
        embed.add_field(
            name="How to Play",
            value=(
                "`Sdarby [stand/item]` - Bet something specific\n"
                "`Sdarby random` - Random bet (can take ANYTHING!)\n"
                "`Sdarby list` - View available bets"
            ),
            inline=False
        )
        return await ctx.send(embed=embed)

    # List subcommand - NO COOLDOWN
    if bet.lower() == "list":
        stands = []
        items = []
        
        for stand in user_inventories.get(user_id, []):
            if isinstance(stand, dict) and stand.get("stars", 1) == 1:
                stands.append(f"{stand['name']} ★{stand.get('stars', 1)}")
        
        load_items()
        if user_id in user_items:
            items.extend(f"{item} ×{count}" for item, count in user_items[user_id].items() if count > 0)
        
        if not stands and not items:
            return await ctx.send("You have nothing to bet!")
        
        embed = discord.Embed(
            title="Available Bets",
            description="\n".join(stands + items),
            color=0x4B0082
        )
        return await ctx.send(embed=embed)

    # Get bucket for cooldown check (but don't update yet)
    bucket = darbysoul._cd.get_bucket(ctx.message)
    retry_after = bucket.get_retry_after()
    
    # Check cooldown status
    if retry_after and retry_after > 0:
        minutes = int(retry_after // 60)
        seconds = int(retry_after % 60)
        embed = discord.Embed(
            title="⏳ Cooldown Active",
            description=f"Try again in {minutes}m {seconds}s!",
            color=0xFFA500
        )
        return await ctx.send(embed=embed)

    # Random bet
    if bet.lower() == "random":
        confirm_msg = await ctx.send(
            "⚠️ **WARNING:** This will randomly select ANY stand or item from your inventory!\n"
            "React with ✅ to confirm or ❌ to cancel."
        )
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")

        def check(reaction, user):
            return (
                user == ctx.author and
                reaction.message.id == confirm_msg.id and
                str(reaction.emoji) in ["✅", "❌"]
            )

        try:
            reaction, _ = await client.wait_for("reaction_add", timeout=30.0, check=check)
            
            if str(reaction.emoji) == "❌":
                await confirm_msg.delete()
                return await ctx.send("Bet cancelled!")
                
        except asyncio.TimeoutError:
            await confirm_msg.delete()
            return await ctx.send("Bet timed out after 30 seconds!")

        possible_bets = []
        for stand in user_inventories.get(user_id, []):
            if isinstance(stand, dict) and stand.get("stars", 1) == 1:
                possible_bets.append(("stand", stand["name"]))
        
        load_items()
        if user_id in user_items:
            possible_bets.extend(("item", item) for item in user_items[user_id] if user_items[user_id][item] > 0)
        
        if not possible_bets:
            await confirm_msg.delete()
            return await ctx.send("You have nothing to bet!")
        
        bet_type, bet_item = random.choice(possible_bets)
        await confirm_msg.delete()
    else:
        # Specific bet with improved error handling
        normalized_bet = normalize_stand_name(bet)
        user_stand = None
        
        # First try exact match
        for stand in user_inventories.get(user_id, []):
            if isinstance(stand, dict) and stand.get("stars", 1) == 1:
                if normalize_stand_name(stand["name"]) == normalized_bet:
                    user_stand = stand
                    break
        
        if not user_stand:
            # Then try items
            load_items()
            if user_id in user_items:
                for item in user_items[user_id]:
                    if item.lower() == bet.lower() and user_items[user_id][item] > 0:
                        bet_type = "item"
                        bet_item = item
                        break
                else:
                    return await ctx.send(f"You don't have {bet} to bet (must be ★1 stand or item)!")
            else:
                return await ctx.send(f"You don't have {bet} to bet (must be ★1 stand or item)!")
        else:
            bet_type = "stand"
            bet_item = user_stand["name"]

    # Process the bet
    RARITY_BASE_CHANCE = {
        "Common": 0.30, 
        "Rare": 0.40,  
        "Epic": 0.50,  
        "Legendary": 0.60,
        "mythical": 0.80  
    }

    if bet_type == "stand":
        rarity = get_stand_rarity(bet_item)
        win_chance = RARITY_BASE_CHANCE.get(rarity, 0.50)
    else:
        win_chance = RARITY_BASE_CHANCE["Epic"]

    player_wins = random.random() < win_chance

    # Game animation
    embed = discord.Embed(
        title=f"🎲 D'Arby Accepts Your Bet!",
        description=f"*\"{bet_item}... interesting choice.\"*",
        color=0x4B0082
    )
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(2)

    if player_wins:
        weighted_stands = []
        for stands in part_stands.values():
            for stand_name, stand_data in stands.items():
                if stand_data.get("rollable", True):
                    rarity = stand_data["rarity"]
                    
                    # Custom D'Arby weights
                    darby_weights = {
                        "Common": 5,
                        "Rare": 15,
                        "Epic": 30,
                        "Legendary": 28,
                        "mythical": 8
                    }
                    
                    weight = darby_weights.get(rarity, 0)
                    weighted_stands.extend([(stand_name, stand_data)] * weight)

        won_stand, stand_data = random.choice(weighted_stands)
        user_inventories[user_id].append({"name": won_stand, "stars": 1})
        
        embed = discord.Embed(
            title="✨ You Win! ✨",
            description=f"You keep your {bet_item} and win:",
            color=0x00FF00
        )
        embed.add_field(
            name="Prize",
            value=f"{stand_data.get('emoji', '')} {won_stand} ({stand_data['rarity']})",
            inline=False
        )
        embed.set_image(url=stand_data["image"])
    else:
        if bet_type == "stand":
            user_inventories[user_id].remove(user_stand)
        else:
            remove_item(user_id, bet_item, 1)
        
        embed = discord.Embed(
            title="💀 You Lose! 💀",
            description=f"Your {bet_item} is now D'Arby's property!",
            color=0xFF0000
        )

    await msg.edit(embed=embed)
    save_inventory()
    save_items()

    # Only update cooldown AFTER successful bet processing
    bucket.update_rate_limit()

@darbysoul.error
async def darbysoul_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        await ctx.send("❌ An error occurred. Please try again.")

def get_stand_rarity(stand_name):
    """Helper function to get a stand's rarity from part_stands"""
    normalized_name = normalize_stand_name(stand_name)
    for part in part_stands.values():
        for name, data in part.items():
            if normalize_stand_name(name) == normalized_name:
                return data["rarity"]
    return None

@client.command(name="dm")
@commands.has_permissions(administrator=True)
async def send_dm(ctx, user: discord.User, *, message: str):
    try:
        # Format the DM
        dm_content = f"\n{message}"

        # Print to terminal (with timestamp)
        print(f"\n[DM SENT] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"From: {ctx.author} (Admin)")
        print(f"To: {user} (ID: {user.id})")
        print(f"Content: {message}\n")
        
        # Send the actual DM
        await user.send(dm_content)
        await ctx.send(f"✅ DM sent to {user.name}")
        
    except discord.Forbidden:
        error_msg = f"{user.name} has DMs disabled or blocked the bot"
        print(f"[DM FAILED] {error_msg}")
        await ctx.send(f"❌ {error_msg}")
    except Exception as e:
        error_msg = str(e)
        print(f"[DM ERROR] {error_msg}")
        await ctx.send(f"⚠️ Error: {error_msg}")

class StandCollectionView(discord.ui.View):
    def __init__(self, pages, stand_data, user_id, current_part_index=0, current_page=0):
        super().__init__(timeout=180)
        self.pages = pages
        self.stand_data = stand_data
        self.part_names = list(stand_data.keys())
        self.user_id = user_id
        self.current_part_index = current_part_index
        self.current_page = current_page
        self.update_view()  # Initialize dropdown

    def update_view(self):
        self.clear_items()  # Clear all buttons/dropdowns
        
        current_part_name = self.part_names[self.current_part_index]
        
        # Only add dropdown if there are stands on this page
        if (current_part_name in self.stand_data and 
            self.current_page < len(self.stand_data[current_part_name])):
            stands_on_page = self.stand_data[current_part_name][self.current_page]
            if stands_on_page:
                self.add_item(StandDropdown(stands_on_page, self.user_id))  # Re-add dropdown
        
        # Navigation buttons
        if len(self.part_names) > 1:
            self.add_item(self.prev_part_button)
            self.add_item(self.next_part_button)
        
        if (current_part_name in self.stand_data and 
            len(self.stand_data[current_part_name]) > 1):
            self.add_item(self.prev_page_button)
            self.add_item(self.next_page_button)
            
    @discord.ui.button(label="◄ Part", style=discord.ButtonStyle.grey, row=1)
    async def prev_part_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_part_index = (self.current_part_index - 1) % len(self.part_names)
        self.current_page = 0
        self.update_view()  # Refresh dropdown
        await interaction.response.edit_message(
            embed=self.pages[self.current_part_index * 2],
            view=self
        )

    @discord.ui.button(label="Part ►", style=discord.ButtonStyle.grey, row=1)
    async def next_part_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_part_index = (self.current_part_index + 1) % len(self.part_names)
        self.current_page = 0
        self.update_view()  # Refresh dropdown
        await interaction.response.edit_message(
            embed=self.pages[self.current_part_index * 2],
            view=self
        )

    @discord.ui.button(label="◄ Page", style=discord.ButtonStyle.blurple, row=1)
    async def prev_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_part_name = self.part_names[self.current_part_index]
        if current_part_name in self.stand_data:
            self.current_page = (self.current_page - 1) % len(self.stand_data[current_part_name])
            self.update_view()  # Refresh dropdown
            page_index = (self.current_part_index * 2) + self.current_page
            await interaction.response.edit_message(
                embed=self.pages[page_index],
                view=self
            )

    @discord.ui.button(label="Page ►", style=discord.ButtonStyle.blurple, row=1)
    async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_part_name = self.part_names[self.current_part_index]
        if current_part_name in self.stand_data:
            self.current_page = (self.current_page + 1) % len(self.stand_data[current_part_name])
            self.update_view()  # Refresh dropdown
            page_index = (self.current_part_index * 2) + self.current_page
            await interaction.response.edit_message(
                embed=self.pages[page_index],
                view=self
            )
@client.command(name="stands", aliases=["stand", "standInv"])
async def view_stands(ctx, member: discord.Member = None):
    try:
        if member is None:
            member = ctx.author

        user_id = str(member.id)
        inventory = user_inventories.get(user_id, [])

        if not inventory:
            await ctx.send(f"{member.name} has no stands in their collection.")
            return

        # Group and combine stands
        stand_records = {}
        for stand in inventory:
            if isinstance(stand, dict):
                name = stand["name"]
                stars = stand.get("stars", 1)
            else:
                name = stand
                stars = 1
                if stand in user_inventories[user_id]:
                    user_inventories[user_id].remove(stand)
                    user_inventories[user_id].append({"name": name, "stars": 1})

            if name not in stand_records:
                stand_records[name] = {}
            stand_records[name][stars] = stand_records[name].get(stars, 0) + 1

        # Organize data
        pages = []
        paginated_data = {}
        
        # Check if user has any Skags stands by comparing with all stand names in Skags part
        skags_stand_names = [normalize_stand_name(s) for s in part_stands.get("Part Skags", {}).keys()]
        has_skags = any(
            normalize_stand_name(stand["name"]) if isinstance(stand, dict) else normalize_stand_name(stand) in skags_stand_names
            for stand in inventory
        )

        # Show all parts, including Skags if user has stands from it
        all_parts = []
        for part_name in part_stands.keys():
            if "skags" in part_name.lower():
                if has_skags:
                    all_parts.append(part_name)
            else:
                all_parts.append(part_name)
        
        for part_name in all_parts:
            premium_stands = []
            common_stands = []
            
            for stand_name, stand_data in part_stands[part_name].items():
                if stand_name in stand_records:
                    star_counts = stand_records[stand_name]
                    entry = (stand_name, stand_data, star_counts)
                    if stand_data['rarity'] == "Common":
                        common_stands.append(entry)
                    else:
                        premium_stands.append(entry)
            
            if premium_stands or common_stands:
                part_pages = []
                paginated_data[part_name] = []
                
                # Premium stands page
                if premium_stands:
                    embed = discord.Embed(
                        title=f"{member.name}'s {part_name.split(':')[0]} Premium Stands",
                        color=discord.Color.purple()
                    )
                    
                    # Process each rarity separately
                    for rarity in ["mythical", "Legendary", "Epic", "Rare"]:
                        stands = [s for s in premium_stands if s[1]['rarity'] == rarity]
                        if stands:
                            field_content = []
                            current_length = 0
                            
                            for stand_name, stand_data, star_counts in stands:
                                star_text = " ".join(f"★{l}×{c}" for l,c in sorted(star_counts.items()))
                                line = f"{stand_data.get('emoji', '')} {stand_name} {star_text}"
                                
                                if current_length + len(line) > 900 or len(field_content) >= 10:
                                    embed.add_field(
                                        name=f"**{rarity} Stands**",
                                        value="\n".join(field_content),
                                        inline=False
                                    )
                                    field_content = []
                                    current_length = 0
                                
                                field_content.append(line)
                                current_length += len(line)
                            
                            if field_content:
                                embed.add_field(
                                    name=f"**{rarity} Stands**",
                                    value="\n".join(field_content),
                                    inline=False
                                )
                    
                    part_pages.append(embed)
                    paginated_data[part_name].append(premium_stands)
                
                # Common stands page
                if common_stands:
                    embed = discord.Embed(
                        title=f"{member.name}'s {part_name.split(':')[0]} Commons",
                        color=discord.Color.green()
                    )
                    
                    field_content = []
                    current_length = 0
                    
                    for stand_name, stand_data, star_counts in common_stands:
                        star_text = " ".join(f"★{l}×{c}" for l,c in sorted(star_counts.items()))
                        line = f"{stand_data.get('emoji', '')} {stand_name} {star_text}"
                        
                        if current_length + len(line) > 900 or len(field_content) >= 25:
                            embed.add_field(
                                name="**Common Stands**",
                                value="\n".join(field_content),
                                inline=False
                            )
                            field_content = []
                            current_length = 0
                        
                        field_content.append(line)
                        current_length += len(line)
                    
                    if field_content:
                        embed.add_field(
                            name="**Common Stands**",
                            value="\n".join(field_content),
                            inline=False
                        )
                    
                    part_pages.append(embed)
                    paginated_data[part_name].append(common_stands)
                
                pages.extend(part_pages)

        # Locked parts (excluding Skags if user doesn't have any)
        locked_parts = [
            p for p in part_stands.keys() 
            if p not in paginated_data and 
            (not "skags" in p.lower() or has_skags)
        ]
        
        if locked_parts:
            locked_embed = discord.Embed(
                title="🔒 Locked Parts",
                description="*You haven't discovered any stands from these parts yet!*",
                color=discord.Color.dark_grey()
            )
            
            for i in range(0, len(locked_parts), 10):
                chunk = locked_parts[i:i+10]
                locked_embed.add_field(
                    name="Mysterious Pages",
                    value="\n".join([f"🔐 {p.split(':')[0]}" for p in chunk]),
                    inline=False
                )
            
            pages.append(locked_embed)
            paginated_data["Locked Parts"] = [[]]

        if not pages:
            await ctx.send("No stand data available.")
            return

        # Create and send view
        view = StandCollectionView(pages, paginated_data, ctx.author.id)
        await ctx.send(embed=pages[0], view=view)
        save_inventory()

    except Exception as e:
        print(f"Error in view_stands: {e}")
        traceback.print_exc()
        await ctx.send("An error occurred while processing your request.")

# ===== QUEST CONSTANTS =====
QUEST_RIDDLES = [
    {
        "riddle": "A void that swallows all, leaving nothing but darkness. What is it?",
        "answers": ["cream"],
        "image": ""
    },
    {
        "riddle": "Time's master, the world bends to its will. What is it?",
        "answers": ["the world"],
        "image": ""
    },
    {
        "riddle": "A realm of dreams and terror, where the mind is bound. What is it?",
        "answers": ["death thirteen","death 13","death13"],
        "image": ""
    },
    {
        "riddle": "A warrior’s spirit bound to a blade, unstoppable in its path. What is it?",
        "answers": ["anubis"],
        "image": ""
    },
    {
        "riddle": "Breaks time’s chains with a punch. What is this power?",
        "answers": ["star platinum"],
        "image": ""
    },
    {
        "riddle": "Denies the cards it was dealt, erasing them. Who is it?",
        "answers": ["king crimson"],
        "image": ""
    },
    {
        "riddle": "This spirit is a stand so strong, it defied the very god himself. Who is it?",
        "answers": ["star platinum","weather report","gold experience"],
        "image": ""
    },
    {
        "riddle": "A coin, a bomb, and death in the air. What power is this?",
        "answers": ["killer queen", "bakugo","bites the dust","killer queen bites the dust"],
        "image": ""
    },
    {
        "riddle": "Weaves through time and fate with unseen threads. What is it?",
        "answers": ["hermit purple"],
        "image": ""
    },
    {
        "riddle": "Sky bends to its will, storm and wind obey. What is it?",
        "answers":["weather report"],
        "image": ""
    },
    {
        "riddle": "Space opens up like a jacket",
        "answers": ["sticky fingers"],
        "image": ""
    },
    {
        "riddle": "A dance of steel, swift and silent. What is it?",
        "answers": ["silver chariot"],
        "image": ""
    },
    {
        "riddle": "A door to the mind, its secrets laid bare. What is it?",
        "answers": ["heavens door","heaven's door"],
        "image": ""
    },
]


async def handle_riddle_start(user):
    """Send the first riddle to a participant"""
    user_id = str(user.id)
    if not hasattr(client, 'active_quest') or user_id not in client.active_quest["participants"]:
        return

    user_state = client.active_quest["participants"][user_id]
    
    try:
        dm_channel = await user.create_dm()
        
        # Intro message (only for first riddle)
        if user_state["current_riddle"] == 0:
            intro_embed = discord.Embed(
                title="👁️ A Dark Figure Emerges...",
                description=(
                    "*The air grows heavy as a priest-like figure materializes before you...*\n\n"
                    "*'I am Enrico Pucci... You seek the bone of He Who is Beyond, do you not?'*\n\n"
                    "*'Answer my riddles to prove your knowledge of His essence...'\n"
                    "*'Fail to answer correctly, and you will be deemed unworthy...'*\n\n"
                    "*'Do you understand?'*"
                ),
                color=discord.Color.dark_purple()
            )
            await dm_channel.send(embed=intro_embed)

            def check(m):
                content = m.content.lower().strip()
                return (m.author == user and 
                        isinstance(m.channel, discord.DMChannel) and
                        content in ['yes', 'y', 'yeah', 'yep', 'no', 'n', 'nope'])
            
            try:
                response = await client.wait_for('message', timeout=60.0, check=check)
                response_content = response.content.lower().strip()
                
                if response_content in ['no', 'n', 'nope']:
                    await dm_channel.send("*Pucci shakes his head and disappears into the shadows...*")
                    del client.active_quest["participants"][user_id]
                    return
                
                # Only proceed if answer was positive
                await asyncio.sleep(1)
                
                # Initialize selected_riddles if it doesn't exist
                if "selected_riddles" not in user_state:
                    # Select 5 random unique riddles for this user
                    user_state["selected_riddles"] = random.sample(QUEST_RIDDLES, 5)
                    user_state["current_riddle"] = 0
                
            except asyncio.TimeoutError:
                del client.active_quest["participants"][user_id]
                await dm_channel.send("*Pucci fades into the shadows...*")
                return

        # Make sure selected_riddles exists before trying to access it
        if "selected_riddles" not in user_state:
            return

        # Get current riddle from user's selected riddles
        current_riddle = user_state["selected_riddles"][user_state["current_riddle"]]
        
        # Send current riddle
        embed = discord.Embed(
            title=f"『Trial {user_state['current_riddle'] + 1}』",  # Fixed quote nesting
            description=current_riddle["riddle"],
            color=discord.Color.dark_red()
        )
        if current_riddle["image"]:
            embed.set_image(url=current_riddle["image"])
        embed.set_footer(text="You have 5 minutes to respond.")
        await dm_channel.send(embed=embed)

    except discord.Forbidden:
        print(f"{user.name} has DMs disabled")
        del client.active_quest["participants"][user_id]
    except Exception as e:
        print(f"Error starting riddle: {e}")
        del client.active_quest["participants"][user_id]

@client.event
async def on_message(message):
    if message.author == client.user:
        return
        
    # Only process messages in DMs during an active quest
    if not isinstance(message.channel, discord.DMChannel) or not hasattr(client, 'active_quest'):
        await client.process_commands(message)
        return

    user_id = str(message.author.id)
    
    # Check if user is participating in the quest
    if user_id not in client.active_quest["participants"]:
        await client.process_commands(message)
        return

    # Process the answer
    await handle_riddle_response(message.author, message.content)
    await client.process_commands(message)


async def handle_riddle_response(user, user_answer):
    """Process a user's answer to a riddle"""
    user_id = str(user.id)
    if not hasattr(client, 'active_quest') or user_id not in client.active_quest["participants"]:
        return

    quest = client.active_quest
    user_state = quest["participants"][user_id]
    
    # Skip processing if this is the initial "yes" response
    if user_state["current_riddle"] == 0 and user_answer.lower().strip() in ['yes', 'y', 'yeah', 'yep']:
        return
        
    current_riddle = user_state["selected_riddles"][user_state["current_riddle"]]
    

    
    normalized_answer = normalize_stand_name(user_answer)
    
    # Check against all possible answers
    correct_answers = [normalize_stand_name(ans) for ans in current_riddle["answers"]]
    
    if normalized_answer in correct_answers:
        # Success - progress to next riddle
        user_state["current_riddle"] += 1
        
        # Check if quest complete
        if user_state["current_riddle"] >= len(user_state["selected_riddles"]):
            await complete_quest(user)
        else:
            await send_next_riddle(user)
    else:
        # Fail - wrong answer
        del quest["participants"][user_id]
        await user.send(f"*'Wrong... You were useless afterall'*")

@client.command(name="pucci")
async def spucci(ctx):
    """Talk to Pucci after obtaining Dio's Diary"""
    user_id = str(ctx.author.id)
    load_items()
    
    # Check if user has Dio's Diary
    if get_item_count(user_id, "Dio's Diary") < 1:
        embed = discord.Embed(
            title="Pucci is not interested...",
            description="*'You haven't proven yourself worthy to speak with me yet.'*",
            color=discord.Color.dark_red()
        )
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="Pucci's Update",
        description=random.choice([
            "*'Yo im still working on this feature please go away for now fn!'*",
        ]),
        color=discord.Color.dark_magenta()
    )
    
    await ctx.send(embed=embed)

async def send_next_riddle(user):
    """Send the next riddle in sequence"""
    await handle_riddle_start(user)

async def complete_quest(user):
    """Reward the user for completing all riddles"""
    user_id = str(user.id)
    quest = client.active_quest
    
    # Add reward (Dio's Diary instead of bone)
    add_item(user_id, "Dio's Diary")
    save_items()

    # Send rewards
    dm_channel = await user.create_dm()
    await dm_channel.send("*Pucci hands you a weathered journal...*")
    
    embed = discord.Embed(
        title="📔 Dio's Diary",
        description="This ancient journal contains Dio's research on stands and heaven...",
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text="The command 'Spucci' is now available to you!")
    await dm_channel.send(embed=embed)

    # Announce in channel
    channel = client.get_channel(quest["channel_id"])
    await channel.send(f"🌑 {user.mention} has obtained **[Dio's Diary]**!")

    # Clean up
    del quest["participants"][user_id]

async def quest_timeout(client, channel):
    """Handle quest timeout after 1 hour"""
    await asyncio.sleep(3600)  # 1 hour timeout
    
    if hasattr(client, 'active_quest'):
        try:
            try:
                message = await channel.fetch_message(client.active_quest["message_id"])
                await message.delete()
            except:
                pass
            
            embed = discord.Embed(
                title="The Presence Fades...",
                description="The opportunity has passed... Whatever was here is gone now.",
                color=discord.Color.dark_purple()
            )
            await channel.send(embed=embed)

            del client.active_quest
        except Exception as e:
            print(f"Timeout cleanup failed: {e}")

# ===== QUEST COMMAND =====
@client.command(name="bone")
@commands.is_owner()
async def dio_bone_quest(ctx, channel: discord.TextChannel):
    """Initiate Dio's Bone quest (Owner Only)"""
    if hasattr(client, 'active_quest') and client.active_quest:
        await ctx.send("A quest is already active!")
        return

    try:
        quest_state = {
            "active": True,
            "channel_id": channel.id,
            "message_id": None,
            "participants": {},
            "start_time": datetime.datetime.now().isoformat()
        }

        embed = discord.Embed(
            title="The Earth Trembles...",
            description=(
                "A cold wind blows through the air...\n"
                "Something ancient stirs beneath your feet...\n\n"
                "*React to investigate*"
            ),
            color=discord.Color.dark_red()
        )
        embed.set_footer(text="This event will vanish in 1 hour...")
        
        message = await channel.send(embed=embed)
        await message.add_reaction("❓")
        quest_state["message_id"] = message.id

        client.active_quest = quest_state
        asyncio.create_task(quest_timeout(client, channel))
        await ctx.send(f"✅ Dio's Bone quest initiated in {channel.mention}", delete_after=10)

    except Exception as e:
        print(f"Quest initiation failed: {e}")
        if hasattr(client, 'active_quest'):
            del client.active_quest
        await ctx.send("Failed to start quest!")

# ===== EVENT HANDLER =====
@client.event
async def on_reaction_add(reaction, user):
    """Handle quest participation via reaction"""
    if user.bot or not hasattr(client, 'active_quest'):
        return
    
    if (reaction.message.id == client.active_quest["message_id"] 
        and str(reaction.emoji) == "❓"):
        
        user_id = str(user.id)
        quest = client.active_quest

        # Prevent duplicate participation
        if user_id in quest["participants"]:
            return

        # Initialize user's quest state
        quest["participants"][user_id] = {
            "current_riddle": 0,
            "sacrificed_stands": [],
            "start_time": datetime.datetime.now().isoformat()
        }

        try:
            await reaction.message.remove_reaction("❓", user)
            await handle_riddle_start(user)
        except Exception as e:
            print(f"Reaction handling failed: {e}")
            del quest["participants"][user_id]

# ===== UTILITY FUNCTIONS =====
def normalize_stand_name(name):
    """Normalize stand names for comparison"""
    if not name:
        return ""
    return (name.lower()
            .strip()
            .replace(" ", "")
            .replace("-", "")
            .replace("'", "")
            .replace(".", ""))
@view_stands.error
async def view_stands_error(ctx, error):
    if isinstance(error, commands.UserNotFound):
        await ctx.send("❌ User not found. Please mention a valid server member.")
    elif isinstance(error, commands.CommandInvokeError):
        await ctx.send("❌ An error occurred while displaying stands. Please try again.")
    else:
        await ctx.send(f"❌ An unexpected error occurred: {str(error)}")

@client.command(name="migrateitems")
@commands.is_owner()
async def migrate_items_command(ctx):
    """Admin command to migrate items to the new system"""
    try:
        # Backup files first
        if os.path.exists("user_inventories.json"):
            shutil.copy("user_inventories.json", "user_inventories_backup.json")
        if os.path.exists("user_items.json"):
            shutil.copy("user_items.json", "user_items_backup.json")
            
        await ctx.send("🔄 Starting migration... (Backups created)")
        
        # Run migration
        migrate_items_to_separate_file()
        
        await ctx.send("✅ Migration completed successfully!")
        await ctx.send("Old items have been moved to `user_items.json` and removed from `user_inventories.json`")
    except Exception as e:
        await ctx.send(f"❌ Migration failed: {str(e)}")
        print(f"Migration error: {traceback.format_exc()}")

@daily_reward.error
async def daily_reward_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        remaining_time = round(error.retry_after)
        hours = remaining_time // 3600
        minutes = (remaining_time % 3600) // 60
        seconds = remaining_time % 60

        embed = discord.Embed(
            title="Cooldown Active!",
            description=f"You have already claimed your daily reward.\n⏳ Try again in **{hours}h {minutes}m {seconds}s**.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

# Add to your commands section
@client.command(name="bizarredrop")
async def drop_bizarre_item(ctx):
    # Weird items with descriptions
    bizarre_items = [
        ("Dio's Left Sock", "gross", ""),
        ("Jotaro's Hat (Dented)", "how does it actually fit", ""),
        ("Kakyoin's Cherry", "Did he actually eat these?", ""),
        ("Joseph's Clacker Volley", "the string's wet", ""),
        ("Polnareff's Hair Gel", "Warning: might make you french", ""),
        ("Kira's Severed Hand", "Disconcertingly well-manicured", ""),
        ("Caesar's Bubble Liquid", "80% tears, 20% soap",""),
        ("Shigechi's Leftover Sandwich ", "it's half eaten", ""),
        ("Narancia's Math Homework ", "the answers are wrong", ""),
        ("Green ball ", "smells like mozerella", ""),
        ("Araki's donut ", "still fresh", ""),
    ]
    
    item, desc, gif = random.choice(bizarre_items)
    user_id = str(ctx.author.id)
    
    # Add to inventory using your item system
    add_item(user_id, item)
    
    embed = discord.Embed(
        title="💥 A SPECIAL ITEM APPEARED!",
        description=f"You found **{item}**!\n*{desc}*",
        color=discord.Color.random()
    )
    embed.set_image(url=gif)
    embed.set_footer(text="Check your inventory with Sitems!")
    await ctx.send(embed=embed)

@client.command(name="suggest", aliases=["suggestion"])
@commands.cooldown(1, 900, commands.BucketType.user)  # 15 minutes = 900 seconds
async def suggest(ctx, *, suggestion: str = None):
    """Submit a suggestion for the bot/server (15 minute cooldown)"""
    if not suggestion:
        await ctx.send("Please provide a suggestion. Example: `Ssuggest Add more Stands from Part 6`")
        return
    
    # Get the target channel
    suggestion_channel = client.get_channel()
    if not suggestion_channel:
        await ctx.send("Error: Suggestion channel not found. Please notify the bot owner.")
        return
    
    # Create and send the suggestion embed
    embed = discord.Embed(
        title="New Suggestion",
        description=suggestion,
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    embed.set_author(name=f"Suggested by {ctx.author}", icon_url=ctx.author.avatar.url)
    embed.set_footer(text=f"User ID: {ctx.author.id}")
    
    try:
        await suggestion_channel.send(embed=embed)
        await ctx.send("✅ Your suggestion has been submitted!")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to post in the suggestions channel.")
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")

@suggest.error
async def suggest_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        remaining = int(error.retry_after)
        minutes = remaining // 60
        seconds = remaining % 60
        await ctx.send(f"⌛ You can make another suggestion in {minutes}m {seconds}s.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please provide a suggestion. Example: `Ssuggest Add more Stands from Part 6`")

@smerge.error
async def merge_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please specify a stand to merge. Example: `Smerge Silver Chariot` or `Smerge Silver Chariot 4`")
    elif isinstance(error, commands.CommandError):
        await ctx.send(f"An error occurred during merging: {str(error)}")

allowed_channels = []  # Add channel IDs here

@client.command(name="Smeteor")
@commands.is_owner()
async def smeeteor(ctx, channel_id: int):
    # Fetch the channel object using the provided ID
    target_channel = client.get_channel(channel_id)

    # Error handling: If the channel ID is invalid
    if not target_channel:
        await ctx.send("Error: Invalid channel ID.")
        return

    # Meteor event message
    embed = discord.Embed(
        title="☄️ A Meteor Has Dropped!",
        description="5 shards have emerged\nQuick, grab a shard from the rubble!\n(Event ends in 1 minute)",
        color=discord.Color.red()
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1346247038576361502/1354628118509387957/latest.png?ex=67e5fb3f&is=67e4a9bf&hm=3b9ba247d02fc0c13541bc500d87996bd5868677c7f06a80a8c8af4ee7308a01&")
    message = await target_channel.send(embed=embed)

    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    for emoji in emojis:
        await message.add_reaction(emoji)

    shard_claims = {}  # Stores {user_id: shard_number}
    claimed_shards = set()  # Track claimed shard numbers

    def check(reaction, user):
        shard_number = emojis.index(reaction.emoji) + 1
        return (
            reaction.message.id == message.id
            and reaction.emoji in emojis
            and user.id not in shard_claims
            and shard_number not in claimed_shards  # Check if shard is claimed
            and not user.bot
        )

    async def countdown_timer():
        await asyncio.sleep(60)  # 1-minute timer
        await target_channel.send("⏳ Time's up! No more shards can be claimed.")
        return True  # Signal that the timer ran out

    countdown_task = asyncio.create_task(countdown_timer())
    timeout_expired = False

    try:
        while len(shard_claims) < 5 and not timeout_expired:
            try:
                reaction, user = await client.wait_for("reaction_add", timeout=5.0, check=check)
                shard_number = emojis.index(reaction.emoji) + 1

                # If the shard is already claimed, notify the user and continue
                if shard_number in claimed_shards:
                    await reaction.message.channel.send("This shard is already collected, pick a different one.")
                    continue

                shard_claims[user.id] = shard_number
                claimed_shards.add(shard_number)  # Add shard to claimed set
                await reaction.message.channel.send(f"{user.mention} has picked up shard {shard_number}!")

                if len(shard_claims) == 5:
                    break
            except asyncio.TimeoutError:
                # Check if the countdown timer has finished
                if countdown_task.done():
                    timeout_expired = True
                else:
                    pass  # Just continue waiting if it's a reaction timeout

    finally:
        countdown_task.cancel()  # Ensure the timer is cancelled

    # Determine the "correct" shard
    correct_shard = random.choice(emojis)
    rewarded_user_id = None

    # Check if anyone claimed the correct shard
    for user_id, shard_number in shard_claims.items():
        if emojis[shard_number - 1] == correct_shard:
            rewarded_user_id = user_id
            break

    # Award the arrow fragment if there's a winner
    if rewarded_user_id:
        rewarded_user = await client.fetch_user(int(rewarded_user_id))  # Fetch user object
        user_id = str(rewarded_user.id)

        # Add arrow fragment using the new item system
        add_item(user_id, "arrow_fragment", 1)

        # Get updated fragment count
        fragment_count = get_item_count(user_id, "arrow_fragment")

        embed = discord.Embed(
            title="✨ A Shard's True Nature Revealed!",
            description=f"Shard {emojis.index(correct_shard) + 1} turned out to be an **Arrow Fragment**!\n{rewarded_user.mention} now has **{fragment_count}/5 arrow fragments**!",
            color=discord.Color.gold()
        )
        await target_channel.send(embed=embed)
    else:
        await target_channel.send("None of the claimed shards contained the Arrow Fragment.")

import random

@client.command(name="slime")
async def slime(ctx, user: discord.User):
    # Get the user who invoked the command
    user_slimer = ctx.author

    if user_slimer == user:
        gifs = [
            "https://files.catbox.moe/bwv03g.gif",  # Example gif for self-sliming
            "https://cdn.discordapp.com/attachments/1324906829192495126/1340447825179443251/togif-1.gif?ex=67e5cf51&is=67e47dd1&hm=57dbaa087b13c1ffeb4162109114385a9bad73e8c33090cce15e745094deab02&",

        ]
    else: 
        gifs = [
        "https://tenor.com/view/jojo-gun-jojos-josuke-meme-gif-18019715",  
        "https://tenor.com/view/mista-jojo-gun-regret-death-gif-17232016",
        "https://tenor.com/view/turles-piccolo-gif-24678501",
        "https://tenor.com/view/dragonball-super-broly-anime-movie-frieza-gif-27137981",
        "https://tenor.com/view/minecraft-minecraft-movie-minecraft-meme-minecraft-villager-villager-gif-5342559956921446299",
        "https://tenor.com/view/hoodbender-rdcworld-hoodavatar-hood-avatar-gif-7373043062452024678",
        "https://tenor.com/view/jjk-jjk-s2-jjk-season-2-jujutsu-kaisen-jujutsu-kaisen-s2-gif-7964484372484357392",
        "https://cdn.discordapp.com/attachments/1165306077441695795/1347771617421557770/unnamed_1.webp?ex=67f3ede1&is=67f29c61&hm=1a8672a5963766886de09651f304c9c65ecc23a12aace81bd39f5ad2d3dbd5c4&",
        "https://tenor.com/view/aba-aba-crocodile-gif-27127106",
        "https://tenor.com/view/broly-fighter-z-broly-dbz-level3-dragon-ball-gif-27042589",
    ]

    # Pick a random gif from the pool
    selected_gif = random.choice(gifs)

    # Send the message and the randomly selected gif
    await ctx.send(f"{user.mention} has been slimed by {user_slimer.mention}!\n"
                   "bye bye")
    await ctx.send(selected_gif)

@client.command(name="kiss")
async def slime(ctx, user: discord.User):
    # Get the user who invoked the command
    user_slimer = ctx.author

    if user_slimer == user:
        gifs = [
            "https://files.catbox.moe/bwv03g.gif",  # Example gif for self-sliming
            
        ]
    else: 
        gifs = [
        "https://cdn.discordapp.com/attachments/1358999994983780447/1359001054670229704/lone-and-ken-pfp-update-collab-album-soon-v0-idt9ks75lhte1.png?ex=67f5e3dc&is=67f4925c&hm=f22a917e40629941c4cc031d4bec63a9bc5ac4ff92aa7fd2a36cb903533d732e&"
        "https://tenor.com/view/goro-majima-kazuma-kiryu-yakuza-kiss-gay-love-gender-ryu-ga-gotoku-goro-majima-kiryu-kazuma-yakuza-gay-gif-22218833",
    ]

    # Pick a random gif from the pool
    selected_gif = random.choice(gifs)

    # Send the message and the randomly selected gif
    await ctx.send(f"{user.mention} has been kissed by {user_slimer.mention}!\n"
                   "💗")
    await ctx.send(selected_gif)

@client.command(name="bless")
@commands.is_owner()
async def sbless(ctx, member: discord.Member = None, item: str = "rareRoll", amount: int = 1):
    if not member:
        await ctx.send("Please mention a user to bless. Example: `Sbless @username [item] [amount]`")
        return

    if amount < 1:
        await ctx.send("Invalid amount. Must be at least 1.")
        return

    user_id = str(member.id)
    
    # Define valid blessable items
    valid_items = [
        "rareRoll",
        "epicRoll",
        "Requiem Arrow",
        "arrow_fragment",
        "actStone"
    ]

    # Normalize item name (case-insensitive)
    item_lower = item.lower()
    matched_item = next((i for i in valid_items if i.lower() == item_lower), None)

    if not matched_item:
        await ctx.send(f"Invalid item! Valid items: {', '.join(valid_items)}")
        return

    # Add the item using the new system
    add_item(user_id, matched_item, amount)

    # Confirmation message
    embed = discord.Embed(
        title="🌟 A Blessing Has Been Bestowed!",
        description=f"{member.mention} has received **{amount} {matched_item}(s)** from {ctx.author.mention}!",
        color=discord.Color.gold()
    )
    
    # Add usage hints for special items
    if matched_item == "rareRoll":
        embed.set_footer(text="Use Srollrare to claim your stand!")
    elif matched_item == "epicRoll":
        embed.set_footer(text="Use Srollepic to claim your stand!")
    elif matched_item == "Requiem Arrow":
        embed.set_footer(text="Use Suse requiemarrow [Stand] to awaken Requiem!")
    elif matched_item == "arrow_fragment":
        embed.set_footer(text="Collect 5 to craft a Requiem Arrow (Scraft requiemarrow)")

    await ctx.send(embed=embed)
                
@client.command(name="announce")
@commands.is_owner()  # ✅ Only you (the bot owner) can use this command
async def sannounce(ctx, *, message: str = None):
    if not message:
        await ctx.send("Please provide an announcement message. Example: `Sannounce New update released!`")
        return

    # List of allowed Discord channel IDs
    allowed_channels = [
    ]

    sent_count = 0
    for channel_id in allowed_channels:
        channel = client.get_channel(channel_id)
        if channel:
            await channel.send(f"📢 **Announcement:**\n{message}")
            sent_count += 1

    if sent_count == 0:
        await ctx.send("❌ No valid channels found. Make sure the bot has access to the specified channels.")
    else:
        await ctx.send(f"✅ Announcement sent to {sent_count} channel(s).")


@client.command(name="rollrare", aliases=["rareroll", "rr"])
async def roll_stand_rare(ctx):
    user_id = str(ctx.author.id)
    load_items()  # Load the latest items data

    # Check if the user has a 'rareRoll' in their items
    if get_item_count(user_id, "rareRoll") < 1:
        await ctx.send("You need at least 1 **Rare Roll** to use this command!")
        return

    # Remove the 'rareRoll' from items
    remove_item(user_id, "rareRoll")
    
    # Special weighted chances for the rare roll
    rare_weights = {
        "mythical": 10,
        "Legendary": 30,
        "Epic": 45,
        "Rare": 60,
        "Common": 0
    }

    # Apply rare weights for the roll
    weighted_stands = []
    for stands in part_stands.values():
        for stand_name, stand_data in stands.items():
            if stand_data.get("rollable", True):
                weight = rare_weights.get(stand_data["rarity"], 0)
                weighted_stands.extend([stand_name] * weight)

    # Roll for a stand (using rare weights)
    chosen_stand = random.choice(weighted_stands)

    # Add the stand to the user's inventory (not items!)
    if user_id not in user_inventories:
        user_inventories[user_id] = []
    user_inventories[user_id].append({"name": chosen_stand, "stars": 1})

    # Fetch stand data
    stand_data = next(
        (data for stands in part_stands.values() 
         for name, data in stands.items() if name == chosen_stand),
        None
    )

    if not stand_data:
        await ctx.send(f"Error: Stand data for {chosen_stand} not found.")
        return

    # Rarity progression animation
    rarity_progression = {
        "Rare": discord.Color.blue(),
        "Epic": discord.Color.purple(),
        "Legendary": discord.Color.gold(),
        "mythical": discord.Color.red()
    }

    # Rolling animation
    embed = discord.Embed(
        title=f"{ctx.author.name} is rolling...",
        description="🔄 Rolling for a Stand...",
        color=discord.Color.dark_gray()
    )
    animation_message = await ctx.send(embed=embed)

    for rarity_stage in ["Rare", "Epic", "Legendary", "mythical"]:
        embed.color = rarity_progression[rarity_stage]
        embed.description = f"🎲 Rolling for a Stand... {rarity_stage}"
        await animation_message.edit(embed=embed)
        await asyncio.sleep(0.6)

    # Final embed
    final_embed = discord.Embed(
        title=f"{ctx.author.name} rolled {chosen_stand}!",
        description=f"**Rarity:** {stand_data['rarity']}",
        color=rarity_progression[stand_data["rarity"]]
    )
    final_embed.set_image(url=stand_data["image"])
    final_embed.set_footer(text="Stand rolled successfully!")


    await animation_message.edit(embed=final_embed)
    save_inventory()  # Save the new stand

@client.command(name="rollepic", aliases=["epicroll", "re","er"])
async def roll_stand_epic(ctx):
    user_id = str(ctx.author.id)
    load_items()  # Load the latest items data

    # Check if the user has an 'epicRoll' in their items
    if get_item_count(user_id, "epicRoll") < 1:
        await ctx.send("You need at least 1 **Epic Roll** to use this command!")
        return

    # Remove the 'epicRoll' from items
    remove_item(user_id, "epicRoll")
    
    # Special weighted chances for the epic roll
    epic_weights = {
        "mythical": 20,
        "Legendary": 60,
        "Epic": 80,
        "Rare": 0,
        "Common": 0
    }

    # Apply epic weights for the roll
    weighted_stands = []
    for stands in part_stands.values():
        for stand_name, stand_data in stands.items():
            if stand_data.get("rollable", True):
                weight = epic_weights.get(stand_data["rarity"], 0)
                weighted_stands.extend([stand_name] * weight)

    # Roll for a stand (using epic weights)
    chosen_stand = random.choice(weighted_stands)

    # Add the stand to the user's inventory (not items!)
    if user_id not in user_inventories:
        user_inventories[user_id] = []
    user_inventories[user_id].append({"name": chosen_stand, "stars": 1})

    # Fetch stand data
    stand_data = next(
        (data for stands in part_stands.values() 
         for name, data in stands.items() if name == chosen_stand),
        None
    )

    if not stand_data:
        await ctx.send(f"Error: Stand data for {chosen_stand} not found.")
        return

    # Rarity progression animation
    rarity_progression = {
        "Epic": discord.Color.purple(),
        "Legendary": discord.Color.gold(),
        "mythical": discord.Color.red()
    }

    # Rolling animation
    embed = discord.Embed(
        title=f"{ctx.author.name} is rolling...",
        description="🔄 Rolling for a Stand...",
        color=discord.Color.dark_gray()
    )
    animation_message = await ctx.send(embed=embed)

    for rarity_stage in ["Epic", "Legendary", "mythical"]:
        embed.color = rarity_progression[rarity_stage]
        embed.description = f"🎲 Rolling for a Stand... {rarity_stage}"
        await animation_message.edit(embed=embed)
        await asyncio.sleep(0.6)

    # Final embed
    final_embed = discord.Embed(
        title=f"{ctx.author.name} rolled {chosen_stand}!",
        description=f"**Rarity:** {stand_data['rarity']}",
        color=rarity_progression[stand_data["rarity"]]
    )
    final_embed.set_image(url=stand_data["image"])
    final_embed.set_footer(text="Stand rolled successfully!")

    await animation_message.edit(embed=final_embed)
    save_inventory()  # Save the new stand

# Handle cooldown error message
@roll_stand.error
async def roll_stand_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        remaining_time = round(error.retry_after)
        minutes = remaining_time // 60
        seconds = remaining_time % 60
        await ctx.send(f"Please wait {minutes}m {seconds}s before rolling again.")

class StandImageView(discord.ui.View):
    def __init__(self, stand_name, stand_data, available_stars):
        super().__init__(timeout=180)
        self.stand_name = stand_name
        self.stand_data = stand_data
        self.available_stars = sorted(available_stars)
        self.current_index = 0
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        if len(self.available_stars) > 1:
            if self.current_index > 0:
                self.add_item(self.prev_button)
            if self.current_index < len(self.available_stars) - 1:
                self.add_item(self.next_button)
    
    @discord.ui.button(label="◄", style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_index = max(0, self.current_index - 1)
        await self.update_view(interaction)
    
    @discord.ui.button(label="►", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_index = min(len(self.available_stars) - 1, self.current_index + 1)
        await self.update_view(interaction)
    
    async def update_view(self, interaction: discord.Interaction):
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    def create_embed(self):
        current_star = self.available_stars[self.current_index]
        image_url = self.stand_data['stars'].get(str(current_star), self.stand_data['stars'].get("1"))
        
        embed = discord.Embed(
            title=f"{self.stand_name} ★{current_star}",
            description=f"**Rarity:** {self.stand_data['rarity']}",
            color=discord.Color.purple()
        )
        if image_url:
            embed.set_image(url=image_url)
        return embed

class StandDropdown(discord.ui.Select):
    def __init__(self, stands_on_page, user_id, label="Select Stand"):
        options = []
        used_names = set()
        
        for stand_name, stand_data, star_level in stands_on_page:
            normalized = normalize_stand_name(stand_name)
            if normalized in used_names:
                continue
            used_names.add(normalized)
            
            user_stand = get_user_stand(user_id, stand_name)
            highest_seen = user_stand.get("highest_seen", 1) if user_stand else 1
            options.append(discord.SelectOption(
                label=f"{stand_name} ★{highest_seen}",
                value=f"{stand_name}_{highest_seen}",
                description=f"{stand_data['rarity']} Stand"
            ))

        super().__init__(
            placeholder=label,
            options=options,
            min_values=1,
            max_values=1
        )
        self.stands_on_page = stands_on_page
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        stand_name = self.values[0].split('_')[0]
        stand_data = next(
            (data for part in part_stands.values() 
             for name, data in part.items() if name == stand_name),
            None
        )
        if stand_data:
            user_stand = get_user_stand(self.user_id, stand_name)
            available_stars = sorted({s.get("stars", 1) for s in user_inventories.get(str(self.user_id), []) 
                             if isinstance(s, dict) and normalize_stand_name(s["name"]) == normalize_stand_name(stand_name)})
            view = StandImageView(stand_name, stand_data, available_stars)
            embed = view.create_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

DARBY_STAND = "Osiris" 


def get_stand_rarity(stand_name):
    """Helper function to get a stand's rarity from part_stands"""
    normalized_name = normalize_stand_name(stand_name)
    for part in part_stands.values():
        for name, data in part.items():
            if normalize_stand_name(name) == normalized_name:
                return data["rarity"]
    return None

@client.command(name="craft")
async def scraft(ctx, *args):
    user_id = str(ctx.author.id)
    load_items()  # Load current items

    # Define all valid bizarre items
    ALL_BIZARRE_ITEMS = [
        "Dio's Left Sock",
        "Speedwagon's Scarf",
        "Jotaro's Hat (Dented)",
        "Kakyoin's Cherry",
        "Joseph's Clacker Volley",
        "Polnareff's Hair Gel",
        "Iggy's Coffee Gum",
        "Kira's Severed Hand",
        "Caesar's Bubble Liquid",
        "Shigechi's Leftover Sandwich",
        "Narancia's Math Homework",
        "Green ball", 
        "Araki's donut",
    ]

    crafting_recipes = {
        "requiemarrow": {
            "description": "Combine 5 Arrow Fragments into a Requiem Arrow",
            "requirements": [{"item": "arrow_fragment", "amount": 5}],
            "reward": {"item": "Requiem Arrow", "amount": 1},
            "auto_craft": False
        },
        "actstone": {
            "description": "This stone brings out the latent potential in certain stands",
            "requirements": [{"rarity": "Epic", "stars": 1, "amount": 5}],
            "reward": {"item": "actStone", "amount": 1},
            "auto_craft": False
        },
        "rareroll": {
            "description": "Convert 10 Common stands into a Rare Roll",
            "requirements": [{"rarity": "Common", "stars": 1, "amount": 10}],
            "reward": {"item": "rareRoll", "amount": 1},
            "auto_craft": False
        },
        "epicroll": {
            "description": "Convert 10 Rare stands into an Epic Roll",
            "requirements": [{"rarity": "Rare", "stars": 1, "amount": 10}],
            "reward": {"item": "epicRoll", "amount": 1},
            "auto_craft": False
        },
        "bitesthedust": {
            "description": "Fuse Killer Queen + Stray Cat + Sheer Heart Attack",
            "requirements": [
                {"stand": "Killer Queen", "stars": 1, "amount": 1},
                {"stand": "Stray Cat", "stars": 1, "amount": 1},
                {"stand": "Sheer Heart Attack", "stars": 1, "amount": 1}
            ],
            "reward": {"stand": "Killer Queen: Bites the Dust", "amount": 1},
            "auto_craft": True,
            "cutscene": "https://tenor.com/view/killer-queen-kira-yoshikage-stand-diamond-is-unbreakable-aura-gif-26566253  ",
            "image_url": "https://cdn.discordapp.com/attachments/1348433490269700198/1348797763030093834/image.png?ex=67d0c54e&is=67cf73ce&hm=bbf4c3f39a6159a1c3dd750f2bf749d867dc9304684c18ef325ff9d71da5cae0&"
        },
        "bizarre": {
            "description": "Combine any 5 bizarre items into an Epic Roll",
            "requirements": [],  # Handled specially
            "reward": {"item": "epicRoll", "amount": 1},
            "auto_craft": False
        }
    }

    # Show crafting menu if no args
    if not args:
        embed = discord.Embed(title="⚒️ Crafting Recipes", color=discord.Color.blue())
        for recipe, details in crafting_recipes.items():
            reqs = []
            if recipe == "bizarre":
                reqs.append("5x Any Bizarre Items")
            else:
                for req in details["requirements"]:
                    if "item" in req:
                        reqs.append(f"{req['amount']}x {req['item']}")
                    elif "rarity" in req:
                        reqs.append(f"{req['amount']}x {req['rarity']} (★{req.get('stars', 1)})")
                    else:
                        reqs.append(f"{req['amount']}x {req['stand']} (★{req.get('stars', 1)})")
            
            reward = details["reward"]
            reward_text = f"{reward['amount']}x {reward.get('item', reward.get('stand'))}"
            
            # Add auto-craft indicator
            auto_text = " (Auto-craft)" if details.get("auto_craft", False) else ""
            
            embed.add_field(
                name=f"🔹 {recipe.upper()}{auto_text}",
                value=f"{details['description']}\n**Requires:** {', '.join(reqs)}\n**Reward:** {reward_text}",
                inline=False
            )
        await ctx.send(embed=embed)
        return

    recipe_name = args[0].lower()
    if recipe_name not in crafting_recipes:
        await ctx.send(f"❌ Unknown recipe! Use `Scraft` to see available recipes.")
        return

    recipe = crafting_recipes[recipe_name]
    
    # Handle auto-craft recipes
    if recipe.get("auto_craft", False):
        # Check requirements
        can_craft = True
        for req in recipe["requirements"]:
            if "stand" in req:
                # Check if user has the required stand
                inventory = user_inventories.get(user_id, [])
                stand_count = sum(
                    1 for s in inventory 
                    if isinstance(s, dict) and 
                    s["name"] == req["stand"] and 
                    s.get("stars", 1) == req.get("stars", 1)
                )
                if stand_count < req["amount"]:
                    can_craft = False
                    break

        if not can_craft:
            await ctx.send(f"❌ You don't meet the requirements for {recipe_name}!")
            return

        # Play cutscene if available
        if "cutscene" in recipe:
            cutscene_msg = await ctx.send(recipe["cutscene"])
            await asyncio.sleep(2.833333) 
            await cutscene_msg.delete()

        # Remove required stands
        for req in recipe["requirements"]:
            if "stand" in req:
                removed = 0
                inventory = user_inventories.get(user_id, [])
                for stand in inventory[:]:
                    if (isinstance(stand, dict) and 
                        stand["name"] == req["stand"] and 
                        stand.get("stars", 1) == req.get("stars", 1)):
                        inventory.remove(stand)
                        removed += 1
                        if removed == req["amount"]:
                            break

        # Add reward
        reward = recipe["reward"]
        if "stand" in reward:
            user_inventories[user_id].append({"name": reward["stand"], "stars": 1})
        
        save_inventory()

        # Show result
        embed = discord.Embed(
            title="✨ Crafting Successful!",
            description=f"Created **{reward.get('item', reward.get('stand'))}**",
            color=discord.Color.dark_gold()
        )
        if "image_url" in recipe:
            embed.set_image(url=recipe["image_url"])
        await ctx.send(embed=embed)
        return

    # Check for auto mode
    auto_mode = len(args) > 1 and args[1].lower() == "auto"
    amount = 1
    if len(args) > (2 if auto_mode else 1):
        try:
            amount = max(1, int(args[2 if auto_mode else 1]))
        except ValueError:
            await ctx.send("❌ Invalid amount specified!")
            return

    # Special handling for bizarre recipe
    if recipe_name == "bizarre":
        # Count ALL bizarre items (trim whitespace for comparison)
        bizarre_items_in_inventory = []
        for item_name, count in user_items.get(user_id, {}).items():
            normalized_name = item_name.strip()
            if normalized_name in [i.strip() for i in ALL_BIZARRE_ITEMS]:
                bizarre_items_in_inventory.append((item_name, count))  # Keep original name for removal
        
        total_bizarre = sum(count for (_, count) in bizarre_items_in_inventory)
        
        if total_bizarre < 5 * amount:
            await ctx.send(
                f"❌ You need {5 * amount} bizarre items (you have {total_bizarre}).\n"
                f"Valid items: {', '.join(ALL_BIZARRE_ITEMS)}"
            )
            return
        
        # Remove items (using original names)
        removed = 0
        needed = 5 * amount
        for item_name, count in bizarre_items_in_inventory:
            while count > 0 and removed < needed:
                remove_item(user_id, item_name)  # Remove using original name
                removed += 1
                count -= 1
                if removed == needed:
                    break
        
        # Add reward
        add_item(user_id, "epicRoll", amount)
        
        embed = discord.Embed(
            title="✨ Bizarre Recycling Complete! ✨",
            description=f"Converted {needed} junk items into something useful!",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="Reward",
            value=f"**Epic Roll** ×{amount}\nUse with `Srollepic` for guaranteed Epic+ stands!",
            inline=False
        )
        await ctx.send(embed=embed)
        save_items()
        return

    # Normal recipe handling
    required_total = sum(req["amount"] for req in recipe["requirements"]) * amount

    # AUTO MODE - Use lowest star stands first
    if auto_mode:
        used_stands = []
        can_craft = True

        for req in recipe["requirements"]:
            needed = req["amount"] * amount
            count = 0

            # Handle item requirements
            if "item" in req:
                available = get_item_count(user_id, req["item"])
                if available < needed:
                    can_craft = False
                    break

            # Handle stand requirements
            else:
                inventory = user_inventories.get(user_id, [])
                stands = [
                    s for s in inventory 
                    if isinstance(s, dict) and 
                    (("stand" in req and s["name"] == req["stand"]) or
                     ("rarity" in req and get_stand_rarity(s["name"]) == req["rarity"])) and
                    s.get("stars", 1) == req.get("stars", 1)
                ]
                
                if len(stands) < needed:
                    can_craft = False
                    break
                
                used_stands.extend(stands[:needed])

        if not can_craft:
            await ctx.send(f"❌ Not enough materials for {amount}x {recipe_name}!")
            return

        # Remove used items/stands
        for req in recipe["requirements"]:
            if "item" in req:
                remove_item(user_id, req["item"], req["amount"] * amount)
            else:
                for stand in used_stands[:req["amount"] * amount]:
                    if stand in user_inventories.get(user_id, []):
                        user_inventories[user_id].remove(stand)
                used_stands = used_stands[req["amount"] * amount:]

        # Add reward
        reward = recipe["reward"]
        if "item" in reward:
            add_item(user_id, reward["item"], reward["amount"] * amount)
        else:
            for _ in range(reward["amount"] * amount):
                user_inventories[user_id].append({"name": reward["stand"], "stars": 1})

        save_inventory()
        await ctx.send(f"✅ Successfully crafted {amount}x {recipe_name}!")
        return

    # MANUAL MODE - Interactive selection
    selected_materials = []
    selection_msg = None

    embed = discord.Embed(
        title=f"Crafting: {recipe_name} x{amount}",
        description=f"Select materials (type `done` when ready or `cancel` to abort)\n"
                   f"Format: `standname` or `itemname`",
        color=discord.Color.orange()
    )
    
    # Show requirements
    req_text = []
    for req in recipe["requirements"]:
        if "item" in req:
            req_text.append(f"{req['amount'] * amount}x {req['item']}")
        elif "stand" in req:
            req_text.append(f"{req['amount'] * amount}x {req['stand']} (★{req.get('stars', 1)})")
        else:
            req_text.append(f"{req['amount'] * amount}x {req['rarity']} (★{req.get('stars', 1)})")
    
    embed.add_field(name="Requirements", value="\n".join(req_text), inline=False)
    selection_msg = await ctx.send(embed=embed)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    while len(selected_materials) < required_total:
        try:
            msg = await client.wait_for("message", check=check, timeout=60)
            content = msg.content.lower()

            if content == "cancel":
                await selection_msg.delete()
                await ctx.send("❌ Crafting cancelled.")
                return
            elif content == "done":
                if len(selected_materials) >= required_total:
                    break
                await ctx.send(f"⚠️ You still need {required_total - len(selected_materials)} more materials!")
                continue

            # Find matching item or stand
            found = None
            if any(req.get("item") for req in recipe["requirements"]):
                for item in user_items.get(user_id, {}):
                    if item.lower() == content:
                        found = item
                        break

            if not found:  # Check stands
                for stand in user_inventories.get(user_id, []):
                    if isinstance(stand, dict) and stand["name"].lower() == content:
                        found = stand
                        break

            if not found:
                await ctx.send(f"❌ You don't have {content}!")
                continue

            # Verify it meets recipe requirements
            valid = False
            for req in recipe["requirements"]:
                if "item" in req and isinstance(found, str) and found == req["item"]:
                    valid = True
                    break
                elif isinstance(found, dict):
                    if "stand" in req and found["name"] == req["stand"] and found.get("stars", 1) == req.get("stars", 1):
                        valid = True
                        break
                    elif "rarity" in req and get_stand_rarity(found["name"]) == req["rarity"] and found.get("stars", 1) == req.get("stars", 1):
                        valid = True
                        break

            if not valid:
                await ctx.send(f"❌ {found['name'] if isinstance(found, dict) else found} doesn't match requirements!")
                continue

            selected_materials.append(found)
            remaining = max(0, required_total - len(selected_materials))
            
            # Update selection message
            counts = {}
            for mat in selected_materials:
                name = mat["name"] if isinstance(mat, dict) else mat
                counts[name] = counts.get(name, 0) + 1
            
            selected_text = "\n".join([f"{name} ×{count}" for name, count in counts.items()])
            embed.set_field_at(
                0,
                name=f"Selected ({len(selected_materials)}/{required_total})",
                value=selected_text,
                inline=False
            )
            await selection_msg.edit(embed=embed)

        except asyncio.TimeoutError:
            await ctx.send("⌛ Crafting timed out.")
            return

    # Perform crafting
    for mat in selected_materials:
        if isinstance(mat, str):  # Item
            remove_item(user_id, mat, 1)
        else:  # Stand
            if mat in user_inventories.get(user_id, []):
                user_inventories[user_id].remove(mat)

    # Add reward
    reward = recipe["reward"]
    if "item" in reward:
        add_item(user_id, reward["item"], reward["amount"] * amount)
    else:
        for _ in range(reward["amount"] * amount):
            user_inventories[user_id].append({"name": reward["stand"], "stars": 1})

    save_inventory()

    # Show result
    reward_name = reward.get("item", reward.get("stand"))
    embed = discord.Embed(
        title="✨ Crafting Successful!",
        description=f"Created **{reward_name} ×{reward['amount'] * amount}**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@client.command(name="use")
async def suse(ctx, item_name: str = None, *stand_name_parts):
    user_id = str(ctx.author.id)
    load_items()  # Ensure fresh item data
    
    if not item_name:
        embed = discord.Embed(
            title="Usage Guide",
            description="`Suse <item> <stand>`\n\nAvailable items:\n"
                       "- `actstone` (Echoes/Tusk Acts)\n"
                       "- `requiemarrow` (Gold Experience/Silver Chariot)",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return

    item_name = item_name.lower()
    stand_name = " ".join(stand_name_parts).strip()
    stand_name_cleaned = stand_name.replace(" ", "").lower()

    # Act Upgrade Paths
    act_upgrades = {
        "echoesact1": {
            "new_stand": "Echoes Act2",
            "gif_url": "https://cdn.discordapp.com/attachments/1353096163410055170/1353826415337799851/UntitledProject-ezgif.com-cut.gif",
            "image_url": "https://media.discordapp.net/attachments/1348433490269700198/1349369860349493299/image.png"
        },
        "echoesact2": {
            "new_stand": "Echoes Act3",
            "gif_url": "https://tenor.com/view/okay-jojo-jjba-dui-part4-gif-13897254",
            "image_url": "https://media.discordapp.net/attachments/1348433490269700198/1349370095909994540/image.png"
        },
        "tuskact1": {
            "new_stand": "Tusk ACT2",
            "gif_url": "https://example.com/tusk1to2.gif",
            "image_url": "https://example.com/tusk2.png"
        },
        # Add other act upgrades here
    }

    # Requiem Upgrade Paths
    requiem_upgrades = {
        "goldexperience": {
            "new_stand": "Gold Experience Requiem",
            "gif_url": "https://tenor.com/view/jojo-jo-jos-adventurebizarre-giorno-giovanna-golden-wind-gold-experience-gif-14487899",
            "image_url": "https://media.discordapp.net/attachments/1353096163410055170/1353098891452612658/image.png"
        },
        "silverchariot": {
            "new_stand": "Silver Chariot Requiem",
            "gif_url": "https://cdn.discordapp.com/attachments/1353096163410055170/1353163280553873449/UntitledProject-ezgif.com-optimize.gif",
            "image_url": "https://cdn.discordapp.com/attachments/1353096163410055170/1353162556805746688/image.png"
        }
    }

    # Act Stone Usage
    if item_name == "actstone":
        if stand_name_cleaned not in act_upgrades:
            await ctx.send(f"❌ {stand_name} cannot be upgraded with an Act Stone!")
            return

        if get_item_count(user_id, "actStone") < 1:
            await ctx.send("❌ You don't have an Act Stone!")
            return

        user_stand = get_user_stand(user_id, stand_name)
        if not user_stand:
            await ctx.send(f"❌ You don't have {stand_name} in your inventory!")
            return

        # Show transformation GIF
        gif_msg = await ctx.send(act_upgrades[stand_name_cleaned]["gif_url"])
        await asyncio.sleep(5)
        await gif_msg.delete()

        # Perform upgrade
        remove_item(user_id, "actStone", 1)
        user_inventories[user_id].remove(user_stand)
        new_stand = {"name": act_upgrades[stand_name_cleaned]["new_stand"], "stars": 1}
        user_inventories[user_id].append(new_stand)
        save_inventory()

        # Show result
        embed = discord.Embed(
            title=f"✨ {stand_name} has evolved!",
            description=f"Into **{new_stand['name']}**!",
            color=discord.Color.gold()
        )
        embed.set_image(url=act_upgrades[stand_name_cleaned]["image_url"])
        await ctx.send(embed=embed)

    # Requiem Arrow Usage
    elif item_name == "requiemarrow":
        if stand_name_cleaned not in requiem_upgrades:
            await ctx.send(f"❌ {stand_name} cannot become Requiem!")
            return

        if get_item_count(user_id, "Requiem Arrow") < 1:
            await ctx.send("❌ You don't have a Requiem Arrow!")
            return

        user_stand = get_user_stand(user_id, stand_name)
        if not user_stand:
            await ctx.send(f"❌ You don't have {stand_name}!")
            return

        # Show transformation GIF
        gif_msg = await ctx.send(requiem_upgrades[stand_name_cleaned]["gif_url"])
        await asyncio.sleep(5)
        await gif_msg.delete()

        # Perform upgrade
        remove_item(user_id, "Requiem Arrow", 1)
        user_inventories[user_id].remove(user_stand)
        new_stand = {"name": requiem_upgrades[stand_name_cleaned]["new_stand"], "stars": 1}
        user_inventories[user_id].append(new_stand)
        save_inventory()

        # Show result
        embed = discord.Embed(
            title=f"🌟 {stand_name} has awakened!",
            description=f"**{new_stand['name']}** has been obtained!",
            color=discord.Color.gold()
        )
        embed.set_image(url=requiem_upgrades[stand_name_cleaned]["image_url"])
        await ctx.send(embed=embed)

    else:
        await ctx.send(f"❌ Unknown item: {item_name}")

@client.command(name="items", aliases=["inv", "inventory"])
async def sitems(ctx):
    user_id = str(ctx.author.id)
    load_items()  # Ensure we have fresh data
    
    if user_id not in user_items or not user_items[user_id]:
        await ctx.send("You have no items in your inventory.")
        return

    item_descriptions = {
        "rareRoll": "Use with `Srollrare` for guaranteed Rare+ stand",
        "epicRoll": "Use with `Srollepic` for guaranteed Epic+ stand",
        "Requiem Arrow": "Use with `Suse requiemarrow [Stand]` to awaken Requiem",
        "arrow_fragment": "Collect 5 to craft a Requiem Arrow (`Scraft requiemarrow`)",
        "actStone": "Use with `Suse actstone [Stand]` to upgrade certain stands"
    }

    embed = discord.Embed(
        title=f"{ctx.author.name}'s Items",
        color=discord.Color.blue()
    )
    
    for item, count in user_items[user_id].items():
        embed.add_field(
            name=f"×{count} {item}",
            value=item_descriptions.get(item, "No description available"),
            inline=False
        )

    await ctx.send(embed=embed)\
    
def add_to_inventory(user_id, stand_data):
    if user_id not in user_inventories:
        user_inventories[user_id] = []
    
    # Track highest seen stars for each stand
    stand_name = stand_data["name"]
    new_stars = stand_data.get("stars", 1)
    
    # Check if we already have this stand recorded
    existing = next((s for s in user_inventories[user_id] if isinstance(s, dict) and s["name"] == stand_name), None)
    
    if existing:
        # Update highest seen stars if this is higher
        existing["highest_seen"] = max(existing.get("highest_seen", 1), new_stars)
    else:
        # Add new entry with highest seen
        stand_data["highest_seen"] = new_stars
        user_inventories[user_id].append(stand_data)
    
    save_inventory()


@client.event
async def on_ready():
    load_inventory()  # For stands
    load_items()     # For items
    await client.change_presence(activity=discord.Game(name="Sroll for stands!"))
    print(f"{client.user} is now running!")

def migrate_items_to_separate_file():
    """Migrate items from user_inventories.json to user_items.json"""
    # Load existing data
    load_inventory()  # Loads user_inventories.json
    load_items()      # Loads user_items.json (empty initially)
    
    # Define all valid items that should be moved
    valid_items = [
        "rareRoll",
        "epicRoll",
        "Requiem Arrow",
        "arrow_fragment",
        "actStone"
    ]
    
    migrated_count = 0
    
    for user_id, inventory in user_inventories.items():
        # Create a new inventory without items
        new_inventory = []
        
        for entry in inventory:
            if isinstance(entry, str) and entry in valid_items:
                # Add to items system
                add_item(user_id, entry)
                migrated_count += 1
            elif isinstance(entry, dict) and entry["name"] in valid_items:
                # Handle case where items were stored as stands
                add_item(user_id, entry["name"])
                migrated_count += 1
            else:
                # Keep in stands inventory
                new_inventory.append(entry)
        
        # Update the inventory
        user_inventories[user_id] = new_inventory
    
    # Save both files
    save_inventory()
    save_items()
    
    print(f"✅ Migration complete! Moved {migrated_count} items to the new system.")

def main():
    client.run(TOKEN)

if __name__ == '__main__':
    main()
