import QtQuick
import QtQuick.Layouts

// What is still to play on the controlled speaker. OK on a row: play / move / remove.
// (The shell keeps the queue loaded while this screen or Now Playing shows.)
FocusScope {
    id: page
    property real u: 1
    property var sheet: null
    property real topInset: 104 * u
    property real qrWidth: 0
    property real qrBottom: 0

    function focusDefault() { list.forceActiveFocus() }
    Component.onCompleted: { rows = app.queueRows; list.forceActiveFocus() }

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
        anchors { fill: parent; topMargin: page.topInset + 36 * page.u
                  leftMargin: 150 * page.u; rightMargin: Math.max(150 * page.u, page.qrWidth) }
        spacing: 16 * page.u

        ScreenTitle {
            Layout.fillWidth: true
            u: page.u
            title: list.count > 1 ? "Queue · " + list.count + " songs" : "Queue"
            note: list.count === 0 ? "Nothing queued — add songs from Search" : ""
        }

        ListView {
            id: list
            objectName: "queueList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 12 * page.u
            model: page.rows
            keyNavigationEnabled: true
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: height * 0.2
            preferredHighlightEnd: height * 0.8
            highlightMoveDuration: 150
            leftMargin: 10 * page.u
            rightMargin: 10 * page.u
            bottomMargin: 40 * page.u
            // "Now playing" above the playing song, "Up next" above the first one after it
            delegate: FocusScope {
                id: slot
                required property var modelData
                required property int index
                readonly property string caption: modelData.current ? "Now playing"
                    : (index === 0 || page.rows[index - 1].current) ? "Up next" : ""
                width: ListView.view.width - 20 * page.u
                height: rowItem.height + (caption !== "" ? captionText.height + 22 * page.u : 0)
                focus: ListView.isCurrentItem
                z: ListView.isCurrentItem ? 1 : 0
                Text {
                    id: captionText
                    textFormat: Text.PlainText
                    visible: slot.caption !== ""
                    x: 6 * page.u
                    y: 8 * page.u
                    text: slot.caption
                    color: Theme.textDim
                    font.pixelSize: Theme.label * page.u
                    font.weight: Font.Bold
                }
                ListRow {
                    id: rowItem
                    readonly property var modelData: slot.modelData
                    readonly property int index: slot.index
                    anchors.bottom: parent.bottom
                    width: parent.width
                    u: page.u
                    focus: true
                    imageUrl: modelData.imageUrl
                    title: modelData.title
                    subtitle: modelData.subtitle
                    marked: modelData.current
                    badges: modelData.addedBy ? ["Added by " + modelData.addedBy] : []
                    trailing: modelData.duration > 0 ? app.formatTime(modelData.duration) : ""
                    onActivated: page.openRow(modelData, rowItem, index)
                }
            }
        }
    }
}
