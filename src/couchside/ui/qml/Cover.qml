pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects

// A cover picture with rounded corners and a soft shadow; a quiet note icon until (or
// without) a picture. Non-square pictures are cropped to fill. The rounding is a mask on
// the picture's own layer, the shadow a blurred dark shape under it: both are drawn again
// only when the picture or the size changes. (The shadow is not part of the mask's effect:
// with both switched on in one MultiEffect, Qt 6.11 drops the mask.)
Item {
    id: cover
    property url source
    property real radius: 28
    property bool shadow: true
    readonly property bool hasImage: picture.hasImage

    Item {   // the shadow
        visible: cover.shadow
        anchors.fill: parent
        anchors.topMargin: cover.height * 0.05
        anchors.bottomMargin: -cover.height * 0.05
        Rectangle {
            id: shade
            anchors.fill: parent
            anchors.margins: cover.width * 0.02
            radius: cover.radius
            color: "#000000"
            visible: false
            layer.enabled: true
        }
        MultiEffect {
            anchors.fill: shade
            source: shade
            blurEnabled: true
            blur: 1.0
            blurMax: 64
            autoPaddingEnabled: true
            opacity: 0.6
        }
    }

    Rectangle {   // the mask: a rounded shape the size of the picture
        id: shape
        anchors.fill: parent
        radius: cover.radius
        color: "#000000"
        visible: false
        layer.enabled: true
    }
    Item {
        id: content
        anchors.fill: parent
        visible: false
        layer.enabled: true
        Rectangle { anchors.fill: parent; color: "#16161f" }
        Icon {
            anchors.centerIn: parent
            size: parent.width * 0.3
            name: "music"
            color: "#40ffffff"
            visible: !picture.hasImage
        }
        CrossfadeImage {
            id: picture
            anchors.fill: parent
            source: cover.source
            // decode at the size shown: sharp on a 4K TV (the URL serves 1024 px)
            sourceSize: Qt.size(Math.ceil(cover.width), Math.ceil(cover.height))
        }
    }
    MultiEffect {
        anchors.fill: parent
        source: content
        maskEnabled: true
        maskSource: shape
        maskThresholdMin: 0.5
        maskSpreadAtMin: 1.0
    }
}
