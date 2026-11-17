.pragma library

// Where the remote can go. Tabs sit in the top bar; the Visualizer, Speakers, Guests,
// Settings and a content page opened from outside are screens without a tab.

var ALL_TABS = ["now", "search", "queue"]
var LABELS = { now: "Now Playing", search: "Search", queue: "Queue" }
var SCREENS = ALL_TABS.concat(["visualizer", "speakers", "guests", "settings", "content"])

function tabs() { return ALL_TABS }

function isTab(screen) { return ALL_TABS.indexOf(screen) >= 0 }

function label(screen) { return LABELS[screen] || "" }

// The screen to show: itself, or Now Playing for a name that isn't a screen (Lyrics was
// a tab once: it is a button on Now Playing now).
function validScreen(screen) { return SCREENS.indexOf(screen) >= 0 ? screen : "now" }

// Where Back goes: a screen without a tab returns to the tab it was opened from, any
// other tab returns to Now Playing, and Now Playing asks to exit.
function back(screen, lastTab) {
    if (!isTab(screen)) return isTab(lastTab) ? lastTab : "now"
    return screen === "now" ? "exit" : "now"
}
