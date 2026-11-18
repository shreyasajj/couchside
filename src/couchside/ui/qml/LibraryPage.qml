import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import "typing.js" as Typing

// Search, with recently played and recently added while the box is empty. Rows of cover
// cards, one row per kind (Tracks, Albums, …); OK on a card asks what to do with it.
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
    Component.onCompleted: { if (!bridgeManaged) app.loadRecents(); searchBox.forceActiveFocus() }
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

    // results gone while the remote was on them: back to the box
    Connections {
        target: app
        function onLibraryChanged() {
            if (list.count === 0 && list.activeFocus) { page.rowFocused = false; searchBox.forceActiveFocus() }
        }
    }
    // Opened before the server was reachable (right after starting): ask for the recents
    // once more when it is.
    property bool askedAgain: false
    Connections {
        target: app
        function onChanged() {
            if (!page.askedAgain && !page.bridgeManaged && list.count === 0 && field.text === ""
                    && app.connState === "connected") {
                page.askedAgain = true
                app.loadRecents()
            }
        }
    }

    Timer {
        id: debounce
        interval: 300  // after the last letter; the library's matches then show almost at once
        onTriggered: app.search(field.text)
    }

    ColumnLayout {
        anchors { fill: parent; topMargin: page.topInset + 44 * page.u
                  leftMargin: 72 * page.u; rightMargin: 72 * page.u }
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
                // A TextField passes Enter on to its parent after `accepted`, and the search box
                // would take it as "start typing" again: finish here and keep the key.
                Keys.onReturnPressed: (event) => { accepted(); event.accepted = true }
                Keys.onEnterPressed: (event) => { accepted(); event.accepted = true }
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

        // Rows of cards, one row per kind (Tracks, Albums, …): Up/Down change row,
        // Left/Right move along it.
        ListView {
            id: list
            objectName: "results"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 20 * page.u
            model: app.libraryRows
            keyNavigationEnabled: false
            highlightMoveDuration: 200
            preferredHighlightBegin: 0
            preferredHighlightEnd: height * 0.6
            highlightRangeMode: ListView.ApplyRange
            bottomMargin: 40 * page.u
            onModelChanged: currentIndex = 0

            Keys.onUpPressed: {
                if (currentIndex <= 0) { page.rowFocused = false; searchBox.forceActiveFocus() }
                else decrementCurrentIndex()
            }
            Keys.onDownPressed: if (currentIndex < count - 1) incrementCurrentIndex()

            // Each row is a FocusScope so focus passes row -> card list -> card.
            delegate: FocusScope {
                id: rowItem
                required property var modelData
                required property int index
                width: ListView.view.width
                height: rowColumn.implicitHeight
                Column {
                    id: rowColumn
                    width: parent.width
                    spacing: 14 * page.u

                    Text {
                        textFormat: Text.PlainText
                        text: rowItem.modelData.title
                        color: rowItem.ListView.isCurrentItem && list.activeFocus ? Theme.text : Theme.textDim
                        font.pixelSize: Theme.body * page.u
                        font.weight: Font.Bold
                        leftPadding: 16 * page.u
                    }
                    ListView {
                        id: cards
                        objectName: "cards"
                        width: parent.width
                        height: 352 * page.u + 28 * page.u
                        orientation: ListView.Horizontal
                        spacing: 32 * page.u
                        clip: false
                        focus: true
                        model: rowItem.modelData.items
                        highlightRangeMode: ListView.ApplyRange
                        preferredHighlightBegin: 16 * page.u
                        preferredHighlightEnd: width - 280 * page.u
                        highlightMoveDuration: 150
                        topMargin: 16 * page.u
                        leftMargin: 16 * page.u
                        delegate: MediaCardItem {
                            id: cardItem
                            required property var modelData
                            u: page.u
                            focus: ListView.isCurrentItem
                            title: modelData.title
                            subtitle: modelData.subtitle
                            imageUrl: modelData.imageUrl
                            kind: modelData.kind
                            onActivated: page.openCard(modelData, cardItem)
                        }
                    }
                }
            }
        }
    }
}
