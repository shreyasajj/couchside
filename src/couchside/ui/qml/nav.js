.pragma library

// Where the remote can go. Tabs sit in the top bar; Speakers, Guests, Settings and a
// content page opened from outside are screens without a tab.

var ALL_TABS = ["now", "search", "queue", "lyrics", "visualizer"]
var LABELS = { now: "Now Playing", search: "Search", queue: "Queue", lyrics: "Lyrics", visualizer: "Visualizer" }

// The tabs on show: Lyrics and Visualizer disappear with their settings.
function tabs(lyricsOn, visualizerOn) {
    return ALL_TABS.filter(function(t) {
        return (t !== "lyrics" || lyricsOn) && (t !== "visualizer" || visualizerOn)
    })
}

function isTab(screen) { return ALL_TABS.indexOf(screen) >= 0 }

function label(screen) { return LABELS[screen] || "" }

// The screen to show: itself, or Now Playing when its tab has just been switched off.
function validScreen(screen, lyricsOn, visualizerOn) {
    if (!isTab(screen)) return screen
    return tabs(lyricsOn, visualizerOn).indexOf(screen) >= 0 ? screen : "now"
}

// Where Back goes: a screen without a tab returns to the tab it was opened from, any
// other tab returns to Now Playing, and Now Playing asks to exit.
function back(screen, lastTab) {
    if (!isTab(screen)) return isTab(lastTab) ? lastTab : "now"
    return screen === "now" ? "exit" : "now"
}
