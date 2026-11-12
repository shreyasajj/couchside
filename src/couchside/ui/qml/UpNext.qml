import QtQuick

// "Up next" in the corner of Now Playing: the next song's name, artist and cover.
// Only to look at; never takes focus.
Rectangle {
    id: chip
    property real u: 1
    property string title: ""
    property string artist: ""
    property string imageUrl: ""
    property real maxTextWidth: 440 * u

    visible: title !== ""
    width: row.width + 36 * u
    height: row.height + 28 * u
    radius: 20 * u
    color: Theme.scrim

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 20 * chip.u
        Column {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2 * chip.u
            width: Math.min(chip.maxTextWidth, Math.max(caption.implicitWidth, name.implicitWidth))
            Text {
                id: caption
                textFormat: Text.PlainText
                width: parent.width
                horizontalAlignment: Text.AlignRight
                text: "Up next"
                color: Theme.textDim
                font.pixelSize: Theme.label * chip.u
            }
            Text {
                id: name
                textFormat: Text.PlainText
                width: parent.width
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideRight
                text: chip.artist !== "" ? chip.title + " · " + chip.artist : chip.title
                color: Theme.text
                font.pixelSize: Theme.label * chip.u
                font.weight: Font.DemiBold
            }
        }
        Rectangle {
            width: 84 * chip.u
            height: width
            radius: 10 * chip.u
            color: Theme.surfaceHigh
            visible: chip.imageUrl !== ""
            Image {
                anchors.fill: parent
                anchors.margins: 0
                source: chip.imageUrl
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize: Qt.size(width, height)
            }
        }
    }
}
