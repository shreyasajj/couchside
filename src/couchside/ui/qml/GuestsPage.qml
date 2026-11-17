import QtQuick
import QtQuick.Layouts

// Guest mode's people: turn guest mode off, show a one-time admin code, and for each guest make or unmake an
// admin, give their skips and boosts back, or remove them from the party.
FocusScope {
    id: page
    property real u: 1
    property var sheet: null
    property real topInset: 104 * u
    property real qrWidth: 0
    property real qrBottom: 0

    function focusDefault() { (rows.length > 0 ? list : modeButton).forceActiveFocus() }
    Component.onCompleted: { rows = app.guestRows; modeButton.forceActiveFocus() }

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
        if (hadFocus && rows.length === 0) modeButton.forceActiveFocus()
    }
    Connections { target: app; function onGuestChanged() { page.takeRows() } }

    function openRow(row, item) {
        var acts = [row.admin ? { id: "revoke", label: "Remove admin" } : { id: "promote", label: "Make admin" }]
        if (!row.admin) acts.push({ id: "reset", label: "Give back skips and boosts" })
        acts.push({ id: "remove", label: "Remove from the party" })
        sheet.open(row.name, acts, item, function(action) { app.guestAction(row.id, action) })
    }

    ColumnLayout {
        anchors { fill: parent; topMargin: page.topInset + 36 * page.u; bottomMargin: 40 * page.u
                  leftMargin: 150 * page.u; rightMargin: Math.max(150 * page.u, page.qrWidth) }
        spacing: 12 * page.u

        ScreenTitle {
            Layout.fillWidth: true
            Layout.bottomMargin: 8 * page.u
            u: page.u
            title: "Guests and admins"
            note: "Admins can skip without limits, change the queue, volume and speakers, and reset or remove guests."
        }

        ListRow {
            id: modeButton
            objectName: "guestModeButton"
            Layout.fillWidth: true
            Layout.leftMargin: 10 * page.u
            Layout.rightMargin: 10 * page.u
            u: page.u
            iconName: "qr"
            title: app.guestMode ? "Guest mode is on" : "Guest mode is off"
            subtitle: app.guestMode ? "OK turns it off — the QR code stops working and everyone is signed out"
                                    : "OK turns it on and shows a QR code for guests to scan"
            trailing: app.guestMode ? (app.guestCount === 1 ? "1 guest" : app.guestCount + " guests") : ""
            Keys.onDownPressed: codeButton.forceActiveFocus()
            onActivated: app.toggleGuestMode()
        }

        ListRow {
            id: codeButton
            objectName: "adminCodeButton"
            Layout.fillWidth: true
            Layout.leftMargin: 10 * page.u
            Layout.rightMargin: 10 * page.u
            dimmed: !app.guestMode
            Keys.onUpPressed: modeButton.forceActiveFocus()
            u: page.u
            iconName: "star"
            title: "Show an admin code"
            subtitle: "A one-time code for a guest to type on their phone"
            Keys.onDownPressed: if (page.rows.length > 0) list.forceActiveFocus()
            onActivated: app.showAdminCode()
        }

        Text {
            textFormat: Text.PlainText
            Layout.fillWidth: true
            Layout.leftMargin: 16 * page.u
            Layout.topMargin: 8 * page.u
            visible: page.rows.length === 0
            text: app.guestMode ? "No guests yet — they join by scanning the QR code in the corner."
                                : "Turn guest mode on to let guests add songs from their phones."
            color: Theme.textDim
            font.pixelSize: Theme.label * page.u
            wrapMode: Text.WordWrap
        }

        ListView {
            id: list
            objectName: "guestList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 12 * page.u
            leftMargin: 10 * page.u
            rightMargin: 10 * page.u
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
                width: ListView.view.width - 20 * page.u
                u: page.u
                focus: ListView.isCurrentItem
                iconName: modelData.admin ? "star" : "person"
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
