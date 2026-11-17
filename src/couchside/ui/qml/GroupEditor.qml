import QtQuick
import QtQuick.Layouts

// Pick the speakers in a group. open(groupId or "", memberIds, opener).
// OK toggles a speaker; Save creates or updates the group (needs two or more).
Rectangle {
    id: editor
    property real u: 1
    property string groupId: ""
    property var chosen: []
    property Item opener: null
    signal focusLost()  // opener destroyed while open (see ActionSheet)

    anchors.fill: parent
    color: Theme.scrim
    visible: false
    z: 200

    readonly property var candidates: app.speakerRows.filter(function(r) { return !r.isGroup && r.available })

    function open(id, members, from) {
        groupId = id
        chosen = members.slice()
        opener = from
        visible = true
        Qt.callLater(function() { list.currentIndex = 0; list.forceActiveFocus() })
    }
    function close() {
        if (!visible) return
        visible = false
        if (opener) opener.forceActiveFocus()
        else focusLost()
    }
    function toggle(id) {
        var c = chosen.slice()
        var i = c.indexOf(id)
        if (i >= 0) c.splice(i, 1); else c.push(id)
        chosen = c
    }
    function save() {
        if (chosen.length < 2) return
        if (groupId === "") app.createGroup(chosen)
        else app.editGroup(groupId, chosen)
        close()
    }

    MouseArea { anchors.fill: parent; onClicked: editor.close() }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width * 0.55, 1000 * editor.u)
        height: column.implicitHeight + 64 * editor.u
        radius: 24 * editor.u
        color: Theme.panel
        border.width: Math.max(1, editor.u)
        border.color: Theme.border

        ColumnLayout {
            id: column
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 32 * editor.u }
            spacing: 20 * editor.u
            Text {
                textFormat: Text.PlainText
                text: editor.groupId === "" ? "New group" : "Edit group"
                color: Theme.text
                font.pixelSize: Theme.heading * editor.u
                font.weight: Font.ExtraBold
            }
            Text {
                textFormat: Text.PlainText
                text: "Pick two or more speakers to play in sync"
                color: Theme.textDim
                font.pixelSize: Theme.label * editor.u
            }
            ListView {
                id: list
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(contentHeight, 600 * editor.u)
                clip: true
                spacing: 10 * editor.u
                model: editor.candidates
                keyNavigationEnabled: true
                Keys.onDownPressed: (event) => {
                    if (currentIndex >= count - 1) saveButton.forceActiveFocus()
                    else incrementCurrentIndex()
                }
                delegate: Item {
                    id: option
                    required property var modelData
                    readonly property bool on: editor.chosen.indexOf(modelData.playerId) >= 0
                    readonly property bool lit: ListView.isCurrentItem && list.activeFocus
                    width: ListView.view.width
                    height: 84 * editor.u
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 3 * editor.u   // room for the outline inside the clipped list
                        radius: 16 * editor.u
                        color: option.lit ? Theme.tint(Theme.a1, 0.22) : Theme.surface
                        border.width: (option.lit ? 3 : 1) * editor.u
                        border.color: option.lit ? Theme.a1 : Theme.border
                    }
                    RowLayout {
                        anchors { fill: parent; leftMargin: 28 * editor.u; rightMargin: 28 * editor.u }
                        spacing: 20 * editor.u
                        Rectangle {
                            Layout.preferredWidth: 38 * editor.u
                            Layout.preferredHeight: 38 * editor.u
                            radius: 10 * editor.u
                            color: option.on ? Theme.a1 : "transparent"
                            border.width: 3 * editor.u
                            border.color: option.on ? Theme.a1 : Theme.textDim
                            Icon {
                                anchors.centerIn: parent
                                visible: option.on
                                name: "check"
                                size: 28 * editor.u
                                color: Theme.ink
                            }
                        }
                        Text {
                            textFormat: Text.PlainText
                            Layout.fillWidth: true
                            text: option.modelData.name
                            color: Theme.text
                            font.pixelSize: Theme.body * editor.u
                            font.weight: option.on ? Font.Bold : Font.Medium
                            elide: Text.ElideRight
                        }
                    }
                    MouseArea { anchors.fill: parent; onClicked: editor.toggle(option.modelData.playerId) }
                }
                Keys.onReturnPressed: editor.toggle(model[currentIndex].playerId)
                Keys.onEnterPressed: editor.toggle(model[currentIndex].playerId)
                Keys.onPressed: (event) => {
                    if (event.key === Qt.Key_Select) { editor.toggle(model[currentIndex].playerId); event.accepted = true }
                }
            }
            RowLayout {
                spacing: 24 * editor.u
                PillButton {
                    id: saveButton
                    u: editor.u
                    strong: editor.chosen.length >= 2
                    dim: editor.chosen.length < 2
                    text: editor.chosen.length < 2 ? "Pick at least two" : "Save"
                    KeyNavigation.right: cancelButton
                    Keys.onUpPressed: list.forceActiveFocus()
                    onClicked: editor.save()
                }
                PillButton {
                    id: cancelButton
                    u: editor.u
                    text: "Cancel"
                    KeyNavigation.left: saveButton
                    Keys.onUpPressed: list.forceActiveFocus()
                    onClicked: editor.close()
                }
            }
        }
    }
}
