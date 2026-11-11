import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// What is still to play on the controlled speaker. OK on a row: play / move / remove.
Kirigami.Page {
    id: page
    property real u: 1
    property var sheet: null

    padding: 0
    globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None
    background: Rectangle { color: "#0d0b1a" }

    function focusDefault() { list.forceActiveFocus() }
    Component.onCompleted: { rows = app.queueRows; app.queueVisible = true; list.forceActiveFocus() }
    Component.onDestruction: app.queueVisible = false

    // The page owns its copy of the rows: a ListView resets to row 0 the moment its
    // model changes, so swap the rows and put focus back on the same song in one step.
    property var rows: []
    function takeRows() {
        var keep = (list.currentIndex >= 0 && list.currentIndex < rows.length) ? rows[list.currentIndex].itemId : ""
        var oldIndex = Math.max(0, list.currentIndex)
        rows = app.queueRows
        var idx = -1
        for (var i = 0; i < rows.length; i++) if (rows[i].itemId === keep) { idx = i; break }
        if (idx < 0) idx = Math.min(oldIndex, rows.length - 1)
        list.currentIndex = Math.max(0, idx)
    }
    Connections { target: app; function onQueueChanged() { page.takeRows() } }

    function openRow(row, item, index) {
        var acts = []
        if (!row.current) {
            acts.push({ id: "play", label: "Play this now" })
            acts.push({ id: "next", label: "Play next" })
        }
        if (index > (row.current ? 0 : 1)) acts.push({ id: "up", label: "Move up" })
        if (index < list.count - 1) acts.push({ id: "down", label: "Move down" })
        acts.push({ id: "remove", label: "Remove from queue" })
        sheet.open(row.title, acts, item, function(action) { app.queueAction(row.itemId, action) })
    }

    ColumnLayout {
        anchors { fill: parent; margins: 72 * page.u; bottomMargin: 0 }
        spacing: 24 * page.u

        QQC2.Label {
            text: "Queue"
            color: "#ffffff"
            font.pixelSize: 48 * page.u
            font.weight: Font.Bold
        }
        QQC2.Label {
            visible: list.count === 0
            text: "Nothing queued — add songs from Search"
            color: "#ffffff"
            opacity: 0.8
            font.pixelSize: 30 * page.u
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
            highlightMoveDuration: 150
            delegate: ListRow {
                id: rowItem
                required property var modelData
                required property int index
                width: ListView.view.width
                u: page.u
                focus: ListView.isCurrentItem
                imageUrl: modelData.imageUrl
                title: modelData.title
                subtitle: modelData.subtitle
                marked: modelData.current
                badges: modelData.current ? ["Now playing"] : []
                trailing: modelData.duration > 0 ? app.formatTime(modelData.duration) : ""
                onActivated: page.openRow(modelData, rowItem, index)
            }
        }
    }
}
