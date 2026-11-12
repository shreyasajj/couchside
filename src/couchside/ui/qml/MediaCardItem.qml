import QtQuick
import QtQuick.Layouts

// Square artwork card for search results / recents. OK emits activated().
// The focused card grows a little and gets a white ring.
FocusScope {
    id: card
    property real u: 1
    property string imageUrl: ""
    property string title: ""
    property string subtitle: ""
    property string kind: "track"
    signal activated()

    width: 240 * u
    height: 240 * u + 112 * u

    Keys.onReturnPressed: (event) => { if (!event.isAutoRepeat) activated() }
    Keys.onEnterPressed: (event) => { if (!event.isAutoRepeat) activated() }
    Keys.onPressed: (event) => { if (event.key === Qt.Key_Select) { if (!event.isAutoRepeat) activated(); event.accepted = true } }

    readonly property string icon: ({ track: "music", album: "album", artist: "person",
                                       playlist: "queue", radio: "radio" })[kind] || "music"

    Rectangle {
        id: artBox
        width: parent.width
        height: width
        radius: (kind === "artist" ? width / 2 : 16 * card.u)
        color: Theme.surfaceHigh
        clip: true
        scale: card.activeFocus ? 1.05 : 1
        Behavior on scale { NumberAnimation { duration: Theme.focusMs; easing.type: Easing.OutCubic } }
        Icon {
            anchors.centerIn: parent
            size: parent.width * 0.4
            name: card.icon
            opacity: 0.6
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
        border.width: 5 * card.u
        border.color: Theme.focus
        visible: card.activeFocus
    }
    ColumnLayout {
        anchors { left: parent.left; right: parent.right; top: artBox.bottom; topMargin: 20 * card.u }
        spacing: 2 * card.u
        Text {
            textFormat: Text.PlainText
            Layout.fillWidth: true
            text: card.title
            color: Theme.text
            font.pixelSize: Theme.label * card.u
            font.weight: card.activeFocus ? Font.Bold : Font.Normal
            elide: Text.ElideRight
        }
        Text {
            textFormat: Text.PlainText
            Layout.fillWidth: true
            visible: text !== ""
            text: card.subtitle
            color: Theme.textDim
            font.pixelSize: Theme.label * card.u
            elide: Text.ElideRight
        }
    }
    MouseArea { anchors.fill: parent; onClicked: { card.forceActiveFocus(); card.activated() } }
}
