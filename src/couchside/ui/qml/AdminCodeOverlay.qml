import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2

// The one-time admin code, large enough to read from the couch. Back cancels it.
Rectangle {
    id: overlay
    property real u: 1
    anchors.fill: parent
    color: "#e6000000"
    // While shown it holds focus and swallows keys; Back is a window Shortcut.
    focus: visible
    Keys.onPressed: (event) => { event.accepted = true }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 160 * overlay.u, 1500 * overlay.u)
        spacing: 32 * overlay.u
        QQC2.Label {
            textFormat: Text.PlainText
            Layout.alignment: Qt.AlignHCenter
            text: "Admin code"
            color: "#ffffff"
            font.pixelSize: 48 * overlay.u
            font.weight: Font.Bold
        }
        QQC2.Label {
            textFormat: Text.PlainText
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: "On the guest page, tap “Have an admin code from the host?” and enter:"
            color: "#ffffff"
            opacity: 0.8
            font.pixelSize: 34 * overlay.u
        }
        QQC2.Label {
            objectName: "adminCodeText"
            textFormat: Text.PlainText
            Layout.alignment: Qt.AlignHCenter
            text: app.adminCode.length === 6 ? app.adminCode.slice(0, 3) + " " + app.adminCode.slice(3) : app.adminCode
            color: "#ffffff"
            font.pixelSize: 180 * overlay.u
            font.weight: Font.Black
            font.letterSpacing: 12 * overlay.u
        }
        QQC2.Label {
            textFormat: Text.PlainText
            Layout.alignment: Qt.AlignHCenter
            text: "Works once, for 10 minutes · Back to cancel"
            color: "#ffffff"
            opacity: 0.6
            font.pixelSize: 28 * overlay.u
        }
    }
}
