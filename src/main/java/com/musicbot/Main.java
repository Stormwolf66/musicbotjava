package com.musicbot;

import net.dv8tion.jda.api.JDABuilder;
import net.dv8tion.jda.api.entities.*;
import net.dv8tion.jda.api.events.message.MessageReceivedEvent;
import net.dv8tion.jda.api.hooks.ListenerAdapter;

import com.sedmelluq.discord.lavaplayer.player.*;
import com.sedmelluq.discord.lavaplayer.source.youtube.YoutubeAudioSourceManager;
import com.sedmelluq.discord.lavaplayer.track.*;

import javax.security.auth.login.LoginException;
import java.util.HashMap;
import java.util.Map;

public class Main extends ListenerAdapter {

    private static final AudioPlayerManager playerManager = new DefaultAudioPlayerManager();
    private static final Map<Long, GuildMusicManager> musicManagers = new HashMap<>();

    public static void main(String[] args) throws LoginException {
        JDABuilder.createDefault("MTM5MDYxMDQzODg4MTkzNTQ2MQ.G6w20p.3qRnXvzbNY-of5vZ6Zug47A8K1GnEFwUwe_pds")
                .addEventListeners(new Main())
                .build();

        playerManager.registerSourceManager(new YoutubeAudioSourceManager());
    }

    private static synchronized GuildMusicManager getGuildAudioPlayer(Guild guild) {
        long guildId = guild.getIdLong();
        GuildMusicManager musicManager = musicManagers.get(guildId);

        if (musicManager == null) {
            musicManager = new GuildMusicManager(playerManager);
            musicManagers.put(guildId, musicManager);
        }

        guild.getAudioManager().setSendingHandler(musicManager.getSendHandler());
        return musicManager;
    }

    @Override
    public void onMessageReceived(MessageReceivedEvent event) {
        if (event.getAuthor().isBot() || !event.isFromGuild()) return;

        String[] command = event.getMessage().getContentRaw().split(" ", 2);
        String prefix = "!";

        if (!command[0].startsWith(prefix)) return;

        switch (command[0]) {
            case "!play":
                if (command.length < 2) {
                    event.getChannel().sendMessage("Please provide a YouTube link or playlist.").queue();
                    return;
                }
                play(event.getGuild(), event.getChannel().asTextChannel(), command[1], event.getMember());
                break;

            case "!skip":
                skipTrack(event.getGuild(), event.getChannel().asTextChannel());
                break;

            case "!stop":
                stop(event.getGuild(), event.getChannel().asTextChannel());
                break;
        }
    }

    private void play(Guild guild, TextChannel channel, String trackUrl, Member member) {
        GuildMusicManager musicManager = getGuildAudioPlayer(guild);

        AudioManager audioManager = guild.getAudioManager();
        if (!audioManager.isConnected()) {
            audioManager.openAudioConnection(member.getVoiceState().getChannel());
        }

        playerManager.loadItemOrdered(musicManager, trackUrl, new AudioLoadResultHandler() {
            @Override
            public void trackLoaded(AudioTrack track) {
                channel.sendMessage("Adding to queue: " + track.getInfo().title).queue();
                musicManager.scheduler.queue(track);
            }

            @Override
            public void playlistLoaded(AudioPlaylist playlist) {
                channel.sendMessage("Adding playlist: " + playlist.getName()).queue();
                for (AudioTrack track : playlist.getTracks()) {
                    musicManager.scheduler.queue(track);
                }
            }

            @Override
            public void noMatches() {
                channel.sendMessage("Nothing found by: " + trackUrl).queue();
            }

            @Override
            public void loadFailed(FriendlyException exception) {
                channel.sendMessage("Could not play: " + exception.getMessage()).queue();
            }
        });
    }

    private void skipTrack(Guild guild, TextChannel channel) {
        GuildMusicManager musicManager = getGuildAudioPlayer(guild);
        musicManager.scheduler.nextTrack();
        channel.sendMessage("Skipped to next track.").queue();
    }

    private void stop(Guild guild, TextChannel channel) {
        GuildMusicManager musicManager = getGuildAudioPlayer(guild);
        musicManager.scheduler.stop();
        guild.getAudioManager().closeAudioConnection();
        channel.sendMessage("Stopped music and left the channel.").queue();
    }
}
