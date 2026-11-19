pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts

// The one-time admin code, large enough to read from the couch. Back cancels it.
Rectangle {
    id: overlay
    property real u: 1
    anchors.fill: parent
    color: "#f007070b"
    // While shown it holds focus and swallows keys; Back is a window Shortcut.
    focus: visible
    Keys.onPressed: (event) => { event.accepted = true }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 160 * overlay.u, 1500 * overlay.u)
        spacing: 32 * overlay.u
        Text {
            textFormat: Text.PlainText
            Layout.alignment: Qt.AlignHCenter
            text: "Admin code"
            color: Theme.text
            font.pixelSize: 48 * overlay.u
            font.weight: Font.ExtraBold
        }
        Text {
            textFormat: Text.PlainText
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: "On the guest page, tap “Have an admin code from the host?” and enter:"
            color: Theme.textDim
            font.pixelSize: 34 * overlay.u
        }
        Text {
            objectName: "adminCodeText"
            textFormat: Text.PlainText
            Layout.alignment: Qt.AlignHCenter
            text: app.adminCode.length === 6 ? app.adminCode.slice(0, 3) + " " + app.adminCode.slice(3) : app.adminCode
            color: Theme.a1
            font.pixelSize: 180 * overlay.u
            font.weight: Font.Black
            font.letterSpacing: 12 * overlay.u
        }
        Text {
            textFormat: Text.PlainText
            Layout.alignment: Qt.AlignHCenter
            text: "Works once, for 10 minutes · Back to cancel"
            color: Theme.textFaint
            font.pixelSize: 28 * overlay.u
        }
    }
}
