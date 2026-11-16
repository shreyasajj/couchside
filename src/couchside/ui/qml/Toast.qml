import QtQuick

// Short message at the bottom for 4 s (failed actions). Never takes focus.
Rectangle {
    id: toast
    property real u: 1
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 72 * u
    width: Math.min(parent.width - 2 * Theme.margin * u, label.implicitWidth + 72 * u)
    height: label.implicitHeight + 32 * u
    radius: height / 2
    color: Theme.panel
    border.width: 2 * u
    border.color: Theme.tint(Theme.a2, 0.7)
    visible: app.toast !== ""
    z: 300

    Text {
        id: label
        textFormat: Text.PlainText
        anchors.centerIn: parent
        width: Math.min(implicitWidth, parent.width - 72 * toast.u)
        elide: Text.ElideRight
        text: app.toast
        color: Theme.text
        font.pixelSize: Theme.label * toast.u
        font.weight: Font.DemiBold
    }
    Timer {
        interval: 4000
        running: toast.visible
        onTriggered: app.clearToast()
    }
}
