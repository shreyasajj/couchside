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
