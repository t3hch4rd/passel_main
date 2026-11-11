import os
from random import randrange
import discord
from discord.ext import commands

# --- CONFIGURATION ---
MAX_PINS = 250  # Modern discord.py handles up to 250 natively
MODE = 2        # 1 = archive newest pin, 2 = archive oldest pin
SEND_ALL = 0    # 1 = archive every pin immediately, 0 = only archive at MAX_PINS
PINS_CHANNEL_ID = int(os.environ.get('CHANNEL', 0))
BLACKLISTED_CHANNELS = []  # Add integer channel IDs here if needed (e.g., [123456789])

EMBED_COLORS = [
    discord.Colour.magenta(), discord.Colour.blurple(), discord.Colour.dark_teal(),
    discord.Colour.blue(), discord.Colour.dark_blue(), discord.Colour.dark_gold(),
    discord.Colour.dark_green(), discord.Colour.dark_grey(), discord.Colour.dark_magenta(),
    discord.Colour.dark_orange(), discord.Colour.dark_purple(), discord.Colour.dark_red(),
    discord.Colour.darker_grey(), discord.Colour.gold(), discord.Colour.green(),
    discord.Colour.greyple(), discord.Colour.orange(), discord.Colour.purple(),
]

# --- BOT INITIALIZATION ---
intents = discord.Intents.default()
intents.message_content = True  # Required for p.pins and p.settings commands

client = commands.Bot(command_prefix='p.', case_insensitive=True, intents=intents)
client.remove_command("help")

@client.event
async def on_ready():
    print(f'Logged in as {client.user} (discord.py v{discord.__version__})')

# --- COMMANDS ---
@client.command(name='pins')
async def pins(ctx):
    """Troubleshooting command to verify the bot sees all 250 pins."""
    current_pins = [msg async for msg in ctx.channel.pins(limit=None)]
    await ctx.send(f"{ctx.channel.mention} currently has **{len(current_pins)}** pins.")

@client.command(name='settings')
@commands.has_permissions(administrator=True)
async def settings(ctx):
    archive_chan = ctx.guild.get_channel(PINS_CHANNEL_ID)
    chan_mention = archive_chan.mention if archive_chan else "Not Found (Check CHANNEL env var)"
    await ctx.send(
        f"**Mode:** {MODE}\n"
        f"**Send All:** {SEND_ALL}\n"
        f"**Archive Channel:** {chan_mention}"
    )

# --- HELPER FUNCTION ---
async def archive_and_unpin(message, archive_channel, unpin=True):
    """Builds the embed, sends it to the archive channel, and unpins the original."""
    color = EMBED_COLORS[randrange(len(EMBED_COLORS))]
    
    # Only show [No text content] if there is literally no text AND no attachments/embeds
    has_media = bool(message.attachments or message.embeds)
    desc = f'"{message.content}"' if message.content else ("" if has_media else "*[No text content]*")
    
    embed = discord.Embed(description=desc, colour=color)
    
    # 1. grab the first uploaded attachment
    first_file = next(iter(message.attachments), None)
    first_embed = next(iter(message.embeds), None)

    if first_file:
        # Check by file extension so it works even if content_type is missing
        if first_file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            embed.set_image(url=first_file.url)
        else:
            embed.add_field(name="Attachment", value=f"[{first_file.filename}]({first_file.url})", inline=False)
            
    # 2. Fallback: Check if the pinned message was a pasted image/GIF link
    elif first_embed:
        if first_embed.image:
            embed.set_image(url=first_embed.image.url)
        elif first_embed.thumbnail:
            embed.set_image(url=first_embed.thumbnail.url)

    embed.add_field(name="Jump", value=message.jump_url, inline=False)
    embed.set_footer(text=f"Sent in #{message.channel.name} • {message.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
    embed.set_author(name=f"Sent by {message.author.display_name}", icon_url=message.author.display_avatar.url)

    await archive_channel.send(embed=embed)
    
    if unpin:
        await message.channel.send(f"Archived oldest pinned message to {archive_channel.mention}.")
        await message.unpin()
    else:
        await message.channel.send(f"Mirrored pinned message to {archive_channel.mention}.")

# --- MAIN PIN LISTENER ---
@client.event
async def on_guild_channel_pins_update(channel, last_pin):
    # Ignore blacklisted channels or the archive channel itself
    if channel.id in BLACKLISTED_CHANNELS or channel.id == PINS_CHANNEL_ID:
        return

    archive_channel = channel.guild.get_channel(PINS_CHANNEL_ID)
    if not archive_channel:
        print(f"Error: Archive channel {PINS_CHANNEL_ID} not found in guild {channel.guild.name}.")
        return

    try:
        current_pins = [msg async for msg in channel.pins(limit=None)]
        pin_count = len(current_pins)

        # Send-all mode
        if SEND_ALL == 1 and pin_count < (MAX_PINS - 1):
            await archive_and_unpin(current_pins[0], archive_channel, unpin=False)
            return

        # Standard overflow modes (triggered when hitting MAX_PINS)
        if pin_count >= MAX_PINS:
            if MODE == 1:
                # current_pins[0] is the newest pin
                await archive_and_unpin(current_pins[0], archive_channel, unpin=True)
            elif MODE == 2:
                # current_pins[-1] is the oldest pin
                await archive_and_unpin(current_pins[-1], archive_channel, unpin=True)

    except discord.Forbidden:
        print(f"Permission Error: Missing 'Pin Messages' or 'Manage Messages' permission in #{channel.name}.")
    except Exception as e:
        print(f"Unexpected error processing pin update in #{channel.name}: {e}")

client.run(os.environ.get('TOKEN'))
