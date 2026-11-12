import QtQuick
import QtQuick.Controls as QQC2

// A button with words on it. Quiet until focused; the focused one is white with dark text.
QQC2.AbstractButton {
    id: control
    property real u: 1
    property bool dim: false  // looks unavailable (the action explains why when pressed)

    focusPolicy: Qt.StrongFocus
    font.pixelSize: Theme.body * u
    topPadding: 20 * u
    bottomPadding: 20 * u
    leftPadding: 40 * u
    rightPadding: 40 * u
    Accessible.name: text

    Keys.onReturnPressed: if (enabled) clicked()
    Keys.onEnterPressed: if (enabled) clicked()
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Select) { if (enabled) clicked(); event.accepted = true }
    }

    background: Rectangle {
        radius: height / 2
        color: control.activeFocus ? Theme.focus : Theme.surfaceHigh
        opacity: control.enabled && !control.dim ? 1 : 0.6
        scale: control.down ? 0.97 : (control.activeFocus ? 1.04 : 1.0)
        Behavior on scale { NumberAnimation { duration: Theme.focusMs; easing.type: Easing.OutCubic } }
    }
    contentItem: Text {
        textFormat: Text.PlainText
        text: control.text
        font: control.font
        color: control.activeFocus ? Theme.focusText : Theme.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
