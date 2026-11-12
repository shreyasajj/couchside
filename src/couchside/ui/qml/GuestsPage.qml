import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Guest mode's people: show a one-time admin code, and for each guest make or unmake an
// admin, give their skips and boosts back, or remove them from the party.
Kirigami.Page {
    id: page
    property real u: 1
    property var sheet: null

    padding: 0
    globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None
    background: Rectangle { color: "#0d0b1a" }

    function focusDefault() { (rows.length > 0 ? list : codeButton).forceActiveFocus() }
    Component.onCompleted: { rows = app.guestRows; codeButton.forceActiveFocus() }

    // Own copy of the rows, swapped together with the focus (see QueuePage).
    property var rows: []
    function takeRows() {
        var keep = (list.currentIndex >= 0 && list.currentIndex < rows.length) ? rows[list.currentIndex].id : ""
        var oldIndex = Math.max(0, list.currentIndex)
        var hadFocus = list.activeFocus
        rows = app.guestRows
        var idx = -1
        for (var i = 0; i < rows.length; i++) if (rows[i].id === keep) { idx = i; break }
        if (idx < 0) idx = Math.min(oldIndex, rows.length - 1)
        list.currentIndex = Math.max(0, idx)
        if (hadFocus && rows.length === 0) codeButton.forceActiveFocus()
    }
    Connections { target: app; function onGuestChanged() { page.takeRows() } }

    function openRow(row, item) {
        var acts = [row.admin ? { id: "revoke", label: "Remove admin" } : { id: "promote", label: "Make admin" }]
        if (!row.admin) acts.push({ id: "reset", label: "Give back skips and boosts" })
        acts.push({ id: "remove", label: "Remove from the party" })
        sheet.open(row.name, acts, item, function(action) { app.guestAction(row.id, action) })
    }

    ColumnLayout {
        anchors { fill: parent; margins: 72 * page.u }
        spacing: 24 * page.u

        QQC2.Label {
            textFormat: Text.PlainText
            text: "Guests and admins"
            color: "#ffffff"
            font.pixelSize: 48 * page.u
            font.weight: Font.Bold
        }
        QQC2.Label {
            textFormat: Text.PlainText
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "Admins can skip without limits, change the queue, volume and speakers, and reset or remove guests."
            color: "#ffffff"
            opacity: 0.75
            font.pixelSize: 28 * page.u
        }

        QQC2.Button {
            id: codeButton
            objectName: "adminCodeButton"
            text: "Show an admin code"
            font.pixelSize: 32 * page.u
            padding: 22 * page.u
            Keys.onDownPressed: if (page.rows.length > 0) list.forceActiveFocus()
            Keys.onReturnPressed: clicked()
            Keys.onEnterPressed: clicked()
            onClicked: app.showAdminCode()
            background: Rectangle {
                radius: 12 * page.u
                color: codeButton.activeFocus ? "#ffffff" : "#33ffffff"
                border.width: codeButton.activeFocus ? 6 * page.u : 0
                border.color: "#4fc3f7"
            }
            contentItem: QQC2.Label {
                textFormat: Text.PlainText
                text: codeButton.text
                font: codeButton.font
                color: codeButton.activeFocus ? "#000000" : "#ffffff"
                horizontalAlignment: Text.AlignHCenter
            }
        }

        QQC2.Label {
            textFormat: Text.PlainText
            visible: page.rows.length === 0
            text: "No guests yet — they join by scanning the QR code on Now Playing."
            color: "#ffffff"
            opacity: 0.6
            font.pixelSize: 30 * page.u
        }

        ListView {
            id: list
            objectName: "guestList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8 * page.u
            model: page.rows
            keyNavigationEnabled: true
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: height * 0.2
            preferredHighlightEnd: height * 0.8
            Keys.onUpPressed: (event) => {
                if (currentIndex <= 0) codeButton.forceActiveFocus()
                else decrementCurrentIndex()
            }
            delegate: ListRow {
                id: rowItem
                required property var modelData
                width: ListView.view.width
                u: page.u
                focus: ListView.isCurrentItem
                iconName: modelData.admin ? "user-admin" : "user"
                title: modelData.name
                subtitle: modelData.admin ? "No limits"
                          : "Skips left " + modelData.skipsLeft + " · Boosts left " + modelData.boostsLeft
                marked: modelData.admin
                badges: modelData.admin ? ["Admin"] : []
                onActivated: page.openRow(modelData, rowItem)
            }
        }
    }
}
