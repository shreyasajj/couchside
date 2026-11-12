import QtQuick

// Party mode's light show: colour along all four edges of the screen, brighter and wider
// with the music (`pulse`, 0..1) and a new set of colours on every beat (`hue`, 0..1).
// Lights behind the TV that copy the screen's edges dance with it. No animations here:
// it redraws only when the pulse or the colour changes (see BeatGlow).
Item {
    id: lights
    property real pulse: 0
    property real hue: 0.55
    readonly property real glow: 0.25 + 0.75 * pulse   // never fully dark while music plays
    readonly property real reach: 0.6 + 0.4 * pulse    // how far the colour comes in
    function tint(offset) { return Qt.hsla((hue + offset) % 1, 1.0, 0.55, 1) }
    // one colour family per beat: neighbours on the colour wheel, so the frame looks like
    // one light with a little movement in it rather than four stripes
    readonly property color leftColour: tint(0)
    readonly property color topColour: tint(0.04)
    readonly property color rightColour: tint(0.1)
    readonly property color bottomColour: tint(0.06)
    opacity: glow

    Rectangle {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        width: parent.width * 0.24 * lights.reach
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: lights.leftColour }
                        GradientStop { position: 1.0; color: "transparent" }
        }
    }
    Rectangle {
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        width: parent.width * 0.24 * lights.reach
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 1.0; color: lights.rightColour }
        }
    }
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: parent.height * 0.26 * lights.reach
        gradient: Gradient {
            GradientStop { position: 0.0; color: lights.topColour }
                        GradientStop { position: 1.0; color: "transparent" }
        }
    }
    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: parent.height * 0.26 * lights.reach
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 1.0; color: lights.bottomColour }
        }
    }
}
