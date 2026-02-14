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
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': False,
    'no_warnings': False,
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'cookiefile': 'cookies.txt',
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios', 'web'],
            'player_skip': ['webpage', 'configs'],
        }
    },
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'best',
    }],
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 128k'
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
        channel = ctx.author.voice.channel
        
        # Force cleanup any existing connection with better error handling
        if ctx.guild.voice_client:
            print(f"Cleaning up existing connection...")
            try:
                if hasattr(ctx.guild.voice_client, 'ws') and ctx.guild.voice_client.ws:
                    try:
                        await ctx.guild.voice_client.ws.close(4000)
                        await asyncio.sleep(0.5)
                    except:
                        pass
                await ctx.guild.voice_client.disconnect(force=True)
                await asyncio.sleep(3)  # Even longer delay for cleanup
            except Exception as cleanup_error:
                print(f"Cleanup warning: {cleanup_error}")
                await asyncio.sleep(2)
        
        print(f"Attempting to connect to {channel.name}...")
        
        # Connect with self_deaf=True to reduce voice server load
        voice_client = await channel.connect(timeout=60.0, reconnect=True, self_deaf=True)
        
        # Extended wait for connection to stabilize
        print("Waiting for connection to stabilize...")
        await asyncio.sleep(3)
        
        # Verify connection is still active
        if voice_client and voice_client.is_connected():
            await ctx.send(f"✅ Joined {channel.name}!")
            print(f"✅ Successfully connected and stable in: {channel.name}")
        else:
            await ctx.send("⚠️ Connection unstable. This may be a network/firewall issue blocking UDP voice traffic.")
            print("⚠️ Connection succeeded but immediately became unstable")
    except asyncio.TimeoutError:
        await ctx.send("❌ Connection timeout (60s). Network issue or Discord voice server problem.")
        print("❌ Timeout during voice connection")
    except discord.errors.ConnectionClosed as e:
        await ctx.send(f"❌ Voice error {e.code}. This often means:\n• Network/firewall blocking UDP\n• Multiple bot instances running\n• Discord voice server issue")
        print(f"❌ ConnectionClosed error {e.code}")
    except (IndexError, AttributeError) as e:
        await ctx.send("❌ Voice state error. Discord.py internal issue. Use `!reset`")
        print(f"Voice state error in join: {type(e).__name__}: {e}")
    except Exception as e:
        await ctx.send(f"❌ Could not join: {type(e).__name__}")
        print(f"Join error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


@bot.command(name='leave', help='Make the bot leave the voice channel')
async def leave(ctx):
    voice_client = ctx.guild.voice_client
    if voice_client:
        try:
            if voice_client.is_playing():
                voice_client.stop()
            
            # Better cleanup
            if hasattr(voice_client, 'ws') and voice_client.ws:
                try:
                    await voice_client.ws.close(4000)
                except:
                    pass
            
            await voice_client.disconnect(force=True)
            await ctx.send("👋 Disconnected")
        except Exception as e:
            await ctx.send(f"Disconnected (error: {type(e).__name__})")
            print(f"Leave error: {e}")
    else:
        await ctx.send("I'm not in a voice channel.")


@bot.command(name='reset', help='Force reset voice connection (use if stuck)')
async def reset(ctx):
    """Force cleanup of all voice connections"""
    try:
        vc = ctx.guild.voice_client
        if vc:
            # Force stop everything
            if vc.is_playing():
                vc.stop()
            
            # Close websocket if exists
            if hasattr(vc, 'ws') and vc.ws:
                try:
                    await vc.ws.close(4000)
                except:
                    pass
            
            # Force disconnect
            await vc.disconnect(force=True)
            await asyncio.sleep(2)
        
        await ctx.send("✅ Voice connection reset. You can now use `!join` again.")
    except Exception as e:
        await ctx.send(f"✅ Reset attempted ({type(e).__name__}). Try `!join` now.")
        print(f"Reset error: {e}")


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
                if ctx.guild.voice_client:
                    try:
                        if hasattr(ctx.guild.voice_client, 'ws') and ctx.guild.voice_client.ws:
                            try:
                                await ctx.guild.voice_client.ws.close(4000)
                            except:
                                pass
                        await ctx.guild.voice_client.disconnect(force=True)
                        await asyncio.sleep(2)
                    except:
                        pass
                
                voice_client = await ctx.author.voice.channel.connect(timeout=30.0, reconnect=True)
                await asyncio.sleep(1)  # Let connection stabilize
                
                if not voice_client.is_connected():
                    await ctx.send("❌ Connection failed. Use `!join` first.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("❌ Connection timeout. Use `!reset` then `!join` first.")
                return
            except discord.errors.ConnectionClosed as e:
                await ctx.send(f"❌ Voice error {e.code}. Use `!reset` first.")
                return
            except (IndexError, AttributeError):
                await ctx.send("❌ Voice state error. Use `!reset` first.")
                return
            except Exception as e:
                await ctx.send(f"❌ Could not join: {type(e).__name__}. Use `!reset`")
                print(f"Play connection error: {e}")
                return
        else:
            await ctx.send("You are not connected to a voice channel.")
            return

    # Validate connection
    if not voice_client.is_connected():
        await ctx.send("❌ Voice connection lost. Use `!reset` then `!join`.")
        return

    if voice_client.is_playing():
        voice_client.stop()

    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        except Exception as e:
            error_msg = str(e)
            print(f"YouTube extraction error: {error_msg}")
            
            if "Requested format is not available" in error_msg:
                await ctx.send("❌ No playable format found. Try:\n1. Update yt-dlp: `pip install -U yt-dlp`\n2. Try a different video\n3. Check if video is age-restricted")
            elif "Video unavailable" in error_msg:
                await ctx.send("❌ Video is unavailable or private.")
            elif "Sign in to confirm" in error_msg or "age" in error_msg.lower():
                await ctx.send("❌ Age-restricted video. Bot cannot play these.")
            else:
                await ctx.send(f"❌ Download error: {error_msg[:100]}")
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
        import nacl.secret
        info.append(f"PyNaCl: ✅ v{nacl.__version__}")
        
        # Test PyNaCl encryption functionality
        try:
            key = b'0' * 32
            box = nacl.secret.SecretBox(key)
            test = box.encrypt(b'test')
            info.append("PyNaCl encryption: ✅ Working")
        except Exception as e:
            info.append(f"PyNaCl encryption: ❌ Failed ({e})")
    except ImportError:
        info.append("PyNaCl: ❌ NOT INSTALLED")
    
    vc = ctx.guild.voice_client
    if vc:
        info.append(f"Connected: ✅ {vc.channel.name}")
        info.append(f"Is connected: {'✅' if vc.is_connected() else '❌'}")
        info.append(f"Playing: {'✅' if vc.is_playing() else '❌'}")
        info.append(f"Latency: {vc.latency*1000:.0f}ms" if hasattr(vc, 'latency') and vc.latency else "Latency: N/A")
    else:
        info.append("Connected: ❌")
    
    await ctx.send("\n".join(info))


@bot.command(name='testconnection', help='Test if voice connection stays alive')
async def testconnection(ctx):
    """Test voice connection stability"""
    vc = ctx.guild.voice_client
    if not vc:
        await ctx.send("❌ Not connected to voice. Use `!join` first.")
        return
    
    await ctx.send("🔄 Testing connection stability...")
    await asyncio.sleep(2)
    
    if vc.is_connected():
        await ctx.send(f"✅ Connection stable! Still connected to {vc.channel.name}")
    else:
        await ctx.send("❌ Connection lost! Use `!reset` and try again.")


@bot.command(name='fix4006', help='Troubleshooting guide for error 4006')
async def fix4006(ctx):
    """Provide troubleshooting steps for 4006 error"""
    guide = """
**Error 4006 Troubleshooting Guide:**

**Common Causes:**
1. **Network/Firewall**: UDP voice packets blocked
2. **Multiple Bot Instances**: Only run ONE instance
3. **PyNaCl Issues**: Encryption library problems

**Try These Steps:**
1. `!voiceinfo` - Check if PyNaCl encryption works
2. Ensure firewall allows UDP traffic to Discord
3. Kill all other bot instances with same token
4. Reinstall PyNaCl: `pip uninstall PyNaCl -y && pip install PyNaCl==1.5.0`
5. Check if other voice bots work in same server
6. Try connecting from different network/VPS

**If still failing:** This may be a Discord voice server region issue or deep network problem.
"""
    await ctx.send(guide)


@bot.command(name='ytinfo', help='Check yt-dlp version and test extraction')
async def ytinfo(ctx):
    """Check yt-dlp version"""
    info = []
    info.append(f"yt-dlp version: {yt_dlp.version.__version__}")
    info.append(f"FFMPEG path: {FFMPEG_PATH}")
    await ctx.send("\n".join(info))


@bot.event
async def on_voice_state_update(member, before, after):
    # If the bot was disconnected from a voice channel, cleanup
    if member == bot.user and before.channel is not None and after.channel is None:
        # Cleanup voice client with proper error handling
        vc = before.channel.guild.voice_client
        if vc:
            try:
                if hasattr(vc, 'ws') and vc.ws:
                    try:
                        await vc.ws.close(4000)
                    except:
                        pass
                await vc.disconnect(force=True)
            except Exception as e:
                print(f"Cleanup error in on_voice_state_update: {e}")
        
        for text_channel in before.channel.guild.text_channels:
            if text_channel.permissions_for(before.channel.guild.me).send_messages:
                await text_channel.send("👋 Disconnected from voice")
                break


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
