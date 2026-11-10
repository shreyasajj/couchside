import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2

// Shown while the Sendspin daemon waits for its pairing code to be entered in Music Assistant.
Rectangle {
    id: overlay
    property real u: 1
    anchors.fill: parent
    color: "#e6000000"
    visible: app.pairingCode !== ""

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 32 * overlay.u
        QQC2.Label {
            Layout.alignment: Qt.AlignHCenter
            text: "Pair this TV with Music Assistant"
            color: "#ffffff"
            font.pixelSize: 48 * overlay.u
            font.weight: Font.Bold
        }
        QQC2.Label {
            Layout.alignment: Qt.AlignHCenter
            text: "Enter this code in Music Assistant"
            color: "#ffffff"
            opacity: 0.8
            font.pixelSize: 34 * overlay.u
        }
        QQC2.Label {
            Layout.alignment: Qt.AlignHCenter
            text: app.pairingCode
            color: "#ffffff"
            font.pixelSize: 180 * overlay.u
            font.weight: Font.Black
            font.letterSpacing: 12 * overlay.u
        }
    }
}
