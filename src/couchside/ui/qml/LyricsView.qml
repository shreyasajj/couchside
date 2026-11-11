import QtQuick
import QtQuick.Effects

// Synced lyrics, lyrics-forward layout B: the current line very large and bold, the next
// one medium, the rest small and faded; scrolls so the current line sits in the upper third.
// Not focusable: the remote stays on the control bar.
ListView {
    id: view
    property real position: 0
    property var lines: []
    property real u: 1
    property real refWidth: width  // sizes are fractions of the screen width (design)
    property string size: "medium"  // small | medium | large (Settings)
    // [current, next, other] line sizes as fractions of the screen width
    readonly property var scale: ({ large: [0.060, 0.034, 0.026],
                                    medium: [0.045, 0.029, 0.023],
                                    small: [0.035, 0.025, 0.020] })[size] || [0.045, 0.029, 0.023]
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
    spacing: 18 * u
    currentIndex: Math.max(0, activeIndex)
    highlightRangeMode: ListView.StrictlyEnforceRange
    preferredHighlightBegin: height * 0.28
    preferredHighlightEnd: height * 0.28 + 1
    highlightMoveDuration: 400
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
                    GradientStop { position: 0.85; color: "white" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }
    }

    delegate: Text {
        id: line
        required property var modelData
        required property int index
        readonly property int distance: index - view.activeIndex
        readonly property bool current: distance === 0
        width: ListView.view.width
        text: modelData.text !== "" ? modelData.text : "♪"
        color: "#ffffff"
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        font.weight: current ? Font.Bold : Font.DemiBold
        // Long lines (rap, Punjabi) shrink so the current line never needs more than two
        // rows; the 0.85 leaves room for word-wrap waste. Short lines keep the full size.
        readonly property real fullSize: view.refWidth * view.scale[0]
        readonly property real fit: Math.min(1, (2 * width * 0.85) / Math.max(1, metrics.advanceWidth))
        font.pixelSize: current ? fullSize * fit
                        : distance === 1 ? view.refWidth * view.scale[1]
                        : view.refWidth * view.scale[2]
        maximumLineCount: current ? 2 : 3
        elide: Text.ElideRight
        TextMetrics {
            id: metrics
            font.family: line.font.family
            font.weight: Font.Bold
            font.pixelSize: line.fullSize
            text: line.text
        }
        opacity: current ? 1.0 : distance === 1 ? 0.85 : distance > 1 ? 0.45 : 0.35
        Behavior on font.pixelSize { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 300 } }
        // English underneath (optional translation): the current line's at the "next line"
        // size, the others smaller; sits in the bottom padding so the line keeps its size.
        readonly property string sub: modelData.sub || ""
        bottomPadding: sub !== "" ? subText.implicitHeight + 6 * view.u : 0
        Text {
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
            font.pixelSize: line.current ? view.refWidth * view.scale[1] * 0.8 : view.refWidth * view.scale[2] * 0.75
        }
        layer.enabled: current
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowBlur: 0.6
            shadowOpacity: 0.7
            shadowVerticalOffset: 4 * view.u
        }
    }
}
