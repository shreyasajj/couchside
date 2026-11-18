import QtQuick
import QtQuick.Effects

// Synced lyrics: the current line large and bright, the others drawn smaller and faded.
// `stage` is the full-screen look (the Lyrics tab, party mode): the line being sung in
// the accent colour in the middle of the screen, the rest fading away above and below.
// Without it the current line sits in the upper third, in white. Not focusable.
ListView {
    id: view
    property real position: 0
    property var lines: []
    property real u: 1
    property real refWidth: width  // sizes are fractions of the screen width (design)
    property string size: "medium"  // small | medium | large (Settings)
    property bool stage: false
    // [current, next, other] line sizes as fractions of the screen width
    // (stage: 92 px at 1080p for medium, 15 % either way for the other two)
    readonly property var scale: stage ? (({ large: [0.0551, 0.034, 0.026],
                                             medium: [0.0479, 0.029, 0.023],
                                             small: [0.0407, 0.025, 0.020] })[size] || [0.0479, 0.029, 0.023])
                                       : (({ large: [0.060, 0.034, 0.026],
                                             medium: [0.045, 0.029, 0.023],
                                             small: [0.035, 0.025, 0.020] })[size] || [0.045, 0.029, 0.023])
    // line being sung (-1 before the first line), same rule as core.lyrics.line_index_at
    readonly property int activeIndex: {
        var lo = 0, hi = lines.length
        while (lo < hi) {
            var mid = (lo + hi) >> 1
            if (lines[mid].t <= position) lo = mid + 1
            else hi = mid
        }
        return lo - 1
    }

    model: lines
    interactive: false
    focus: false
    activeFocusOnTab: false
    clip: true
    // lines not being sung are drawn smaller inside their full-size box: tuck the boxes
    // together a little so the gaps stay even
    spacing: -0.18 * refWidth * scale[0]
    currentIndex: Math.max(0, activeIndex)
    highlightRangeMode: ListView.StrictlyEnforceRange
    // on stage the line being sung sits a third of the way down: most of the room is for
    // the lines coming up, so you can read ahead
    preferredHighlightBegin: height * (stage ? 0.3 : 0.28)
    preferredHighlightEnd: preferredHighlightBegin + 1
    highlightMoveDuration: stage ? 550 : 400
    highlightMoveVelocity: -1

    // fade the edges so lines drift in and out instead of being cut
    layer.enabled: true
    layer.effect: MultiEffect {
        maskEnabled: true
        maskThresholdMin: 0.0
        maskSpreadAtMin: 1.0
        maskSource: ShaderEffectSource {
            sourceItem: Rectangle {
                width: view.width
                height: view.height
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.12; color: "white" }
                    GradientStop { position: 0.9; color: "white" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }
    }

    delegate: Text {

        textFormat: Text.PlainText
        id: line
        required property var modelData
        required property int index
        readonly property int distance: index - view.activeIndex
        readonly property int away: Math.abs(distance)
        readonly property bool current: distance === 0
        width: ListView.view.width
        text: modelData.text !== "" ? modelData.text : "♪"
        color: view.stage && current ? Theme.a1 : "#ffffff"
        Behavior on color { ColorAnimation { duration: 300 } }
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        // Every line is laid out once, at the size it has when sung, and never changes
        // size or wrapping: text that resizes while you read it is hard to follow. The
        // lines not being sung are only drawn smaller (scale) and dimmer.
        font.weight: Font.Bold
        // Long lines (rap, Punjabi) shrink so no line needs more than two rows; the 0.85
        // leaves room for word-wrap waste. Short lines keep the full size.
        readonly property real fullSize: view.refWidth * view.scale[0]
        readonly property real fit: Math.min(1, (2 * width * 0.85) / Math.max(1, metrics.advanceWidth))
        font.pixelSize: fullSize * fit
        maximumLineCount: 2
        elide: Text.ElideRight
        TextMetrics {
            id: metrics
            font.family: line.font.family
            font.weight: Font.Bold
            font.pixelSize: line.fullSize
            text: line.text
        }
        transformOrigin: Item.Center
        // on stage the lines coming up stay larger and brighter than the ones already sung
        scale: view.stage ? (current ? 1.0 : distance === 1 ? 0.62 : distance === 2 ? 0.54
                                     : distance > 2 ? 0.48 : away === 1 ? 0.46 : 0.41)
                          : (current ? 1.0 : distance === 1 ? 0.72 : 0.62)
        opacity: view.stage ? (current ? 1.0 : distance === 1 ? 0.75 : distance === 2 ? 0.55
                                       : distance > 2 ? 0.35 : away === 1 ? 0.35 : 0.12)
                            : (current ? 1.0 : distance === 1 ? 0.8 : distance > 1 ? 0.45 : 0.35)
        Behavior on scale { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 250 } }

        // English underneath (optional translation): the current line's at the "next line"
        // size, the others smaller; sits in the bottom padding so the line keeps its size.
        readonly property string sub: modelData.sub || ""
        bottomPadding: sub !== "" ? subText.implicitHeight + 6 * view.u : 0
        Text {
            textFormat: Text.PlainText
            id: subText
            visible: line.sub !== ""
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            text: line.sub
            color: "#ffffff"
            opacity: 0.75
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
            font.italic: true
            font.pixelSize: view.refWidth * view.scale[1] * 0.85  // fixed, like the line itself
        }
        layer.enabled: current && !view.stage   // the stage line stands out by colour
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowBlur: 0.6
            shadowOpacity: 0.7
            shadowVerticalOffset: 4 * view.u
        }
    }
}
