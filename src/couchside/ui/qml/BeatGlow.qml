import QtQuick
import QtQuick.Effects

// A soft glow that breathes with the music: bigger and brighter with `pulse` (the level,
// swelling on each beat; computed by the controller). No animations here on purpose: the
// screen redraws only when the pulse changes (at most 20 times a second).
Item {
    id: glow
    property real pulse: 0      // 0..1
    property color baseColour: "#4fc3f7"
    property real strength: 1   // party mode goes bigger

    readonly property color tint: {
        var c = baseColour
        return c.hslHue < 0 ? Qt.rgba(0.31, 0.76, 0.97, 1)
                            : Qt.hsla(c.hslHue, Math.max(0.55, c.hslSaturation), 0.62, 1)
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
        opacity: Math.min(0.95, (0.18 + 0.6 * glow.pulse) * glow.strength)
        scale: 1.0 + 0.16 * glow.pulse * glow.strength
    }
}
