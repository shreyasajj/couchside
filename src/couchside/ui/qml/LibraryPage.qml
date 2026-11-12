import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import "typing.js" as Typing

// Search + recently played/added. Rows of cards: Up/Down between rows, Left/Right within.
Kirigami.Page {
    id: page
    property real u: 1
    property var sheet: null

    padding: 0
    globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None
    background: Rectangle { color: "#0d0b1a" }

    // The search box is focused without editing: Bigscreen's on-screen keyboard opens
    // on a focused text field and takes the arrow keys. OK starts editing; the
    // keyboard's Enter searches and moves to the results; Back stops editing.
    function focusDefault() {
        if (rows.count > 0 && page.cardFocused) rows.forceActiveFocus()
        else searchBox.forceActiveFocus()
    }
    property bool cardFocused: false
    Component.onCompleted: { app.loadRecents(); searchBox.forceActiveFocus() }
    function handleBack() {
        // Back while typing: keyboard away, straight to the results (Bigscreen's keyboard
        // swallows the first key after it hides, so landing there saves a press).
        if (field.activeFocus) { debounce.stop(); app.search(field.text); toResults(); return true }
        return false
    }
    function startEditing() { field.forceActiveFocus(); Qt.inputMethod.show() }
    // Letters from a keyboard remote: start a new search with them (or keep typing),
    // without the on-screen keyboard.
    function typeInto(text) {
        if (!field.activeFocus) field.text = ""
        field.forceActiveFocus()
        Qt.inputMethod.hide()
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
        if (rows.count > 0) { page.cardFocused = true; rows.forceActiveFocus() }
        else searchBox.forceActiveFocus()
    }

    function openCard(card, item) {
        sheet.open(card.title, [
            { id: "now", label: "Play now" },
            { id: "next", label: "Play next" },
            { id: "add", label: "Add to queue" },
        ], item, function(mode) { app.playUri(card.uri, mode) })
    }

    Timer {
        id: debounce
        interval: 500
        onTriggered: app.search(field.text)
    }

    ColumnLayout {
        anchors { fill: parent; margins: 72 * page.u; bottomMargin: 0 }
        spacing: 24 * page.u

        QQC2.Label {

            textFormat: Text.PlainText
            text: "Search"
            color: "#ffffff"
            font.pixelSize: 48 * page.u
            font.weight: Font.Bold
        }

        FocusScope {
            id: searchBox
            Layout.fillWidth: true
            implicitHeight: field.implicitHeight
            Keys.onReturnPressed: page.startEditing()
            Keys.onEnterPressed: page.startEditing()
            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Select) { page.startEditing(); event.accepted = true; return }
                var t = Typing.typed(event)
                if (t) { page.typeInto(t); event.accepted = true }
            }
            Keys.onDownPressed: page.toResults()

            QQC2.TextField {
                id: field
                anchors.fill: parent
                focus: false
                activeFocusOnTab: false
                placeholderText: searchBox.activeFocus && !field.activeFocus
                                 ? "Press OK to type" : "Songs, albums, artists, playlists, radio"
                font.pixelSize: 34 * page.u
                color: "#ffffff"
                placeholderTextColor: "#99ffffff"
                padding: 22 * page.u
                inputMethodHints: Qt.ImhNoPredictiveText
                background: Rectangle {
                    radius: 12 * page.u
                    color: field.activeFocus ? "#33ffffff" : "#22ffffff"
                    border.width: searchBox.activeFocus ? 5 * page.u : 0
                    border.color: "#4fc3f7"
                }
                onTextEdited: debounce.restart()
                onAccepted: { debounce.stop(); app.search(text); page.toResults() }
            }
        }

        QQC2.Label {

            textFormat: Text.PlainText
            Layout.fillWidth: true
            visible: text !== ""
            text: app.libraryBusy ? "Searching…"
                  : app.libraryError !== "" ? app.libraryError
                  : (rows.count === 0 && field.text.trim() !== "") ? "No results"
                  : (rows.count === 0 ? "Nothing here yet — try a search" : "")
            color: app.libraryError !== "" ? "#ffd479" : "#ffffff"
            opacity: 0.8
            font.pixelSize: 30 * page.u
        }

        ListView {
            id: rows
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 32 * page.u
            model: app.libraryRows
            keyNavigationEnabled: false
            highlightMoveDuration: 200
            preferredHighlightBegin: 0
            preferredHighlightEnd: height * 0.6
            highlightRangeMode: ListView.ApplyRange
            onModelChanged: currentIndex = 0

            Keys.onUpPressed: {
                if (currentIndex <= 0) { page.cardFocused = false; searchBox.forceActiveFocus() }
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
                spacing: 16 * page.u

                QQC2.Label {

                    textFormat: Text.PlainText
                    text: rowItem.modelData.title
                    color: "#ffffff"
                    opacity: rowItem.ListView.isCurrentItem ? 1 : 0.7
                    font.pixelSize: 34 * page.u
                    font.weight: Font.DemiBold
                }
                ListView {
                    id: cards
                    width: parent.width
                    height: 340 * page.u + 24 * page.u
                    orientation: ListView.Horizontal
                    spacing: 32 * page.u
                    clip: false
                    focus: true
                    model: rowItem.modelData.items
                    highlightRangeMode: ListView.ApplyRange
                    preferredHighlightBegin: 16 * page.u
                    preferredHighlightEnd: width - 280 * page.u
                    highlightMoveDuration: 150
                    topMargin: 12 * page.u
                    leftMargin: 12 * page.u
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
