pragma Singleton
import QtQuick

// One place for the look: colours, text sizes, spacing, timing. Sizes are for a 1080p
// screen; multiply by `u` (window height / 1080) where they are used.
QtObject {
    // colour: near-black, with two accents that run into each other as a gradient
    readonly property color bg: "#07070b"
    property color a1: "#00e0c6"                        // first accent: focus, "on", the current thing
    property color a2: "#ff3da6"                        // second accent: the far end of the gradient
    readonly property color text: "#ffffff"
    readonly property color textDim: "#9effffff"        // secondary text (62 %)
    readonly property color textFaint: "#73ffffff"      // tabs not chosen, hints (45 %)
    readonly property color surface: "#0dffffff"        // quiet fills: rows, fields (5 %)
    readonly property color surfaceHigh: "#1affffff"    // (10 %)
    readonly property color border: "#1affffff"
    readonly property color panel: "#e60f0f15"          // cards and sheets over artwork
    readonly property color scrim: "#b3000000"          // behind a sheet
    readonly property color ink: "#06121a"              // text and icons on the gradient
    readonly property color warn: "#ffd479"
    function tint(colour, alpha) { return Qt.rgba(colour.r, colour.g, colour.b, alpha) }

    readonly property string fontFamily: "Noto Sans"

    // text sizes (never below `label`: 28 px is the smallest readable from the couch;
    // `small` is for times and counts only)
    readonly property int display: 84
    readonly property int title: 48
    readonly property int rowTitle: 42
    readonly property int heading: 40
    readonly property int subtitle: 38
    readonly property int body: 32
    readonly property int tab: 30
    readonly property int label: 28
    readonly property int small: 24

    // spacing and shape
    readonly property int margin: 56
    readonly property int gap: 24
    readonly property int radius: 22

    // timing: short, and only on things the remote just did
    readonly property int focusMs: 120
    readonly property int fadeMs: 300
}
