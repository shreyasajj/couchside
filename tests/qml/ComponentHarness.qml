import QtQuick
import "../../src/couchside/ui/qml"

// One screen or control at TV size, with the overlays a screen opens (the action sheet,
// the group editor). `load(name, props)` makes it; what it signals lands in `events`.
Item {
    id: root
    width: 1920; height: 1080
    property Item page: null
    property var events: []
    function note(e) { var a = events.slice(); a.push(e); events = a }

    // takes focus back when a sheet opened from something that has gone away closes
    Item { id: fallback; objectName: "fallback"; focus: true }

    function load(name, props) {
        if (page) { page.destroy(); page = null }
        var c = Qt.createComponent("../../src/couchside/ui/qml/" + name + ".qml")
        if (c.status !== Component.Ready) { console.error("load failed: " + c.errorString()); return null }
        var p = props || {}
        p.width = root.width
        p.height = root.height
        page = c.createObject(stage, p)
        if (!page) return null
        if ("sheet" in page) page.sheet = sheet
        if ("groupEditor" in page) page.groupEditor = editor
        for (const s of ["done", "openGuests", "openLogs", "openPage", "openVolume", "typed",
                         "activated", "clicked", "closed", "focusLost"]) {
            if (page[s] && page[s].connect)
                page[s].connect(function(a) { root.note(a === undefined ? s : s + ":" + a) })
        }
        if (page.focusDefault) page.focusDefault()
        else page.forceActiveFocus()
        return page
    }

    Item { id: stage; objectName: "stage"; anchors.fill: parent }
    ActionSheet { id: sheet; objectName: "sheet"; onFocusLost: fallback.forceActiveFocus() }
    GroupEditor { id: editor; objectName: "groupEditor"; onFocusLost: fallback.forceActiveFocus() }
    property alias sheet: sheet
    property alias groupEditor: editor
}
