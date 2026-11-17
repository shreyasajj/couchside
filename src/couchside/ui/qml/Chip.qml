import QtQuick
import QtQuick.Controls as QQC2

// A pill with a few words (and optionally a dot or an icon) for the top bar and the
// visualizer. OK/Enter/Select activates. Long text is cut at maxTextWidth.
QQC2.AbstractButton {
    id: chip
    property real u: 1
    property bool active: false          // "on": outlined and written in the first accent
    property bool warn: false            // something is wrong: outlined and written in amber
    property bool dot: false
    property color dotColor: Theme.a1
    property string iconName: ""
    property real maxTextWidth: 420 * u

    focusPolicy: Qt.StrongFocus
    topPadding: 11 * u
    bottomPadding: 11 * u
    leftPadding: 22 * u
    rightPadding: 22 * u
    Accessible.name: text

    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Select) { clicked(); event.accepted = true }
    }

    background: Item {
        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: chip.warn ? Theme.tint(Theme.warn, chip.activeFocus ? 0.28 : 0.16)
                   : chip.active ? Theme.tint(Theme.a1, 0.12) : (chip.activeFocus ? Theme.surfaceHigh : Theme.surface)
            border.width: Math.max(1, chip.u)
            border.color: chip.warn ? Theme.warn : chip.active ? Theme.a1 : Theme.border
        }
        FocusRing { anchors.fill: parent; u: chip.u; radius: height / 2; shown: chip.activeFocus }
    }
    contentItem: Row {
        spacing: 11 * chip.u
        Rectangle {
            visible: chip.dot
            anchors.verticalCenter: parent.verticalCenter
            width: 10 * chip.u; height: width; radius: width / 2
            color: chip.dotColor
        }
        Icon {
            visible: chip.iconName !== ""
            anchors.verticalCenter: parent.verticalCenter
            name: chip.iconName
            size: 28 * chip.u
            color: chip.warn ? Theme.warn : chip.active ? Theme.a1 : Theme.text
        }
        Text {
            visible: chip.text !== ""
            anchors.verticalCenter: parent.verticalCenter
            textFormat: Text.PlainText
            text: chip.text
            width: Math.min(implicitWidth, chip.maxTextWidth)
            elide: Text.ElideRight
            color: chip.warn ? Theme.warn : chip.active ? Theme.a1 : (chip.activeFocus ? Theme.text : Theme.textDim)
            font.pixelSize: Theme.label * chip.u
            font.weight: Font.Bold
        }
    }
}
