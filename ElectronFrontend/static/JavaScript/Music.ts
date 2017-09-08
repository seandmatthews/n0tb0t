const path = require('path');
const fs = require('fs');

const playNextSong = () => {
    const audioElement = readyNextSong();
    audioElement.oncanplaythrough = audioElement.play; // When the song is loaded, play it.
};

const readyNextSong = () => {
    const audioElement = <HTMLAudioElement>document.getElementById("music_player");
    const audioSource = document.getElementById("audio_source");
    const songPath = getNextSongFromQueue();
    const songTitle = path.basename(songPath);
    const titleSpan = document.getElementById("title_span");
    titleSpan.textContent = songTitle.substring(0, songTitle.lastIndexOf('.'));
    audioSource.setAttribute("src", songPath);

    audioElement.pause();
    audioElement.load();// Suspends and restores all audio element
    return audioElement
};

const getNextSongFromQueue = () => {
    //Nonsense to fill in until I have the grpc calls set up
    const currentFile = __filename;
    const musicCacheDir = path.normalize(path.join(path.dirname(currentFile), '..', '..', 'MusicCache'));
    let filesArr = [];
    fs.readdirSync(musicCacheDir).forEach(file => {
        filesArr.push(file);
    });
    const songName = filesArr[Math.floor(Math.random()*filesArr.length)];
    return path.join(musicCacheDir , songName);
};

const removeSong = () => {

};

const promoteSong = () => {

};