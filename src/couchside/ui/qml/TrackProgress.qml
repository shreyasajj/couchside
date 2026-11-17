import QtQuick
import QtQuick.Layouts

// Elapsed time, a progress line in the accent gradient, the song's length: one row.
// Not focusable (no seeking).
RowLayout {
    id: progress
    property real u: 1
    property real position: 0
    property real duration: 0
    readonly property bool known: duration > 0
    spacing: 24 * u

    Text {
        textFormat: Text.PlainText
        Layout.preferredWidth: 96 * progress.u
        text: app.formatTime(progress.position)
        color: "#b8ffffff"
        font.pixelSize: Theme.label * progress.u
        font.features: { "tnum": 1 }
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: 8 * progress.u
        radius: height / 2
        color: "#29ffffff"
        opacity: progress.known ? 1 : 0
        clip: true
        GradientFill {
            width: parent.width * Math.max(0, Math.min(1, progress.position / Math.max(1, progress.duration)))
            height: parent.height
            radius: height / 2
        }
    }
    Text {
        textFormat: Text.PlainText
        Layout.preferredWidth: 96 * progress.u
        horizontalAlignment: Text.AlignRight
        opacity: progress.known ? 1 : 0
        text: app.formatTime(progress.duration)
        color: "#b8ffffff"
        font.pixelSize: Theme.label * progress.u
        font.features: { "tnum": 1 }
    }
}
