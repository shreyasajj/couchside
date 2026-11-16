import QtQuick
import QtQuick.Controls as QQC2

// A button with words on it. Quiet until focused; the focused one gets the accent ring.
// `strong` fills it with the accent gradient (the one thing to do on a page, a chosen mode).
QQC2.AbstractButton {
    id: control
    property real u: 1
    property bool dim: false     // looks unavailable (the action explains why when pressed)
    property bool strong: false

    focusPolicy: Qt.StrongFocus
    font.pixelSize: Theme.body * u
    font.weight: Font.Bold
    topPadding: 18 * u
    bottomPadding: 18 * u
    leftPadding: 40 * u
    rightPadding: 40 * u
    Accessible.name: text

    Keys.onReturnPressed: if (enabled) clicked()
    Keys.onEnterPressed: if (enabled) clicked()
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Select) { if (enabled) clicked(); event.accepted = true }
    }

    background: Item {
        opacity: control.enabled && !control.dim ? 1 : 0.5
        scale: control.down ? 0.97 : (control.activeFocus ? 1.03 : 1.0)
        Behavior on scale { NumberAnimation { duration: Theme.focusMs; easing.type: Easing.OutCubic } }
        Rectangle {
            visible: !control.strong
            anchors.fill: parent
            radius: height / 2
            color: control.activeFocus ? Theme.surfaceHigh : Theme.surface
            border.width: Math.max(1, control.u)
            border.color: Theme.border
        }
        GradientFill { visible: control.strong; anchors.fill: parent; radius: height / 2 }
        FocusRing { anchors.fill: parent; u: control.u; radius: height / 2; shown: control.activeFocus }
    }
    contentItem: Text {
        textFormat: Text.PlainText
        text: control.text
        font: control.font
        color: control.strong ? Theme.ink : (control.activeFocus ? Theme.text : Theme.textDim)
        opacity: control.enabled && !control.dim ? 1 : 0.6
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
