import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Big round TV button: OK/Enter/Select activates, clear focus ring.
QQC2.AbstractButton {
    id: control
    property string iconName: ""
    property bool primary: false
    property bool active: false  // on/off controls (shuffle, repeat): accent dot when on
    property real u: 1
    property real size: (primary ? 132 : 104) * u

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
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: control.primary ? "#ffffff" : (control.activeFocus ? "#33ffffff" : "#22ffffff")
            scale: control.down ? 0.94 : 1.0
            Behavior on scale { NumberAnimation { duration: 80 } }
        }
        Rectangle {  // "on" indicator
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 12 * control.u
            width: 12 * control.u
            height: width
            radius: width / 2
            color: "#4fc3f7"
            visible: control.active
        }
        Rectangle {  // focus ring
            anchors.fill: parent
            anchors.margins: -10 * control.u
            radius: width / 2
            color: "transparent"
            border.width: 5 * control.u
            border.color: "#4fc3f7"
            visible: control.activeFocus
        }
    }

    contentItem: Kirigami.Icon {
        source: control.iconName
        color: control.primary ? "#000000" : "#ffffff"
        isMask: true
        anchors.centerIn: parent
        width: control.size * 0.45
        height: width
    }
}
