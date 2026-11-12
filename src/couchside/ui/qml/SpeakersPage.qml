import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Every speaker and group: control it, sync it, move the queue, manage groups.
Kirigami.Page {
    id: page
    property real u: 1
    property var sheet: null
    property var groupEditor: null

    padding: 0
    globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None
    background: PageBackground { tint: app.backgroundColour }

    function focusDefault() { list.forceActiveFocus() }
    Component.onCompleted: { rows = app.speakerRows; list.forceActiveFocus() }

    readonly property var controlled: {
        var rows = app.speakerRows
        for (var i = 0; i < rows.length; i++) if (rows[i].controlled) return rows[i]
        return null
    }
    function nameOf(id) {
        var rows = app.speakerRows
        for (var i = 0; i < rows.length; i++) if (rows[i].playerId === id) return rows[i].name
        return id
    }

    // Own copy of the rows, swapped together with the focus (see QueuePage).
    property var rows: []
    function takeRows() {
        var keep = (list.currentIndex >= 0 && list.currentIndex < rows.length) ? rows[list.currentIndex].playerId : ""
        var oldIndex = Math.max(0, list.currentIndex)
        rows = app.speakerRows
        var idx = -1
        for (var i = 0; i < rows.length; i++) if (rows[i].playerId === keep) { idx = i; break }
        if (idx < 0) idx = Math.min(oldIndex, rows.length - 1)
        list.currentIndex = Math.max(0, idx)
    }
    Connections { target: app; function onSpeakersChanged() { page.takeRows() } }

    function openRow(row, item) {
        var acts = []
        if (row.available && !row.controlled) acts.push({ id: "control", label: "Control this speaker" })
        if (row.available && !row.controlled && page.controlled)
            acts.push({ id: "transfer", label: "Move the queue here" })
        if (row.canSync && row.syncedTo === "" && page.controlled)
            acts.push({ id: "sync", label: "Sync with " + page.controlled.name })
        if (row.syncedTo !== "") acts.push({ id: "unsync", label: "Stop syncing" })
        if (row.isGroup) {
            acts.push({ id: "edit", label: "Edit members" })
            acts.push({ id: "delete_group", label: "Delete group" })
        }
        if (acts.length === 0) acts.push({ id: "close", label: row.available ? "Close" : "Offline — close" })
        sheet.open(row.name, acts, item, function(action) {
            if (action === "control") app.controlSpeaker(row.playerId)
            else if (action === "edit") groupEditor.open(row.playerId, row.members, item)
            else if (action !== "close") app.speakerAction(row.playerId, action)
        })
    }

    ColumnLayout {
        anchors { fill: parent; margins: 72 * page.u }
        spacing: 24 * page.u

        QQC2.Label {

            textFormat: Text.PlainText
            text: "Speakers"
            color: "#ffffff"
            font.pixelSize: 48 * page.u
            font.weight: Font.Bold
        }

        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8 * page.u
            model: page.rows
            keyNavigationEnabled: true
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: height * 0.2
            preferredHighlightEnd: height * 0.8
            Keys.onDownPressed: (event) => {
                if (currentIndex >= count - 1) newGroup.forceActiveFocus()
                else incrementCurrentIndex()
            }
            delegate: ListRow {
                id: rowItem
                required property var modelData
                width: ListView.view.width
                u: page.u
                focus: ListView.isCurrentItem
                iconName: modelData.isGroup ? "group" : "speaker"
                title: modelData.name
                subtitle: !modelData.available ? "Offline"
                          : modelData.playing !== "" ? modelData.playing
                          : modelData.isGroup ? modelData.members.map(page.nameOf).join(", ") : ""
                dimmed: !modelData.available
                marked: modelData.controlled
                badges: {
                    var b = []
                    if (modelData.local) b.push("This TV")
                    if (modelData.controlled) b.push("Controlling")
                    if (modelData.syncedTo !== "") b.push("Synced with " + page.nameOf(modelData.syncedTo))
                    return b
                }
                onActivated: page.openRow(modelData, rowItem)
            }
        }

        ListRow {  // looks like one more row at the end of the list
            id: newGroup
            Layout.fillWidth: true
            u: page.u
            iconName: "plus"
            title: "New group"
            subtitle: "Pick speakers to play in sync"
            Keys.onUpPressed: list.forceActiveFocus()
            onActivated: groupEditor.open("", [], newGroup)
        }
    }
}
