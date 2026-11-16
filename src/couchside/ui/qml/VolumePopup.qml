import QtQuick
import QtQuick.Layouts

// Volume bar, shown low on the screen.
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
    radius: 24 * u
    color: Theme.panel
    border.width: (interactive ? 3 : 1) * u
    border.color: interactive ? Theme.a1 : Theme.border

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
            color: "#29ffffff"
            GradientFill {
                width: parent.width * popup.level / 100
                height: parent.height
                radius: height / 2
            }
        }
        Text {
            textFormat: Text.PlainText
            Layout.preferredWidth: 90 * popup.u
            horizontalAlignment: Text.AlignRight
            text: popup.level
            color: Theme.text
            font.pixelSize: 44 * popup.u
            font.weight: Font.Bold
            font.features: { "tnum": 1 }
        }
    }
}
