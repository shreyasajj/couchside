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
        wrapMode: Text.WordWrap
        font.weight: current ? Font.Bold : Font.DemiBold
        font.pixelSize: current ? view.refWidth * 0.06
                        : distance === 1 ? view.refWidth * 0.034
                        : view.refWidth * 0.026
        opacity: current ? 1.0 : distance === 1 ? 0.85 : distance > 1 ? 0.45 : 0.35
        Behavior on font.pixelSize { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 300 } }
        layer.enabled: current
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowBlur: 0.6
            shadowOpacity: 0.7
            shadowVerticalOffset: 4 * view.u
        }
    }
}
