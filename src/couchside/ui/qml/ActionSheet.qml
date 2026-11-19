pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts

// Modal list of big actions, also used to pick one of several choices.
// open(title, [{id, label, checked?, section?, a1?, a2?}], opener, callback(id)).
// `checked` puts a tick on a choice and the sheet opens on it; `section` puts a small
// heading above the first action of each section; a1/a2 show two colour dots.
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
    property alias currentIndex: list.currentIndex
    signal focusLost()

    anchors.fill: parent
    color: Theme.scrim
    visible: false
    z: 200

    function open(t, acts, from, cb) {
        title = t
        actions = acts
        opener = from
        callback = cb
        openedAt = Date.now()
        visible = true
        var start = 0
        for (let i = 0; i < acts.length; i++) if (acts[i].checked) { start = i; break }
        Qt.callLater(function() {
            if (list.count > 0) {
                list.currentIndex = start
                list.positionViewAtIndex(start, ListView.Contain)
                list.forceActiveFocus()
            }
        })
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
        radius: 24 * sheet.u
        color: Theme.panel
        border.width: Math.max(1, sheet.u)
        border.color: Theme.border

        ColumnLayout {
            id: column
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 32 * sheet.u }
            spacing: 20 * sheet.u
            Text {
                textFormat: Text.PlainText
                Layout.fillWidth: true
                text: sheet.title
                color: Theme.text
                font.pixelSize: Theme.heading * sheet.u
                font.weight: Font.ExtraBold
                elide: Text.ElideRight
                maximumLineCount: 2
                wrapMode: Text.WordWrap
            }
            ListView {
                id: list
                Layout.fillWidth: true
                // long lists (audio devices) scroll inside the sheet
                Layout.preferredHeight: Math.min(contentHeight, sheet.height * 0.62)
                clip: true
                interactive: false
                spacing: 12 * sheet.u
                model: sheet.actions
                keyNavigationEnabled: true
                highlightMoveDuration: 0
                delegate: Column {
                    id: actionItem
                    required property var modelData
                    required property int index
                    readonly property bool current: ListView.isCurrentItem && list.activeFocus
                    readonly property string section: modelData.section || ""
                    readonly property bool startsSection: section !== ""
                        && (index === 0 || (sheet.actions[index - 1].section || "") !== section)
                    width: ListView.view.width
                    spacing: 10 * sheet.u
                    Text {
                        objectName: "sectionHeading"
                        textFormat: Text.PlainText
                        visible: actionItem.startsSection
                        topPadding: 10 * sheet.u
                        leftPadding: 6 * sheet.u
                        width: parent.width
                        elide: Text.ElideRight
                        text: actionItem.section
                        color: Theme.textFaint
                        font.pixelSize: Theme.label * sheet.u
                        font.weight: Font.Bold
                    }
                    Item {
                        width: parent.width
                        height: 84 * sheet.u
                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 3 * sheet.u   // room for the ring inside the clipped list
                            radius: 16 * sheet.u
                            color: actionItem.current ? Theme.tint(Theme.a1, 0.22) : Theme.surface
                            border.width: (actionItem.current ? 3 : 1) * sheet.u
                            border.color: actionItem.current ? Theme.a1 : Theme.border
                        }
                        RowLayout {
                            anchors { fill: parent; leftMargin: 28 * sheet.u; rightMargin: 28 * sheet.u }
                            spacing: 16 * sheet.u
                            Row {
                                visible: !!actionItem.modelData.a1
                                spacing: -10 * sheet.u
                                Repeater {
                                    model: actionItem.modelData.a1 ? [actionItem.modelData.a1, actionItem.modelData.a2] : []
                                    delegate: Rectangle {
                                        required property string modelData
                                        width: 36 * sheet.u; height: width; radius: width / 2
                                        color: modelData
                                        border.width: 2 * sheet.u
                                        border.color: Theme.bg
                                    }
                                }
                            }
                            Text {
                                textFormat: Text.PlainText
                                Layout.fillWidth: true
                                text: actionItem.modelData.label
                                color: Theme.text
                                font.pixelSize: Theme.body * sheet.u
                                font.weight: actionItem.modelData.checked ? Font.Bold : Font.Medium
                                elide: Text.ElideRight
                            }
                            Icon {
                                objectName: "tick"
                                visible: !!actionItem.modelData.checked
                                name: "check"
                                size: 36 * sheet.u
                                color: Theme.a1
                            }
                        }
                        MouseArea { anchors.fill: parent; onClicked: sheet.run(actionItem.index) }
                    }
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
