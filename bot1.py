import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv
import ctypes.util

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Set ffmpeg path (make sure start.sh downloads it)
FFMPEG_PATH = os.path.join(os.getcwd(), "ffmpeg")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Opus load check ---
if not discord.opus.is_loaded():
    try:
        opus_lib = ctypes.util.find_library("opus")
        if opus_lib:
            discord.opus.load_opus(opus_lib)
            print(f"✅ Loaded Opus from: {opus_lib}")
        else:
            raise RuntimeError("Opus library not found.")
    except Exception as e:
        print(f"❌ Could not load Opus library: {e}")

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'cachedir': False,
    'source_address': '0.0.0.0',
    'cookiefile': 'cookies.txt'
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            raise Exception("Playlists are not supported. Please use a single video URL.")

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, executable=FFMPEG_PATH, **FFMPEG_OPTIONS), data=data)

@bot.command(name='join', help='Tells the bot to join the voice channel')
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("You are not connected to a voice channel.")
        return
    try:
        await ctx.author.voice.channel.connect()
    except Exception as e:
        await ctx.send(f"❌ Could not join voice channel: {e}")

@bot.command(name='leave', help='Make the bot leave the voice channel')
async def leave(ctx):
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_connected():
        await ctx.send("Bye 😢")
        await voice_client.disconnect()
    else:
        await ctx.send("I'm not in a voice channel.")

@bot.command(name='play', help='Play a song from a YouTube URL')
async def play(ctx, url: str):
    voice_client = ctx.guild.voice_client

    if not voice_client:
        if ctx.author.voice:
            try:
                voice_client = await ctx.author.voice.channel.connect()
            except Exception as e:
                await ctx.send(f"❌ Could not join voice channel: {e}")
                return
        else:
            await ctx.send("You are not connected to a voice channel.")
            return

    if voice_client.is_playing():
        voice_client.stop()

    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)}")
            return

        voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
        await ctx.send(f'🎶 Now playing: *{player.title}*')

@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and before.channel is not None and after.channel is None:
        for text_channel in before.channel.guild.text_channels:
            if text_channel.permissions_for(before.channel.guild.me).send_messages:
                await text_channel.send("Bye 😢 I was disconnected from the voice channel.")
                break

bot.run(DISCORD_TOKEN)
