import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Square artwork card for search results / recents. OK emits activated().
FocusScope {
    id: card
    property real u: 1
    property string imageUrl: ""
    property string title: ""
    property string subtitle: ""
    property string kind: "track"
    signal activated()

    width: 240 * u
    height: 240 * u + 100 * u

    Keys.onReturnPressed: (event) => { if (!event.isAutoRepeat) activated() }
    Keys.onEnterPressed: (event) => { if (!event.isAutoRepeat) activated() }
    Keys.onPressed: (event) => { if (event.key === Qt.Key_Select) { if (!event.isAutoRepeat) activated(); event.accepted = true } }

    readonly property string icon: ({ track: "media-optical-audio", album: "media-optical",
                                       artist: "view-media-artist", playlist: "view-media-playlist",
                                       radio: "radio" })[kind] || "media-optical-audio"

    Rectangle {
        id: artBox
        width: parent.width
        height: width
        radius: (kind === "artist" ? width / 2 : 14 * card.u)
        color: "#2b2163"
        clip: true
        scale: card.activeFocus ? 1.04 : 1
        Behavior on scale { NumberAnimation { duration: 120 } }
        Kirigami.Icon {
            anchors.centerIn: parent
            width: parent.width * 0.4
            height: width
            source: card.icon
            color: "#aaffffff"
            isMask: true
            visible: img.status !== Image.Ready
        }
        Image {
            id: img
            anchors.fill: parent
            source: card.imageUrl
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            sourceSize: Qt.size(256, 256)
            visible: status === Image.Ready
        }
    }
    Rectangle {  // focus ring: outside artBox, which clips its children
        anchors.fill: artBox
        anchors.margins: -10 * card.u
        scale: artBox.scale
        radius: artBox.radius + 10 * card.u
        color: "transparent"
        border.width: 6 * card.u
        border.color: "#4fc3f7"
        visible: card.activeFocus
    }
    ColumnLayout {
        anchors { left: parent.left; right: parent.right; top: artBox.bottom; topMargin: 16 * card.u }
        spacing: 2 * card.u
        QQC2.Label {
            Layout.fillWidth: true
            text: card.title
            color: "#ffffff"
            font.pixelSize: 28 * card.u
            font.weight: card.activeFocus ? Font.Bold : Font.Normal
            elide: Text.ElideRight
        }
        QQC2.Label {
            Layout.fillWidth: true
            visible: text !== ""
            text: card.subtitle
            color: "#ffffff"
            opacity: 0.7
            font.pixelSize: 24 * card.u
            elide: Text.ElideRight
        }
    }
    MouseArea { anchors.fill: parent; onClicked: { card.forceActiveFocus(); card.activated() } }
}
