import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2

// Pick the speakers in a group. open(groupId or "", memberIds, opener).
// OK toggles a speaker; Save creates or updates the group (needs two or more).
Rectangle {
    id: editor
    property real u: 1
    property string groupId: ""
    property var chosen: []
    property Item opener: null

    anchors.fill: parent
    color: "#b3000000"
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
        radius: 20 * editor.u
        color: "#1d1840"

        ColumnLayout {
            id: column
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 32 * editor.u }
            spacing: 20 * editor.u

            QQC2.Label {
                text: editor.groupId === "" ? "New group" : "Edit group"
                color: "#ffffff"
                font.pixelSize: 40 * editor.u
                font.weight: Font.Bold
            }
            QQC2.Label {
                text: "Pick two or more speakers to play in sync"
                color: "#ffffff"
                opacity: 0.75
                font.pixelSize: 28 * editor.u
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
                delegate: Rectangle {
                    id: option
                    required property var modelData
                    readonly property bool on: editor.chosen.indexOf(modelData.playerId) >= 0
                    readonly property bool lit: ListView.isCurrentItem && list.activeFocus
                    width: ListView.view.width
                    height: 84 * editor.u
                    radius: 12 * editor.u
                    color: lit ? "#ffffff" : "#26ffffff"
                    border.width: lit ? 5 * editor.u : 0
                    border.color: "#4fc3f7"
                    RowLayout {
                        anchors { fill: parent; leftMargin: 24 * editor.u; rightMargin: 24 * editor.u }
                        spacing: 20 * editor.u
                        Rectangle {
                            width: 36 * editor.u
                            height: width
                            radius: 8 * editor.u
                            color: option.on ? "#4fc3f7" : "transparent"
                            border.width: 3 * editor.u
                            border.color: option.lit ? "#000000" : "#ffffff"
                            QQC2.Label {
                                anchors.centerIn: parent
                                visible: option.on
                                text: "✓"
                                color: "#000000"
                                font.pixelSize: 28 * editor.u
                                font.weight: Font.Bold
                            }
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            text: option.modelData.name
                            color: option.lit ? "#000000" : "#ffffff"
                            font.pixelSize: 32 * editor.u
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
                EditorButton {
                    id: saveButton
                    text: editor.chosen.length < 2 ? "Pick at least two" : "Save"
                    KeyNavigation.right: cancelButton
                    Keys.onUpPressed: list.forceActiveFocus()
                    onClicked: editor.save()
                }
                EditorButton {
                    id: cancelButton
                    text: "Cancel"
                    KeyNavigation.left: saveButton
                    Keys.onUpPressed: list.forceActiveFocus()
                    onClicked: editor.close()
                }
            }
        }
    }

    component EditorButton: QQC2.Button {
        id: btn
        font.pixelSize: 32 * editor.u
        padding: 22 * editor.u
        focusPolicy: Qt.StrongFocus
        Keys.onReturnPressed: if (enabled) clicked()
        Keys.onEnterPressed: if (enabled) clicked()
        background: Rectangle {
            radius: 12 * editor.u
            color: btn.activeFocus ? "#ffffff" : "#33ffffff"
            opacity: btn.enabled ? 1 : 0.6
            border.width: btn.activeFocus ? 6 * editor.u : 0
            border.color: "#4fc3f7"
        }
        contentItem: QQC2.Label {
            text: btn.text
            font: btn.font
            color: btn.activeFocus ? "#000000" : "#ffffff"
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
