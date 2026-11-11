import QtQuick

// Test harness: an ActionSheet plus an opener that the test can destroy.
Item {
    id: root
    width: 800; height: 600
    property int lostCount: 0
    property var ran: []
    property Item opener: null

    Component { id: openerComponent; Rectangle { width: 10; height: 10; focus: true } }
    function makeOpener() { opener = openerComponent.createObject(root); opener.forceActiveFocus(); return opener }
    function openSheet() {
        sheet.open("Title", [{ id: "first", label: "First" }, { id: "second", label: "Second" }],
                   opener, function(id) { var r = ran.slice(); r.push(id); ran = r })
    }

    ActionSheet { id: sheet; objectName: "sheet"; onFocusLost: root.lostCount += 1 }
}
