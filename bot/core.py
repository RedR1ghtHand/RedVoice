import logging
import random
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

import settings
from database import SessionManager
from database.connection import db
from database.models import Session
from utils import get_message

from .ui.views import ChannelControlView

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.presences = True  
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
session_manager = SessionManager(db)

temporary_channels: set[int] = set()

ALLOWED_GUILDS = settings.ALLOWED_GUILDS


@bot.event
async def on_guild_join(guild):
    if guild.id not in ALLOWED_GUILDS:
        logging.info(f"Bot joined unauthorized guild: {guild.name} (ID: {guild.id})")
        logging.info(f"Leaving guild: {guild.name}")
        await guild.leave()
        return
    
    logging.info(f"Bot joined authorized guild: {guild.name} (ID: {guild.id})")


@bot.event
async def on_ready():
    global temporary_channels
    logging.info(f"Bot is ready! Logged in as {bot.user}")
    logging.info(f"Currently registered commands: {len(tree.get_commands())}")
    try:
        synced = await tree.sync()
        logging.info(f"Synced {len(synced)} slash command(s) with Discord globally. Command tree: {tree.get_commands()}")
    except Exception as e:
        logging.error(f"Failed to sync slash commands globally: {e}")

    # Guild-specific sync so new commands show up immediately (global sync can take up to 1 hour)
    for guild in bot.guilds:
        if guild.id in ALLOWED_GUILDS:
            try:
                await tree.sync(guild=guild)
                logging.info(f"Synced command tree to guild {guild.name} ({guild.id})")
            except Exception as e:
                logging.error(f"Failed to sync to guild {guild.name}: {e}")

    active_sessions = await session_manager.get_active_sessions()
    temporary_channels.clear()
    temporary_channels.update(item["session"].channel_id for item in active_sessions)
    for item in active_sessions:
        session = item["session"]
        created_by = item["created_by"]
        channel = bot.get_channel(session.channel_id)
        if channel is not None:
            owner = None
            if channel.guild and created_by:
                owner = channel.guild.get_member_named(created_by)
            bot.add_view(ChannelControlView(channel, owner=owner, session_manager=session_manager))
    if active_sessions:
        logging.info(f"Restored {len(active_sessions)} active session(s) into temporary_channels and re-added ChannelControlViews")

    for guild in bot.guilds:
        if guild.id not in ALLOWED_GUILDS:
            logging.info(f"Found unauthorized guild: {guild.name} (ID: {guild.id})")
            logging.info(f"Leaving guild: {guild.name}")
            await guild.leave()
        else:
            logging.info(f"Authorized guild: {guild.name} (ID: {guild.id})")


@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id in settings.CREATE_CHANNEL_IDS:
        logging.info(f"{member} joined the create channel. Creating new VC...")
        guild = member.guild
        category = after.channel.category

        new_channel = await guild.create_voice_channel(
            name=random.choice(settings.DEFAULT_CHANNEL_NAMES),
            category=category,
            reason="Auto-created private channel"
        )
        temporary_channels.add(new_channel.id)

        await session_manager.start_session(
            created_by=str(member.name),
            channel_name=new_channel.name,
            channel_id=new_channel.id,
            creator_metadata={
                "public_name": member.display_name,
                "username": member.name,
                "avatar_url": member.display_avatar.url,
            }
        )

        await member.move_to(new_channel)

        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=1))

        try:
            color = getattr(discord.Color, get_message("embeds.private_voice.color"))()
            
            embed = discord.Embed(
                title=get_message("embeds.private_voice.title"),
                description=get_message("embeds.private_voice.description", mention=member.mention),
                color=color
            )

            for field in get_message("embeds.private_voice.fields"):
                embed.add_field(name=field["name"], value=field["value"], inline=True)

            embed.set_footer(
                text=get_message("embeds.private_voice.footer", display_name=member.display_name),
                icon_url=member.display_avatar.url
                )
            embed.timestamp = discord.utils.utcnow()

            await new_channel.send(embed=embed,view=ChannelControlView(new_channel, member, session_manager))
            logging.info(f"Sent control panel embed to {new_channel.name}")
        except Exception as e:
            logging.error(f"Failed to send control panel message to {new_channel.id}: {e}")

    if before.channel and before.channel != after.channel:
        if before.channel.id not in settings.CREATE_CHANNEL_IDS:
            await session_manager.update_session(before.channel.id)

            if before.channel.id in temporary_channels and len(before.channel.members) == 0:
                await session_manager.update_and_end_session(before.channel.id)
                logging.info(F"Session '{before.channel.name}' ended. Entry saved to the database")
                await before.channel.delete(reason="Temporary VC empty")
                temporary_channels.remove(before.channel.id)



