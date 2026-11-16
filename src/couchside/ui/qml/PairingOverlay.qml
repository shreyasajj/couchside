import QtQuick
import QtQuick.Layouts

// Shown while the Sendspin daemon waits for its pairing code to be entered in Music Assistant.
Rectangle {
    id: overlay
    property real u: 1
    anchors.fill: parent
    color: "#f007070b"
    // While shown it holds focus and swallows keys, so nothing hidden behind it reacts.
    // Back and media keys are window Shortcuts and still work.
    focus: visible
    Keys.onPressed: (event) => { event.accepted = true }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 32 * overlay.u
        Text {
            textFormat: Text.PlainText
            Layout.alignment: Qt.AlignHCenter
            text: "Pair this TV with Music Assistant"
            color: Theme.text
            font.pixelSize: 48 * overlay.u
            font.weight: Font.ExtraBold
        }
        Text {
            textFormat: Text.PlainText
            Layout.alignment: Qt.AlignHCenter
            text: "Enter this code in Music Assistant"
            color: Theme.textDim
            font.pixelSize: 34 * overlay.u
        }
        Text {
            textFormat: Text.PlainText
            Layout.alignment: Qt.AlignHCenter
            text: app.pairingCode
            color: Theme.a1
            font.pixelSize: 180 * overlay.u
            font.weight: Font.Black
            font.letterSpacing: 12 * overlay.u
        }
        Text {
            textFormat: Text.PlainText
            Layout.alignment: Qt.AlignHCenter
            text: "Press Back to hide"
            color: Theme.textFaint
            font.pixelSize: 28 * overlay.u
        }
    }
}
