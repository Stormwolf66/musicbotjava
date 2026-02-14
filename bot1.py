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

# Use system ffmpeg executable (make sure ffmpeg is installed in your environment)
FFMPEG_PATH = "ffmpeg"  # Just the command, relying on system PATH

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Opus and PyNaCl check with fallback ---
print("Checking voice libraries...")
try:
    import nacl
    print(f"✅ PyNaCl version: {nacl.__version__}")
except ImportError:
    print("❌ PyNaCl not installed! Voice will not work. Run: pip install PyNaCl")

if not discord.opus.is_loaded():
    opus_path = ctypes.util.find_library('opus')
    if opus_path:
        try:
            discord.opus.load_opus(opus_path)
            print(f"✅ Loaded Opus from: {opus_path}")
        except Exception as e:
            print(f"❌ Could not load Opus from {opus_path}: {e}")
    else:
        # Try hardcoded common paths
        paths = [
            "/usr/lib/x86_64-linux-gnu/libopus.so.0",
            "/usr/lib/aarch64-linux-gnu/libopus.so.0",
            "/usr/local/lib/libopus.so",
        ]
        loaded = False
        for hardcoded_path in paths:
            try:
                discord.opus.load_opus(hardcoded_path)
                print(f"✅ Loaded Opus from: {hardcoded_path}")
                loaded = True
                break
            except:
                continue
        if not loaded:
            print("❌ Opus library not found. Audio features will not work.")
            print("Install with: apt-get install libopus0 (Debian/Ubuntu)")
else:
    print("✅ Opus already loaded")

# Utility function to safely cleanup voice connections
async def cleanup_voice_client(guild):
    """Safely disconnect and cleanup voice client"""
    if guild.voice_client:
        try:
            if guild.voice_client.is_playing():
                guild.voice_client.stop()
            await guild.voice_client.disconnect(force=True)
            await asyncio.sleep(0.5)  # Give Discord time to cleanup
        except:
            pass

YTDL_OPTIONS = {
    'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': False,
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'cachedir': False,
    'source_address': '0.0.0.0',
    'cookiefile': 'cookies.txt',
    'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    'age_limit': None,
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

        if data is None:
            raise Exception("Could not retrieve info from URL.")

        if 'entries' in data:
            raise Exception("Playlists are not supported. Please use a single video URL.")

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, executable=FFMPEG_PATH, **FFMPEG_OPTIONS), data=data)


@bot.command(name='join', help='Tells the bot to join the voice channel')
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("You are not connected to a voice channel.")
        return
    
    # Check voice dependencies
    if not discord.opus.is_loaded():
        await ctx.send("❌ Opus library not loaded. Voice features unavailable.")
        return
    
    try:
        # Clean up any existing connection
        await cleanup_voice_client(ctx.guild)
        await asyncio.sleep(1)  # Wait for cleanup
        
        voice_client = await ctx.author.voice.channel.connect(timeout=30.0, reconnect=False)
        await ctx.send(f"✅ Joined {ctx.author.voice.channel.name}!")
    except asyncio.TimeoutError:
        await ctx.send("❌ Connection timeout. Discord voice servers may be slow. Try again.")
    except discord.errors.ConnectionClosed as e:
        await ctx.send(f"❌ Voice connection failed (Error {e.code}). Try `!leave` then `!join` again.")
    except Exception as e:
        await ctx.send(f"❌ Could not join: {e}")


@bot.command(name='leave', help='Make the bot leave the voice channel')
async def leave(ctx):
    voice_client = ctx.guild.voice_client
    if voice_client:
        try:
            await cleanup_voice_client(ctx.guild)
            await ctx.send("👋 Disconnected")
        except Exception as e:
            await ctx.send(f"Disconnected (error: {e})")
    else:
        await ctx.send("I'm not in a voice channel.")


@bot.command(name='play', help='Play a song from a YouTube URL')
async def play(ctx, url: str):
    # Check voice dependencies first
    if not discord.opus.is_loaded():
        await ctx.send("❌ Voice features unavailable (Opus not loaded)")
        return
    
    voice_client = ctx.guild.voice_client

    if not voice_client:
        if ctx.author.voice:
            try:
                # Clean up any stale connections
                await cleanup_voice_client(ctx.guild)
                await asyncio.sleep(1)
                
                voice_client = await ctx.author.voice.channel.connect(timeout=30.0, reconnect=False)
            except asyncio.TimeoutError:
                await ctx.send("❌ Connection timeout. Try `!join` first.")
                return
            except discord.errors.ConnectionClosed as e:
                await ctx.send(f"❌ Voice connection failed (Error {e.code}). Use `!leave` then try again.")
                return
            except Exception as e:
                await ctx.send(f"❌ Could not join: {e}")
                return
        else:
            await ctx.send("You are not connected to a voice channel.")
            return

    # Validate connection
    if not voice_client.is_connected():
        await ctx.send("❌ Voice connection lost. Use `!leave` then `!join`.")
        return

    if voice_client.is_playing():
        voice_client.stop()

    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        except Exception as e:
            error_msg = str(e)
            if "Requested format is not available" in error_msg:
                await ctx.send("❌ Could not find a playable audio format for this video. The video may be unavailable or region-locked.")
            else:
                await ctx.send(f"❌ Error: {error_msg}")
            return

        def after_playing(error):
            if error:
                print(f'Player error: {error}')

        voice_client.play(player, after=after_playing)
        await ctx.send(f'🎶 Now playing: *{player.title}*')


@bot.command(name='voiceinfo', help='Check voice system status')
async def voiceinfo(ctx):
    """Diagnostic command to check voice capabilities"""
    info = []
    info.append(f"Opus loaded: {'✅' if discord.opus.is_loaded() else '❌'}")
    
    try:
        import nacl
        info.append(f"PyNaCl: ✅ v{nacl.__version__}")
    except ImportError:
        info.append("PyNaCl: ❌ NOT INSTALLED")
    
    vc = ctx.guild.voice_client
    if vc:
        info.append(f"Connected: ✅ {vc.channel.name}")
        info.append(f"Playing: {'✅' if vc.is_playing() else '❌'}")
    else:
        info.append("Connected: ❌")
    
    await ctx.send("\n".join(info))


@bot.event
async def on_voice_state_update(member, before, after):
    # If the bot was disconnected from a voice channel, cleanup
    if member == bot.user and before.channel is not None and after.channel is None:
        # Cleanup voice client
        if before.channel.guild.voice_client:
            try:
                await before.channel.guild.voice_client.disconnect(force=True)
            except:
                pass
        
        for text_channel in before.channel.guild.text_channels:
            if text_channel.permissions_for(before.channel.guild.me).send_messages:
                await text_channel.send("👋 Disconnected from voice")
                break


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
