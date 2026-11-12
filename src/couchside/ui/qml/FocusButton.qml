import QtQuick
import QtQuick.Controls as QQC2

// Round icon button for the remote: OK/Enter/Select activates. Quiet until focused (just
// the icon); the focused button turns white, grows a little, gets a ring and shows its name.
QQC2.AbstractButton {
    id: control
    property string iconName: ""
    property bool primary: false   // play/pause: always a white disc
    property bool active: false    // on/off controls (shuffle, repeat): accent colour when on
    property real u: 1
    property real size: (primary ? 92 : 68) * u
    property real iconScale: 0.5
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
        scale: control.down ? 0.94 : (control.activeFocus ? 1.12 : 1.0)
        Behavior on scale { NumberAnimation { duration: Theme.focusMs; easing.type: Easing.OutCubic } }
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: control.lit ? Theme.focus : "transparent"
        }
        Rectangle {  // focus ring, a little outside the disc
            anchors.fill: parent
            anchors.margins: -9 * control.u
            radius: width / 2
            color: "transparent"
            border.width: 4 * control.u
            border.color: Theme.focus
            visible: control.activeFocus
        }
        Rectangle {  // "on" dot
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.bottom
            anchors.topMargin: (control.activeFocus ? 16 : 2) * control.u
            width: 8 * control.u
            height: width
            radius: width / 2
            color: Theme.accent
            visible: control.active
        }
    }

    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: control.iconName
            size: control.size * control.iconScale
            color: control.lit ? Theme.focusText : (control.active ? Theme.accent : Theme.text)
        }
    }

    Rectangle {  // the button's name, while focused
        visible: control.activeFocus && control.showLabel && control.text !== ""
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.top
        anchors.bottomMargin: 16 * control.u
        width: nameText.implicitWidth + 36 * control.u
        height: nameText.implicitHeight + 8 * control.u
        radius: height / 2
        color: "#cc000000"
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
