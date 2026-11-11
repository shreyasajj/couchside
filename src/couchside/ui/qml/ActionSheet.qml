import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2

// Modal list of big actions. open(title, [{id, label}], opener, callback(id)).
// Up/Down move, OK runs one action and closes (once), Back closes; focus goes back to the
// opener, or focusLost() is emitted when the opener was destroyed meanwhile (list rows are
// rebuilt whenever their data changes). OK within 300 ms of opening, or held-down OK
// (auto-repeat), is ignored so a double press on the opener can't run the first action.
Rectangle {
    id: sheet
    property real u: 1
    property string title: ""
    property var actions: []
    property Item opener: null
    property var callback: null
    property double openedAt: 0
    signal focusLost()

    anchors.fill: parent
    color: "#b3000000"
    visible: false
    z: 200

    function open(t, acts, from, cb) {
        title = t
        actions = acts
        opener = from
        callback = cb
        openedAt = Date.now()
        visible = true
        Qt.callLater(function() { if (list.count > 0) { list.currentIndex = 0; list.forceActiveFocus() } })
    }
    function close() {
        if (!visible) return
        visible = false
        if (opener) opener.forceActiveFocus()
        else focusLost()
    }
    function run(index) {
        if (!visible || index < 0 || index >= actions.length) return  // ignore a second OK
        if (Date.now() - openedAt < 300) return                       // double press on the opener
        var id = actions[index].id
        var cb = callback
        close()
        if (cb) cb(id)
    }

    MouseArea { anchors.fill: parent; onClicked: sheet.close() }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width * 0.5, 900 * sheet.u)
        height: column.implicitHeight + 64 * sheet.u
        radius: 20 * sheet.u
        color: "#1d1840"

        ColumnLayout {
            id: column
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 32 * sheet.u }
            spacing: 20 * sheet.u
            QQC2.Label {
                textFormat: Text.PlainText
                Layout.fillWidth: true
                text: sheet.title
                color: "#ffffff"
                font.pixelSize: 40 * sheet.u
                font.weight: Font.Bold
                elide: Text.ElideRight
                maximumLineCount: 2
                wrapMode: Text.WordWrap
            }
            ListView {
                id: list
                Layout.fillWidth: true
                Layout.preferredHeight: contentHeight
                interactive: false
                spacing: 12 * sheet.u
                model: sheet.actions
                keyNavigationEnabled: true
                delegate: Rectangle {
                    id: actionItem
                    required property var modelData
                    required property int index
                    width: ListView.view.width
                    height: 84 * sheet.u
                    radius: 12 * sheet.u
                    color: ListView.isCurrentItem && list.activeFocus ? "#ffffff" : "#26ffffff"
                    border.width: ListView.isCurrentItem && list.activeFocus ? 5 * sheet.u : 0
                    border.color: "#4fc3f7"
                    QQC2.Label {
                        textFormat: Text.PlainText
                        anchors.verticalCenter: parent.verticalCenter
                        x: 28 * sheet.u
                        text: actionItem.modelData.label
                        color: actionItem.ListView.isCurrentItem && list.activeFocus ? "#000000" : "#ffffff"
                        font.pixelSize: 32 * sheet.u
                    }
                    MouseArea { anchors.fill: parent; onClicked: sheet.run(actionItem.index) }
                }
                Keys.onReturnPressed: (event) => { if (!event.isAutoRepeat) sheet.run(currentIndex) }
                Keys.onEnterPressed: (event) => { if (!event.isAutoRepeat) sheet.run(currentIndex) }
                Keys.onPressed: (event) => {
                    if (event.key === Qt.Key_Select) { if (!event.isAutoRepeat) sheet.run(currentIndex); event.accepted = true }
                    else if (event.key === Qt.Key_Left || event.key === Qt.Key_Right) event.accepted = true
                }
            }
        }
    }
}
