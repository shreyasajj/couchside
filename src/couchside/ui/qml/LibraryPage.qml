import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import "typing.js" as Typing

// Search, with recently played and recently added while the box is empty. One list of
// big rows under headings (Tracks, Albums, …): Up/Down move, OK asks what to do with it.
FocusScope {
    id: page
    objectName: "library"
    property real u: 1
    property var sheet: null
    property real topInset: 104 * u
    property real qrWidth: 0
    property real qrBottom: 0
    property bool bridgeManaged: false   // opened from outside: the results are already loading

    // The search box is focused without editing: Bigscreen's on-screen keyboard opens
    // on a focused text field and takes the arrow keys. OK starts editing; the
    // keyboard's Enter searches and moves to the results; Back stops editing.
    function focusDefault() {
        if (list.count > 0 && page.rowFocused) list.forceActiveFocus()
        else searchBox.forceActiveFocus()
    }
    property bool rowFocused: false
    Component.onCompleted: { rebuild(); if (!bridgeManaged) app.loadRecents(); searchBox.forceActiveFocus() }
    function handleBack() {
        // Back while typing: keyboard away, straight to the results (Bigscreen's keyboard
        // swallows the first key after it hides, so landing there saves a press).
        if (field.activeFocus) { debounce.stop(); app.search(field.text); toResults(); return true }
        return false
    }
    function setBridgeQuery(query) {
        debounce.stop()
        field.text = query
        stopEditing()
        toResults()
    }
    function startEditing() { field.forceActiveFocus(); Qt.inputMethod.show() }
    // Letters from a keyboard remote: start a new search with them (or keep typing),
    // without the on-screen keyboard.
    function typeInto(text) {
        if (!field.activeFocus) field.text = ""
        field.forceActiveFocus()
        Typing.hideKeyboard()
        field.insert(field.cursorPosition, text)
        debounce.restart()
    }
    // typing anywhere on the page (results included) goes to the search box
    Keys.onPressed: (event) => {
        var t = Typing.typed(event)
        if (t) { page.typeInto(t); event.accepted = true }
    }
    // Clearing field.focus matters: a FocusScope hands focus back to the child that
    // last had it, which would put the cursor (and the keyboard) straight back.
    function stopEditing() { field.focus = false; Qt.inputMethod.hide() }
    function toResults() {
        stopEditing()
        if (list.count > 0) { page.rowFocused = true; list.forceActiveFocus() }
        else searchBox.forceActiveFocus()
    }

    function openCard(card, item) {
        sheet.open(card.title, [
            { id: "now", label: "Play now" },
            { id: "next", label: "Play next" },
            { id: "add", label: "Add to queue" },
        ], item, function(mode) { app.playUri(card.uri, mode) })
    }

    // The groups from the controller ([{title, items}]) as one flat list with headings.
    ListModel { id: flat }
    function rebuild() {
        flat.clear()
        var groups = app.libraryRows
        for (var g = 0; g < groups.length; g++) {
            var items = groups[g].items
            for (var i = 0; i < items.length; i++)
                flat.append({ group: groups[g].title, title: items[i].title, subtitle: items[i].subtitle || "",
                              imageUrl: items[i].imageUrl || "", kind: items[i].kind || "track",
                              uri: items[i].uri || "" })
        }
        list.currentIndex = 0
        if (flat.count === 0 && list.activeFocus) { page.rowFocused = false; searchBox.forceActiveFocus() }
    }
    Connections { target: app; function onLibraryChanged() { page.rebuild() } }

    Timer {
        id: debounce
        interval: 300  // after the last letter; the library's matches then show almost at once
        onTriggered: app.search(field.text)
    }

    ColumnLayout {
        anchors { fill: parent; topMargin: page.topInset + 44 * page.u
                  leftMargin: 150 * page.u; rightMargin: Math.max(150 * page.u, page.qrWidth) }
        spacing: 20 * page.u

        FocusScope {
            id: searchBox
            objectName: "searchBox"
            Layout.fillWidth: true
            implicitHeight: 104 * page.u
            Keys.onReturnPressed: page.startEditing()
            Keys.onEnterPressed: page.startEditing()
            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Select) { page.startEditing(); event.accepted = true; return }
                var t = Typing.typed(event)
                if (t) { page.typeInto(t); event.accepted = true }
            }
            Keys.onDownPressed: page.toResults()

            Rectangle {
                anchors.fill: parent
                radius: 24 * page.u
                color: field.activeFocus ? Theme.surfaceHigh : Theme.surface
                border.width: 2 * page.u
                border.color: field.activeFocus ? Theme.a2 : "#1fffffff"   // pink while typing
            }
            FocusRing { anchors.fill: parent; u: page.u; radius: 24 * page.u; shown: searchBox.activeFocus && !field.activeFocus }
            Icon {
                id: glass
                anchors { left: parent.left; leftMargin: 34 * page.u; verticalCenter: parent.verticalCenter }
                name: "search"
                size: 44 * page.u
                color: Theme.textDim
            }
            QQC2.TextField {
                id: field
                anchors { left: glass.right; right: parent.right; verticalCenter: parent.verticalCenter
                          leftMargin: 20 * page.u; rightMargin: 28 * page.u }
                focus: false
                activeFocusOnTab: false
                placeholderText: searchBox.activeFocus && !field.activeFocus
                                 ? "Press OK to type" : "Search songs, artists, albums"
                font.pixelSize: 44 * page.u
                font.weight: Font.DemiBold
                color: Theme.text
                placeholderTextColor: "#52ffffff"
                inputMethodHints: Qt.ImhNoPredictiveText
                background: Item {}
                onTextEdited: debounce.restart()
                // typing on a real keyboard: keep Bigscreen's on-screen keyboard out of the way
                Keys.onPressed: (event) => { if (Typing.typed(event)) Typing.hideKeyboard() }
                onAccepted: { debounce.stop(); app.search(text); page.toResults() }
            }
        }

        Text {
            textFormat: Text.PlainText
            Layout.fillWidth: true
            visible: text !== ""
            text: app.libraryBusy ? "Searching…"
                  : app.libraryError !== "" ? app.libraryError
                  : (list.count === 0 && field.text.trim() !== "") ? "No results"
                  : (list.count === 0 ? "Nothing here yet — try a search" : "")
            color: app.libraryError !== "" ? Theme.warn : Theme.textDim
            font.pixelSize: Theme.label * page.u
        }

        ListView {
            id: list
            objectName: "results"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 14 * page.u
            model: flat
            keyNavigationEnabled: false
            highlightMoveDuration: 150
            preferredHighlightBegin: height * 0.2
            preferredHighlightEnd: height * 0.75
            highlightRangeMode: ListView.ApplyRange
            // room for the focused row's ring and growth inside the clipped list
            leftMargin: 10 * page.u
            rightMargin: 10 * page.u
            bottomMargin: 40 * page.u

            Keys.onUpPressed: {
                if (currentIndex <= 0) { page.rowFocused = false; searchBox.forceActiveFocus() }
                else decrementCurrentIndex()
            }
            Keys.onDownPressed: if (currentIndex < count - 1) incrementCurrentIndex()

            section.property: "group"
            section.delegate: Text {
                required property string section
                textFormat: Text.PlainText
                text: section
                color: Theme.textDim
                font.pixelSize: Theme.label * page.u
                font.weight: Font.Bold
                topPadding: 14 * page.u
                bottomPadding: 12 * page.u
                leftPadding: 6 * page.u
            }

            delegate: ListRow {
                id: rowItem
                required property var model
                width: ListView.view.width - 20 * page.u
                u: page.u
                focus: ListView.isCurrentItem
                thumb: 104 * page.u
                titleSize: Theme.rowTitle
                title: model.title
                subtitle: model.subtitle
                imageUrl: model.imageUrl
                roundArt: model.kind === "artist"
                iconName: ({ track: "music", album: "album", artist: "person",
                             playlist: "queue", radio: "radio" })[model.kind] || "music"
                hint: "PLAY"
                onActivated: page.openCard({ title: model.title, uri: model.uri }, rowItem)
            }
        }
    }
}
