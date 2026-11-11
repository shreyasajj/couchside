import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2

// Thin progress line with elapsed / −remaining. Not focusable (no seeking in this phase).
ColumnLayout {
    id: progress
    property real u: 1
    property real position: 0
    property real duration: 0
    readonly property bool known: duration > 0
    spacing: 14 * u

    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: 6 * progress.u
        radius: height / 2
        color: "#33ffffff"
        visible: progress.known
        Rectangle {
            width: parent.width * Math.max(0, Math.min(1, progress.position / Math.max(1, progress.duration)))
            height: parent.height
            radius: height / 2
            color: "#ffffff"
        }
    }
    RowLayout {
        Layout.fillWidth: true
        QQC2.Label {
            textFormat: Text.PlainText
            text: app.formatTime(progress.position)
            color: "#ffffff"
            opacity: 0.8
            font.pixelSize: 28 * progress.u
            font.features: { "tnum": 1 }
        }
        Item { Layout.fillWidth: true }
        QQC2.Label {
            textFormat: Text.PlainText
            visible: progress.known
            text: "−" + app.formatTime(Math.max(0, progress.duration - progress.position))
            color: "#ffffff"
            opacity: 0.8
            font.pixelSize: 28 * progress.u
            font.features: { "tnum": 1 }
        }
    }
}