@tree.command(name="top", description="Show top sessions sorted by duration")
async def top_sessions(interaction: discord.Interaction, limit: int = 10):
    limit = limit if limit <= 10 else 10
    sessions = await session_manager.longest_sessions_all_time(limit=limit)

    title_template = get_message("embeds.top.title", limit=limit)
    color_name = get_message("embeds.top.color")
    no_sessions_text = get_message("embeds.top.no_sessions")
    medals = get_message("embeds.top.medals")

    if not sessions:
        await interaction.response.send_message(no_sessions_text)
        return

    color = getattr(discord.Color, color_name, discord.Color.red)()
    embed = discord.Embed(
        title=title_template.format(limit=limit),
        color=color
    )

    lines = []

    for i, session in enumerate(sessions, start=1):
        duration = session.duration_pretty()
        meta = session.creator_metadata or {}
        username = meta.get("public_name") or session.created_by

        if i <= 3:
            line = f"{medals[i - 1]} **{session.channel_name}** *by* {username}\n⏱️ `{duration}`"
        else:
            line = f"{i}. **{session.channel_name}** *by* {username}\n⏱️ `{duration}`"

        lines.append(line)

    if len(lines) > 3:
        top_three = "\n\n".join(lines[:3])
        others = "\n".join(lines[3:])
        description = f"{top_three}\n\n{others}"
    else:
        description = "\n\n".join(lines)

    embed.description = description

    await interaction.response.send_message(embed=embed)


@tree.command(name="clean-up-short-sessions", description="Clean up short sessions")
@app_commands.checks.has_permissions(administrator=True)
async def clean_up_short_sessions(interaction: discord.Interaction, treshhold: int):
    deleted_count = await session_manager.clean_up_short_sessions(treshhold=treshhold)

    if not deleted_count:
        await interaction.response.send_message(f"No sessions shorter than **{treshhold}**seconds found")
    else:
        await interaction.response.send_message(f"Cleaned up **{deleted_count}** sessions shorter than **{treshhold}**seconds")


@tree.command(name="clean-up-active-sessions", description="Close empty temporary voice channels and save their sessions")
@app_commands.checks.has_permissions(administrator=True)
async def clean_up_active_sessions(interaction: discord.Interaction):
    global temporary_channels
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    empty_temporary = [
        ch for ch in guild.voice_channels
        if ch.id in temporary_channels and len(ch.members) == 0
    ]
    closed = 0
    for ch in empty_temporary:
        await session_manager.update_and_end_session(ch.id)
        logging.info(f"Session '{ch.name}' ended via clean-up. Entry saved to the database")
        await ch.delete(reason="Clean-up: temporary VC empty")
        temporary_channels.discard(ch.id)
        closed += 1

    if closed == 0:
        await interaction.response.send_message("No empty temporary voice channels to close.")
    else:
        await interaction.response.send_message(f"Closed **{closed}** empty temporary channel(s) and saved their sessions.")


@tree.command(name="clean-up-db-sessions", description="End DB sessions that still have is_ended=False but their voice channel no longer exists")
@app_commands.checks.has_permissions(administrator=True)
async def clean_up_db_sessions(interaction: discord.Interaction):
    global temporary_channels
    active = await session_manager.get_active_sessions()
    broken = [
        item["session"] for item in active
        if bot.get_channel(item["session"].channel_id) is None
    ]
    cleaned = 0
    for session in broken:
        await session_manager.update_and_end_session(session.channel_id)
        temporary_channels.discard(session.channel_id)
        logging.info(f"Broken session '{session.channel_name}' (channel_id={session.channel_id}) marked ended.")
        cleaned += 1

    if cleaned == 0:
        await interaction.response.send_message("No broken sessions found.")
    else:
        await interaction.response.send_message(f"Cleaned up **{cleaned}** broken session(s) (channel no longer exists, entry saved and marked ended).")


def run_bot():
    bot.run(settings.BOT_TOKEN)
