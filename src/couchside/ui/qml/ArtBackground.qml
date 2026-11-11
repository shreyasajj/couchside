import QtQuick
import QtQuick.Effects

// Full-screen blurred artwork over the album's palette colour, darkened toward the bottom.
// The blur runs on a small copy that is scaled up: cheap enough for a Raspberry Pi,
// and a heavy blur looks the same either way.
Item {
    id: bg
    property url source
    property color baseColour: "#0d0b1a"
    // Kirigami's page transitions read `background.color` (opaque = slide behind).
    readonly property color color: baseColour
    readonly property real blurWidth: 384

    Rectangle {
        anchors.fill: parent
        color: bg.baseColour
        Behavior on color { ColorAnimation { duration: 600 } }
    }

    Item {
        id: small
        width: bg.blurWidth
        height: bg.width > 0 ? bg.blurWidth * bg.height / bg.width : 0
        scale: bg.width / bg.blurWidth
        transformOrigin: Item.TopLeft
        opacity: art.hasImage ? 0.85 : 0
        Behavior on opacity { NumberAnimation { duration: 500 } }

        CrossfadeImage {
            id: art
            anchors.fill: parent
            source: bg.source
            sourceSize: Qt.size(bg.blurWidth, bg.blurWidth)
            visible: false
        }
        MultiEffect {
            anchors.fill: parent
            source: art
            autoPaddingEnabled: false
            blurEnabled: true
            blur: 1.0
            blurMax: 32
            saturation: 0.15
        }
    }

    Rectangle {  // scrim: keeps text readable on any artwork
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#59000000" }
            GradientStop { position: 0.55; color: "#8c000000" }
            GradientStop { position: 1.0; color: "#d9000000" }
        }
    }
}
