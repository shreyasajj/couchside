import QtQuick
import QtQuick.Controls as QQC2

// Short message at the bottom for 4 s (failed actions). Never takes focus.
Rectangle {
    id: toast
    property real u: 1
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 220 * u
    width: label.implicitWidth + 64 * u
    height: label.implicitHeight + 32 * u
    radius: height / 2
    color: "#e6301818"
    visible: app.toast !== ""
    z: 300

    QQC2.Label {
        id: label
        anchors.centerIn: parent
        text: app.toast
        color: "#ffffff"
        font.pixelSize: 30 * toast.u
    }
    Timer {
        interval: 4000
        running: toast.visible
        onTriggered: app.clearToast()
    }
}
