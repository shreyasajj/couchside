pragma ComponentBehavior: Bound
import QtQuick

// The heading at the top of a screen that has no tab of its own to say where you are,
// with an optional second line.
Column {
    id: heading
    property real u: 1
    property string title: ""
    property string note: ""
    spacing: 6 * u
    Text {
        textFormat: Text.PlainText
        width: parent.width
        text: heading.title
        color: Theme.text
        font.pixelSize: Theme.title * heading.u
        font.weight: Font.ExtraBold
        elide: Text.ElideRight
    }
    Text {
        textFormat: Text.PlainText
        width: parent.width
        visible: heading.note !== ""
        text: heading.note
        color: Theme.textDim
        font.pixelSize: Theme.label * heading.u
        wrapMode: Text.WordWrap
    }
}
