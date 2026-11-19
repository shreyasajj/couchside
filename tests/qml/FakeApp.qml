import QtQuick

// A stand-in for the controller (`app`) so one screen or control can be tested on its own:
// plain properties a test sets, and every call recorded in `calls` as [name, args...].
// tests/test_components_qml.py checks this covers everything the QML uses.
QtObject {
    id: fake
    property var calls: []
    function record(name, args) {
        var c = calls.slice()
        c.push([name].concat(Array.prototype.slice.call(args)))
        calls = c
    }
    function called(name) { return calls.filter(function(c) { return c[0] === name }) }

    signal changed()
    signal libraryChanged()
    signal queueChanged()
    signal speakersChanged()
    signal lyricsChanged()
    signal guestChanged()
    signal sendspinChanged()
    signal updateChanged()
    signal pulseChanged()
    signal levelChanged()
    signal beatChanged()
    signal qrChanged()
    signal healthChanged()
    signal logsChanged()
    signal crossfadeChanged()

    // --- connection and now playing ---
    property string connState: "connected"
    property string statusText: ""
    property bool needsSetup: false
    property bool hasToken: true
    property string serverUrl: ""
    property string pairingCode: ""
    property bool hasLocalPlayer: true
    property string title: "Neon Tide"
    property string artist: "Marisol Vega"
    property string album: "Afterglow"
    property string artUrl: ""
    property string artUrlLarge: ""
    property string nextTitle: "Glass Harbour"
    property string nextArtist: "Marisol Vega"
    property string nextArtUrl: ""
    property real duration: 224
    property bool hasDuration: true
    property real positionBase: 38
    property real positionAt: 0
    property bool shuffle: false
    property string repeatMode: "off"
    property int volume: 40
    property bool hasVolume: true
    property string backgroundColour: "#191c29"
    property bool isPlaying: true
    property string toast: ""
    property string nowPlayingCredit: ""

    // --- lyrics ---
    property var lyricLines: []
    property bool hasLyrics: lyricLines.length > 0
    property bool lyricsPending: false
    property bool lyricsEnabled: true
    property bool lyricsShown: true
    property bool lyricsVisualizer: true
    property string lyricsSize: "medium"
    property string lyricsLanguage: "romanized"
    property bool lyricsTranslate: false
    property string translateService: "google"
    property bool hasDeeplKey: false
    property string libretranslateUrl: ""

    // --- library, queue, speakers ---
    property var libraryRows: []
    property string libraryError: ""
    property bool libraryBusy: false
    property var queueRows: []
    property bool queueVisible: false
    property var speakerRows: []

    // --- guests ---
    property bool guestMode: false
    property var guestRows: []
    property int guestCount: guestRows.length
    property string adminCode: ""
    property string guestUrl: ""
    property var qrRows: []
    property string qrCaption: "Scan to add songs"
    property string guestPublicUrl: ""
    property int guestPort: 8780
    property int guestSkips: 3
    property int guestBoosts: 2
    property int guestMaxWaiting: 3
    property int guestCooldown: 0

    // --- this speaker ---
    property string playerName: "Living Room TV"
    property var audioOutputs: [{ id: "", label: "Default", section: "", current: true },
                                { id: "hdmi", label: "HDMI", section: "", current: false }]
    property string audioOutputLabel: "Default"
    property int sendspinDelay: 0
    property string sendspinVersionText: "Sendspin 5.1.0"
    property bool crossfadeKnown: true
    property bool crossfadeEnabled: false
    property string crossfadeModeLabel: "Standard"
    property var crossfadeModes: [{ id: "global", label: "Default", current: false },
                                  { id: "smart_crossfade", label: "Smart", current: false },
                                  { id: "standard_crossfade", label: "Standard", current: true }]
    property int crossfadeSeconds: 8
    property bool crossfadeLengthApplies: true
    property string appVersion: "1.0.0"
    property string updateState: "current"
    property string updateText: "Up to date"
    property string problem: ""
    property var problems: []
    property string sendspinLog: "speaker line 1\nspeaker line 2"
    property string appLog: "app line 1"

    // --- visualizer and look ---
    property bool visualizerEnabled: true
    property bool pulseVisible: false
    property bool vizVisible: false
    property var spectrum: []
    property real vizBeat: 0
    property real vizEnergy: 0
    property real vizTempo: 120
    property bool visualizerEdges: false
    property real visualizerIntensity: 1.0
    property string visualizerMode: "radial"
    property string visualizerColours: "accent"
    property string visualizerColoursLabel: "Theme"
    property var visualizerColourChoices: [{ id: "accent", label: "Theme", current: true },
                                           { id: "rainbow", label: "Rainbow", current: false }]
    property var beatSources: [{ id: "", label: "This TV", section: "", current: true },
                               { id: "mic", label: "Microphone", section: "Inputs", current: false }]
    property string beatSourceLabel: "This TV"
    property string accent: "aurora"
    property string accent1: "#7c5cff"
    property string accent2: "#ff5ca8"
    property var accents: [{ id: "aurora", label: "Aurora", a1: "#7c5cff", a2: "#ff5ca8", current: true },
                           { id: "ocean", label: "Ocean", a1: "#2fa8ff", a2: "#2fe0c0", current: false }]
    property real audioPulse: 0
    property real lightPulse: 0
    property real beatHue: 0.55

    // --- calls (each one recorded) ---
    function formatTime(seconds) {
        var s = Math.max(0, Math.floor(seconds))
        return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2)
    }
    function playPause() { record("playPause", arguments) }
    function next() { record("next", arguments) }
    function previous() { record("previous", arguments) }
    function toggleShuffle() { record("toggleShuffle", arguments) }
    function cycleRepeat() { record("cycleRepeat", arguments) }
    function setVolume(level) { record("setVolume", arguments) }
    function volumeUp() { record("volumeUp", arguments) }
    function volumeDown() { record("volumeDown", arguments) }
    function search(query) { record("search", arguments) }
    function loadRecents() { record("loadRecents", arguments) }
    function playUri(uri, mode) { record("playUri", arguments) }
    function loadQueue() { record("loadQueue", arguments) }
    function queueAction(itemId, action) { record("queueAction", arguments) }
    function controlSpeaker(playerId) { record("controlSpeaker", arguments) }
    function speakerAction(playerId, action) { record("speakerAction", arguments) }
    function createGroup(members) { record("createGroup", arguments) }
    function editGroup(groupId, members) { record("editGroup", arguments) }
    function guestAction(publicId, action) { record("guestAction", arguments) }
    function showAdminCode() { record("showAdminCode", arguments) }
    function closeAdminCode() { record("closeAdminCode", arguments) }
    function toggleGuestMode() { record("toggleGuestMode", arguments) }
    function setQrCaption(text) { record("setQrCaption", arguments) }
    function setGuestPublicUrl(url) { record("setGuestPublicUrl", arguments) }
    function setGuestPort(text) { record("setGuestPort", arguments) }
    function cycleGuestSkips() { record("cycleGuestSkips", arguments) }
    function cycleGuestBoosts() { record("cycleGuestBoosts", arguments) }
    function cycleGuestMaxWaiting() { record("cycleGuestMaxWaiting", arguments) }
    function cycleGuestCooldown() { record("cycleGuestCooldown", arguments) }
    function setPlayerName(name) { record("setPlayerName", arguments) }
    function setAudioOutput(choice) { record("setAudioOutput", arguments) }
    function loadCrossfade() { record("loadCrossfade", arguments) }
    function toggleCrossfade() { record("toggleCrossfade", arguments) }
    function setCrossfadeMode(mode) { record("setCrossfadeMode", arguments) }
    function stepCrossfadeSeconds(direction) { record("stepCrossfadeSeconds", arguments) }
    function setBeatSource(choice) { record("setBeatSource", arguments) }
    function loadAudioDevices() { record("loadAudioDevices", arguments) }
    function cycleSendspinDelay() { record("cycleSendspinDelay", arguments) }
    function installUpdate() { record("installUpdate", arguments) }
    function restartSpeaker() { record("restartSpeaker", arguments) }
    function loadLogs() { record("loadLogs", arguments) }
    function setVisualizerColours(colours) { record("setVisualizerColours", arguments) }
    function setAccent(accent) { record("setAccent", arguments) }
    function clearToast() { record("clearToast", arguments) }
    function saveConnection(url, token) { record("saveConnection", arguments) }
    function cycleLyricsLanguage() { record("cycleLyricsLanguage", arguments) }
    function toggleLyricsTranslate() { record("toggleLyricsTranslate", arguments) }
    function cycleTranslateService() { record("cycleTranslateService", arguments) }
    function saveDeeplKey(key) { record("saveDeeplKey", arguments) }
    function setLibretranslateUrl(url) { record("setLibretranslateUrl", arguments) }
    function cycleLyricsSize() { record("cycleLyricsSize", arguments) }
}
