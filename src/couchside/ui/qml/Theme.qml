pragma Singleton
import QtQuick

// One place for the look: colours, text sizes, spacing, timing. Sizes are for a 1080p
// screen; multiply by `u` (window height / 1080) where they are used.
QtObject {
    // colour
    readonly property color bg: "#0d0b1a"
    readonly property color panel: "#1d1840"
    readonly property color text: "#ffffff"
    readonly property color textDim: "#b3ffffff"      // secondary text
    readonly property color surface: "#1affffff"      // quiet fills (rows, chips)
    readonly property color surfaceHigh: "#29ffffff"
    readonly property color scrim: "#66000000"        // behind text that sits on artwork
    readonly property color accent: "#4fc3f7"         // "on" states only
    readonly property color focus: "#ffffff"          // the focused control is white...
    readonly property color focusText: "#0d0b1a"        // ...with dark content
    readonly property color warn: "#ffd479"

    // text sizes (never below `label`: 28 px is the smallest readable from the couch)
    readonly property int display: 88
    readonly property int title: 48
    readonly property int heading: 40
    readonly property int body: 32
    readonly property int label: 28

    // spacing and shape
    readonly property int margin: 72
    readonly property int gap: 24
    readonly property int radius: 16

    // timing: short, and only on things the remote just did
    readonly property int focusMs: 120
    readonly property int fadeMs: 300
}
