import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2

// Volume bar shown above the volume button.
// open(true): takes focus; Left/Right change by 5, OK/Back close, closes after 4 s idle.
// flash(delta): remote volume keys; changes volume and shows the bar without taking focus.
Rectangle {
    id: popup
    property real u: 1
    property Item opener: null
    property int level: 0
    readonly property bool interactive: activeFocus
    signal closed()

    visible: false
    width: 520 * u
    height: 132 * u
    radius: 20 * u
    color: "#e6141024"
    border.width: interactive ? 5 * u : 0
    border.color: "#4fc3f7"

    function syncLevel() { if (!settle.running) level = Math.max(0, app.volume) }
    function change(delta) {
        level = Math.max(0, Math.min(100, level + delta))
        app.setVolume(level)
        settle.restart()
        idle.restart()
    }
    function open(takeFocus) {
        syncLevel()
        visible = true
        idle.restart()
        if (takeFocus) forceActiveFocus()
    }
    function flash(delta) {
        if (!visible) open(false)
        change(delta)
    }
    function close() {
        if (!visible) return
        var hadFocus = activeFocus
        visible = false
        idle.stop()
        if (hadFocus && opener) opener.forceActiveFocus()
        closed()
    }

    // Ignore server echoes for a moment after a change so quick presses don't jump back.
    Timer { id: settle; interval: 1500 }
    Timer { id: idle; interval: 4000; onTriggered: popup.close() }
    Connections { target: app; function onChanged() { popup.syncLevel() } }

    Keys.onLeftPressed: change(-5)
    Keys.onRightPressed: change(5)
    Keys.onReturnPressed: close()
    Keys.onEnterPressed: close()
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Select) { close(); event.accepted = true }
        else if (event.key === Qt.Key_Up || event.key === Qt.Key_Down) event.accepted = true
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 28 * popup.u
        spacing: 24 * popup.u
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 10 * popup.u
            radius: height / 2
            color: "#33ffffff"
            Rectangle {
                width: parent.width * popup.level / 100
                height: parent.height
                radius: height / 2
                color: "#ffffff"
            }
        }
        QQC2.Label {
            textFormat: Text.PlainText
            Layout.preferredWidth: 90 * popup.u
            horizontalAlignment: Text.AlignRight
            text: popup.level
            color: "#ffffff"
            font.pixelSize: 44 * popup.u
            font.weight: Font.Bold
            font.features: { "tnum": 1 }
        }
    }
}
