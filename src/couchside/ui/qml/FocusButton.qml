import QtQuick
import QtQuick.Controls as QQC2

// Round icon button for the remote: OK/Enter/Select activates. Just the icon until
// focused; the focused one gets the accent ring and shows its name. `primary` (play/pause)
// is always a disc in the accent gradient.
QQC2.AbstractButton {
    id: control
    property string iconName: ""
    property bool primary: false   // play/pause: the gradient disc
    property bool active: false    // on/off controls (shuffle, repeat): accent colour when on
    property real u: 1
    property real size: (primary ? 116 : 76) * u
    property real iconScale: primary ? 0.45 : 0.62
    property bool showLabel: true  // the name above the button while it has focus
    readonly property bool lit: activeFocus || primary

    implicitWidth: size
    implicitHeight: size
    focusPolicy: Qt.StrongFocus
    Accessible.name: text

    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Select) { clicked(); event.accepted = true }
    }

    background: Item {
        scale: control.down ? 0.94 : (control.activeFocus ? 1.08 : 1.0)
        Behavior on scale { NumberAnimation { duration: Theme.focusMs; easing.type: Easing.OutCubic } }
        Rectangle {  // the play button's halo
            visible: control.primary
            anchors.fill: parent
            anchors.margins: -14 * control.u
            radius: width / 2
            color: Theme.tint(Theme.a2, 0.14)
        }
        GradientFill { visible: control.primary; anchors.fill: parent; radius: width / 2 }
        Rectangle {
            visible: !control.primary && control.activeFocus
            anchors.fill: parent
            radius: width / 2
            color: Theme.surfaceHigh
        }
        FocusRing { anchors.fill: parent; u: control.u; radius: width / 2; shown: control.activeFocus }
        Rectangle {  // "on" dot
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.bottom
            anchors.topMargin: (control.activeFocus ? 14 : 2) * control.u
            width: 8 * control.u
            height: width
            radius: width / 2
            color: Theme.a1
            visible: control.active
        }
    }

    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: control.iconName
            size: control.size * control.iconScale
            color: control.primary ? Theme.ink : (control.active ? Theme.a1 : Theme.text)
            opacity: control.lit || control.active ? 1 : 0.9
        }
    }

    Rectangle {  // the button's name, while focused
        visible: control.activeFocus && control.showLabel && control.text !== ""
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.top
        anchors.bottomMargin: 18 * control.u
        width: nameText.implicitWidth + 36 * control.u
        height: nameText.implicitHeight + 10 * control.u
        radius: height / 2
        color: Theme.panel
        border.width: Math.max(1, control.u)
        border.color: Theme.border
        Text {
            id: nameText
            anchors.centerIn: parent
            textFormat: Text.PlainText
            text: control.text
            color: Theme.text
            font.pixelSize: Theme.label * control.u
            font.weight: Font.DemiBold
        }
    }
}
