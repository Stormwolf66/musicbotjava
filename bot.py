import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Use system ffmpeg executable (Heroku installs it globally)
FFMPEG_PATH = "ffmpeg"

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True  # Required for voice state updates

bot = commands.Bot(command_prefix='!', intents=intents)

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
    'cookiefile': 'cookies.txt'  # Add your YouTube cookies here
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'  # No video
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


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


@bot.command(name='join', help='Tells the bot to join the voice channel')
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("You are not connected to a voice channel.")
        return
    await ctx.author.voice.channel.connect()


@bot.command(name='leave', help='Makes the bot leave the voice channel')
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
            voice_client = await ctx.author.voice.channel.connect()
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

        def after_playing(error):
            if error:
                print(f'Player error: {error}')

        voice_client.play(player, after=after_playing)
        await ctx.send(f'🎶 Now playing: **{player.title}**')


@bot.event
async def on_voice_state_update(member, before, after):
    # If the bot was disconnected manually from voice
    if member == bot.user and before.channel is not None and after.channel is None:
        for channel in before.channel.guild.text_channels:
            if channel.permissions_for(before.channel.guild.me).send_messages:
                await channel.send("Bye 😢 I was disconnected from the voice channel.")
                break


bot.run(os.getenv("DISCORD_BOT_TOKEN"))
