import QtQuick
import QtQuick.Layouts

// Elapsed time, a thin progress line, time left: one row. Not focusable (no seeking).
RowLayout {
    id: progress
    property real u: 1
    property real position: 0
    property real duration: 0
    readonly property bool known: duration > 0
    spacing: 24 * u

    Text {
        textFormat: Text.PlainText
        text: app.formatTime(progress.position)
        color: Theme.textDim
        font.pixelSize: Theme.label * progress.u
        font.features: { "tnum": 1 }
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: 6 * progress.u
        radius: height / 2
        color: Theme.surfaceHigh
        opacity: progress.known ? 1 : 0
        Rectangle {
            width: parent.width * Math.max(0, Math.min(1, progress.position / Math.max(1, progress.duration)))
            height: parent.height
            radius: height / 2
            color: Theme.text
        }
    }
    Text {
        textFormat: Text.PlainText
        visible: progress.known
        text: "−" + app.formatTime(Math.max(0, progress.duration - progress.position))
        color: Theme.textDim
        font.pixelSize: Theme.label * progress.u
        font.features: { "tnum": 1 }
    }
}
