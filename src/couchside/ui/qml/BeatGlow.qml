import QtQuick
import QtQuick.Effects

// A soft glow that breathes with the music: it grows with the level and swells on each
// beat. Sits behind the artwork (or the lyrics in party mode). Colour from the artwork.
Item {
    id: glow
    property real level: 0      // 0..1
    property int beats: 0       // counts up; each change is a beat
    property color baseColour: "#4fc3f7"
    property real strength: 1   // party mode goes bigger
    property real kick: 0

    readonly property color tint: {
        var c = baseColour
        return c.hslHue < 0 ? Qt.rgba(0.31, 0.76, 0.97, 1)
                            : Qt.hsla(c.hslHue, Math.max(0.55, c.hslSaturation), 0.62, 1)
    }

    onBeatsChanged: swell.restart()
    SequentialAnimation {
        id: swell
        NumberAnimation { target: glow; property: "kick"; to: 1; duration: 60; easing.type: Easing.OutQuad }
        NumberAnimation { target: glow; property: "kick"; to: 0; duration: 380; easing.type: Easing.InQuad }
    }

    Rectangle {
        id: blob
        anchors.centerIn: parent
        width: parent.width * 0.8
        height: parent.height * 0.8
        radius: Math.min(width, height) / 2
        color: glow.tint
        visible: false
        layer.enabled: true
    }
    MultiEffect {
        anchors.centerIn: parent
        width: blob.width
        height: blob.height
        source: blob
        blurEnabled: true
        blur: 1.0
        blurMax: 64
        autoPaddingEnabled: true
        opacity: Math.min(0.95, (0.18 + 0.45 * glow.level + 0.3 * glow.kick) * glow.strength)
        scale: 1.0 + (0.12 * glow.level + 0.1 * glow.kick) * glow.strength
        Behavior on opacity { NumberAnimation { duration: 90 } }
        Behavior on scale { NumberAnimation { duration: 90 } }
    }
}
