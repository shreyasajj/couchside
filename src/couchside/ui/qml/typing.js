.pragma library

// The text a key press types, or "" when it isn't typing (arrows, OK, Back, media keys,
// space, control characters, shortcuts with Ctrl/Alt/Meta). Lets a keyboard remote type
// straight into Couchside without pressing OK first.
function typed(event) {
    var t = event.text
    if (!t || (event.modifiers & (0x04000000 | 0x08000000 | 0x10000000)))  // Ctrl, Alt, Meta
        return ""
    for (var i = 0; i < t.length; i++) {
        var c = t.charCodeAt(i)
        if (c <= 32 || c === 127)
            return ""
    }
    return t
}

// Bigscreen opens its on-screen keyboard a moment after a text field gets focus, so hide it
// now and again once the event loop has run.
function hideKeyboard() {
    Qt.inputMethod.hide()
    Qt.callLater(function() { Qt.inputMethod.hide() })
    _later(function() { Qt.inputMethod.hide() }, 300)
}

function _later(fn, ms) {
    var t = Qt.createQmlObject("import QtQuick; Timer {}", Qt.application, "hideKeyboardTimer")
    t.interval = ms
    t.triggered.connect(function() { fn(); t.destroy() })
    t.start()
}
