const nextSong = () => {
    console.log("Now playing next song");
    const audio = document.getElementById("music_player");
    document.getElementById("audio_source").setAttribute("src", ""); // Cheese
    document.getElementById("audio_source").setAttribute("src", "/next_song/"+new Date());
    /****************/
    audio.pause();
    audio.load();// Suspends and restores all audio element

    audio.oncanplaythrough = audio.play(); // When the song is loaded, play it.
};