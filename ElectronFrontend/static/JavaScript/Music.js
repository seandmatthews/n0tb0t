var path = require('path');
var fs = require('fs');
var playNextSong = function () {
    var audioElement = readyNextSong();
    audioElement.oncanplaythrough = audioElement.play; // When the song is loaded, play it.
};
var readyNextSong = function () {
    var audioElement = document.getElementById("music_player");
    var audioSource = document.getElementById("audio_source");
    var songPath = getNextSongFromQueue();
    var songTitle = path.basename(songPath);
    var titleSpan = document.getElementById("title_span");
    titleSpan.textContent = songTitle.substring(0, songTitle.lastIndexOf('.'));
    audioSource.setAttribute("src", songPath);
    audioElement.pause();
    audioElement.load(); // Suspends and restores all audio element
    return audioElement;
};
var getNextSongFromQueue = function () {
    //Nonsense to fill in until I have the grpc calls set up
    var currentFile = __filename;
    var musicCacheDir = path.normalize(path.join(path.dirname(currentFile), '..', '..', 'MusicCache'));
    var filesArr = [];
    fs.readdirSync(musicCacheDir).forEach(function (file) {
        filesArr.push(file);
    });
    var songName = filesArr[Math.floor(Math.random() * filesArr.length)];
    return path.join(musicCacheDir, songName);
};
var removeSong = function () {
};
var promoteSong = function () {
};
//# sourceMappingURL=Music.js.map