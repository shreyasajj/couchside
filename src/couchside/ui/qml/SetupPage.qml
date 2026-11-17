import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import "typing.js" as Typing

// Settings in two panes: the sections on the left, the chosen section's rows on the right.
// Left pane: Up/Down pick a section (the right pane follows), Right or OK goes into it.
// Right pane: Up/Down move between rows (the pane scrolls to follow), OK changes a row,
// Left goes back to the sections. Up from the first row or section reaches the top bar.
// Back leaves Settings from anywhere. Text fields only start editing on OK, because
// Bigscreen's on-screen keyboard takes the arrow keys while a field is being edited;
// the keyboard's Enter or Back stops editing.
FocusScope {
    id: page
    property real u: 1
    property var sheet: null
    property real topInset: 104 * u
    property real qrWidth: 0
    property real qrBottom: 0
    property Item returnTo: null
    signal done()
    signal openGuests()
    signal openLogs()

    function focusDefault() {
        if (returnTo && returnTo.visible) { returnTo.forceActiveFocus(); returnTo = null; return }
        if (!app.hasToken) { category = 0; tokenField.forceActiveFocus() }  // first run: straight to the token
        else toCategories()
    }

    readonly property var categories: ["Music Assistant", "Guest mode", "This speaker", "Visualizer", "Lyrics", "Look", "Updates"]
    property int category: 0
    onCategoryChanged: flick.contentY = 0
    function toCategories() {
        var item = cats.itemAt(category)
        if (item) item.forceActiveFocus()
    }
    function inside(item, container) {
        for (var p = item; p; p = p.parent) if (p === container) return true
        return false
    }
    function firstFocusable(item) {
        for (var i = 0; i < item.children.length; i++) {
            var c = item.children[i]
            if (!c.visible) continue
            if (c.activeFocusOnTab) return c
            var deeper = firstFocusable(c)
            if (deeper) return deeper
        }
        return null
    }
    function enterPane() {
        var first = firstFocusable(column)
        if (first) first.forceActiveFocus()
    }
    Component.onCompleted: {
        urlField.text = app.serverUrl
        libreField.text = app.libretranslateUrl
        captionField.text = app.qrCaption
        publicUrlField.text = app.guestPublicUrl
        playerNameField.text = app.playerName
        app.loadAudioDevices()
        focusDefault()
    }
    // Back while a field is being edited: stop editing and keep what was typed (the same as
    // the keyboard's Enter, which is awkward to reach on Bigscreen's keyboard); stay on the page.
    function handleBack() {
        for (const f of [urlField, tokenField, deeplField, libreField, captionField, publicUrlField, playerNameField])
            if (f.editing) { f.stopEditing(); f.accepted(); return true }
        return false
    }
    // Up/Down: next focusable row in that direction (skips hidden rows, no wrap-around).
    // Returns false when there is no such row (Up from the first row then goes to the top bar).
    function move(from, forward) {
        var next = from.nextItemInFocusChain(forward)
        if (!next || !inside(next, column)) return false  // stay in the right pane
        var a = from.mapToItem(column, 0, 0).y, b = next.mapToItem(column, 0, 0).y
        if (forward ? b > a : b < a) { next.forceActiveFocus(); return true }
        return false
    }
    // keep the focused row on screen
    function follow(item) {
        if (!item) return
        var p = item.mapToItem(column, 0, 0)
        if (p.x < 0 || p.y < 0 || p.y > column.height) return  // not inside this page
        var y = p.y + column.y
        var margin = 120 * page.u
        if (y - margin < flick.contentY) flick.contentY = Math.max(0, y - margin)
        else if (y + item.height + margin > flick.contentY + flick.height)
            flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height,
                                                  y + item.height + margin - flick.height))
    }
    Connections {
        target: page.Window.window
        function onActiveFocusItemChanged() { page.follow(page.Window.window.activeFocusItem) }
    }

    // A text field that edits only on OK (see the comment at the top).
    component TvField: FocusScope {
        id: tv
        property alias text: input.text
        property alias placeholderText: input.placeholderText
        property alias echoMode: input.echoMode
        property alias inputMethodHints: input.inputMethodHints
        readonly property bool editing: input.activeFocus
        signal accepted()
        Layout.fillWidth: true
        implicitHeight: input.implicitHeight
        activeFocusOnTab: true
        function startEditing() { input.forceActiveFocus(); Qt.inputMethod.show() }
        function stopEditing() { input.focus = false; Qt.inputMethod.hide(); tv.forceActiveFocus() }
        Keys.onReturnPressed: startEditing()
        Keys.onEnterPressed: startEditing()
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Select) { startEditing(); event.accepted = true; return }
            var t = Typing.typed(event)  // a keyboard remote: type straight in, no on-screen keyboard
            if (t) {
                input.forceActiveFocus()
                Typing.hideKeyboard()
                input.insert(input.text.length, t)
                event.accepted = true
            }
        }
        Keys.onUpPressed: (event) => { if (!page.move(tv, false)) event.accepted = false }
        Keys.onDownPressed: page.move(tv, true)
        Keys.onLeftPressed: (event) => { if (tv.editing) event.accepted = false; else page.toCategories() }
        QQC2.TextField {
            id: input
            anchors.fill: parent
            focus: false
            // typing on a real keyboard: keep Bigscreen's on-screen keyboard out of the way
            Keys.onPressed: (event) => { if (Typing.typed(event)) Typing.hideKeyboard() }
            activeFocusOnTab: false
            font.pixelSize: 32 * page.u
            color: Theme.text
            placeholderTextColor: "#66ffffff"
            padding: 20 * page.u
            leftPadding: 28 * page.u
            onAccepted: { tv.stopEditing(); tv.accepted() }
            background: Item {
                Rectangle {
                    anchors.fill: parent
                    radius: 18 * page.u
                    color: input.activeFocus ? Theme.surfaceHigh : Theme.surface
                    border.width: 2 * page.u
                    border.color: input.activeFocus ? Theme.a2 : "#1fffffff"   // pink while typing
                }
                FocusRing { anchors.fill: parent; u: page.u; radius: 18 * page.u; shown: tv.activeFocus && !input.activeFocus }
            }
        }
    }

    // A row that toggles, cycles or opens a setting with OK. `adjust` rows also take
    // Left/Right (emitting adjusted(-1 or 1)); Left on the others returns to the sections.
    component SettingRow: FocusScope {
        id: row
        property string label: ""
        property string value: ""
        property string hint: ""
        property bool adjust: false
        signal activated()
        signal adjusted(int direction)
        Layout.fillWidth: true
        implicitHeight: (hint !== "" ? 128 : 96) * page.u
        activeFocusOnTab: true
        Keys.onLeftPressed: if (adjust) adjusted(-1); else page.toCategories()
        Keys.onRightPressed: (event) => { if (adjust) adjusted(1); else event.accepted = false }
        Keys.onReturnPressed: activated()
        Keys.onEnterPressed: activated()
        Keys.onPressed: (event) => { if (event.key === Qt.Key_Select) { activated(); event.accepted = true } }
        Keys.onUpPressed: (event) => { if (!page.move(row, false)) event.accepted = false }
        Keys.onDownPressed: page.move(row, true)
        Rectangle {
            anchors.fill: parent
            radius: 22 * page.u
            color: Theme.surface
            border.width: 2 * page.u
            border.color: row.activeFocus ? Theme.a1 : "#0fffffff"
            gradient: row.activeFocus ? rowFocusFill : null
        }
        ColumnLayout {
            anchors { fill: parent; leftMargin: 28 * page.u; rightMargin: 28 * page.u }
            spacing: 2 * page.u
            RowLayout {
                Layout.fillWidth: true
                spacing: 20 * page.u
                Text {
                    textFormat: Text.PlainText
                    Layout.fillWidth: true
                    text: row.label
                    color: Theme.text
                    font.pixelSize: Theme.body * page.u
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    textFormat: Text.PlainText
                    Layout.maximumWidth: row.width * 0.55
                    text: (row.adjust && row.activeFocus ? "‹  " : "") + row.value + (row.adjust && row.activeFocus ? "  ›" : "")
                    color: Theme.a1
                    font.pixelSize: Theme.body * page.u
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                }
            }
            Text {
                textFormat: Text.PlainText
                Layout.fillWidth: true
                visible: row.hint !== ""
                text: row.hint
                color: Theme.textDim
                font.pixelSize: Theme.label * page.u
                elide: Text.ElideRight
            }
        }
        MouseArea { anchors.fill: parent; onClicked: { row.forceActiveFocus(); row.activated() } }
    }
    Gradient {
        id: rowFocusFill
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: Theme.tint(Theme.a1, 0.32) }
        GradientStop { position: 1; color: Theme.tint(Theme.a2, 0.2) }
    }
    function pick(title, choices, from, apply) {
        sheet.open(title, choices.map(function(c) {
            return { id: c.id, label: c.label, section: c.section || "", checked: c.current, a1: c.a1, a2: c.a2 }
        }), from, apply)
    }

    component Heading: Text {
        textFormat: Text.PlainText
        Layout.bottomMargin: 8 * page.u
        color: Theme.text
        font.pixelSize: Theme.title * page.u
        font.weight: Font.ExtraBold
    }
    component Note: Text {
        textFormat: Text.PlainText
        Layout.fillWidth: true
        color: Theme.textDim
        font.pixelSize: Theme.label * page.u
        wrapMode: Text.WordWrap
    }

    // --- left pane: the sections ---------------------------------------------------
    Column {
        id: side
        anchors { left: parent.left; top: parent.top; leftMargin: Theme.margin * page.u; topMargin: page.topInset + 28 * page.u }
        width: 420 * page.u
        spacing: 8 * page.u

        Text {
            textFormat: Text.PlainText
            text: "Settings"
            color: Theme.text
            font.pixelSize: Theme.title * page.u
            font.weight: Font.ExtraBold
            leftPadding: 24 * page.u
            bottomPadding: 20 * page.u
        }
        Repeater {
            id: cats
            model: page.categories
            delegate: FocusScope {
                id: cat
                required property int index
                required property string modelData
                readonly property bool chosen: page.category === index
                width: side.width
                height: 84 * page.u
                activeFocusOnTab: true
                Rectangle {
                    anchors.fill: parent
                    radius: 20 * page.u
                    color: cat.activeFocus ? Theme.tint(Theme.a1, 0.22) : (cat.chosen ? Theme.surfaceHigh : "transparent")
                    border.width: cat.activeFocus ? 2 * page.u : 0
                    border.color: Theme.a1
                }
                Rectangle {   // the chosen section's mark
                    visible: cat.chosen
                    anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 8 * page.u }
                    width: 6 * page.u; height: parent.height * 0.5; radius: width / 2
                    color: Theme.a1
                }
                onActiveFocusChanged: if (activeFocus) page.category = index
                Keys.onUpPressed: (event) => { if (index > 0) cats.itemAt(index - 1).forceActiveFocus(); else event.accepted = false }
                Keys.onDownPressed: if (index < cats.count - 1) cats.itemAt(index + 1).forceActiveFocus()
                Keys.onRightPressed: page.enterPane()
                Keys.onReturnPressed: page.enterPane()
                Keys.onEnterPressed: page.enterPane()
                Keys.onPressed: (event) => { if (event.key === Qt.Key_Select) { page.enterPane(); event.accepted = true } }
                Text {
                    textFormat: Text.PlainText
                    anchors.verticalCenter: parent.verticalCenter
                    x: 28 * page.u
                    text: cat.modelData
                    color: cat.chosen || cat.activeFocus ? Theme.text : Theme.textDim
                    font.pixelSize: Theme.body * page.u
                    font.weight: cat.chosen ? Font.Bold : Font.Medium
                }
                MouseArea { anchors.fill: parent; onClicked: cat.forceActiveFocus() }
            }
        }
    }

    // --- right pane: the chosen section's rows --------------------------------------
    Flickable {
        id: flick
        anchors { left: side.right; right: parent.right; top: parent.top; bottom: parent.bottom
                  topMargin: page.topInset; leftMargin: 56 * page.u
                  rightMargin: Math.max(Theme.margin * page.u, page.qrWidth) }
        contentHeight: column.implicitHeight + 120 * page.u
        interactive: false
        clip: true
        Behavior on contentY { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        ColumnLayout {
            id: column
            y: 28 * page.u
            x: 8 * page.u
            width: flick.width - 16 * page.u
            spacing: 0

            ColumnLayout {
                visible: page.category === 0
                Layout.fillWidth: true
                spacing: 20 * page.u
                Heading { text: "Music Assistant" }
                Note {
                    visible: app.connState === "auth_failed" && app.hasToken
                    text: "Music Assistant did not accept the token. Create a new one and enter it below."
                    color: Theme.warn
                }
                Note { text: "Server address" }
                TvField {
                    id: urlField
                    placeholderText: "Leave empty to find it automatically"
                    inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoAutoUppercase
                }
                Note { text: "Access token — in the Music Assistant web app: Settings → your profile → Long-lived access tokens" }
                TvField {
                    id: tokenField
                    placeholderText: app.hasToken ? "Saved — leave empty to keep it" : "Press OK, then paste or type the token"
                    echoMode: TextInput.Password
                    inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText | Qt.ImhSensitiveData
                }
                PillButton {
                    id: saveButton
                    Layout.alignment: Qt.AlignLeft
                    u: page.u
                    strong: true
                    text: "Save and connect"
                    dim: tokenField.text.trim() === "" && !app.hasToken
                    Keys.onUpPressed: (event) => { if (!page.move(saveButton, false)) event.accepted = false }
                    Keys.onDownPressed: page.move(saveButton, true)
                    Keys.onLeftPressed: page.toCategories()
                    onClicked: {
                        if (tokenField.text.trim() === "" && !app.hasToken) return
                        app.saveConnection(urlField.text, tokenField.text)
                        tokenField.text = ""
                        page.done()
                    }
                }
            }

            ColumnLayout {
                visible: page.category === 1
                Layout.fillWidth: true
                spacing: 20 * page.u
                Heading { text: "Guest mode" }
                SettingRow {
                    label: "Guest mode"
                    value: app.guestMode ? "On" : "Off"
                    hint: app.guestMode ? (app.guestCount === 1 ? "1 guest joined" : app.guestCount + " guests joined")
                                          + " · turning it off and on makes a new QR code"
                                        : "Shows a QR code so guests can add songs from their phones"
                    onActivated: app.toggleGuestMode()
                }
                SettingRow {
                    id: guestsRow
                    visible: app.guestMode
                    label: "Guests and admins"
                    value: app.guestCount
                    hint: "Make a guest an admin, show an admin code, reset limits or remove someone"
                    onActivated: { page.returnTo = guestsRow; page.openGuests() }
                }
                SettingRow {
                    label: "Skips per guest"
                    value: app.guestSkips
                    onActivated: app.cycleGuestSkips()
                }
                SettingRow {
                    label: "Boosts per guest"
                    value: app.guestBoosts
                    hint: "A boost plays one of their own songs next"
                    onActivated: app.cycleGuestBoosts()
                }
                SettingRow {
                    label: "Songs waiting per guest"
                    value: app.guestMaxWaiting
                    onActivated: app.cycleGuestMaxWaiting()
                }
                SettingRow {
                    label: "Wait between adds"
                    value: app.guestCooldown === 0 ? "Off" : (app.guestCooldown < 60 ? app.guestCooldown + " s" : (app.guestCooldown / 60) + " min")
                    onActivated: app.cycleGuestCooldown()
                }
                Note { text: "Text under the QR code" }
                TvField {
                    id: captionField
                    placeholderText: "Scan to add songs"
                    onAccepted: app.setQrCaption(text)
                }
                Note { text: "Guest page public URL — only if you put a reverse proxy (HTTPS) in front of this TV; leave empty for the local network" }
                TvField {
                    id: publicUrlField
                    placeholderText: "e.g. https://party.example.com"
                    inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoAutoUppercase
                    onAccepted: app.setGuestPublicUrl(text)
                }
            }

            ColumnLayout {
                visible: page.category === 2
                Layout.fillWidth: true
                spacing: 20 * page.u
                Heading { text: "This speaker" }
                Note { text: "Player name — how this TV appears in Music Assistant" }
                TvField {
                    id: playerNameField
                    placeholderText: "Living Room TV"
                    onAccepted: { app.setPlayerName(text); text = app.playerName }
                }
                SettingRow {
                    id: outputRow
                    objectName: "audioOutputRow"
                    label: "Audio output"
                    value: app.audioOutputLabel
                    hint: "Where this TV's music comes out · changing it restarts the speaker for a moment"
                    onActivated: page.pick("Audio output", app.audioOutputs, outputRow,
                                           function(id) { app.setAudioOutput(id) })
                }
                SettingRow {
                    label: "Sync delay"
                    value: app.sendspinDelay === 0 ? "Off" : app.sendspinDelay + " ms"
                    hint: "Delay this TV's sound to line up with other speakers"
                    onActivated: app.cycleSendspinDelay()
                }
                SettingRow {
                    objectName: "logsRow"
                    label: "Logs"
                    value: app.problem !== "" ? "Something's wrong" : "Show"
                    hint: "What this TV's speaker and Couchside said lately, and a way to restart the speaker"
                    onActivated: page.openLogs()
                }
            }

            ColumnLayout {
                visible: page.category === 3
                Layout.fillWidth: true
                spacing: 20 * page.u
                Heading { text: "Visualizer" }
                SettingRow {
                    label: "Beat pulse on Now Playing"
                    value: app.visualizerEnabled ? "On" : "Off"
                    hint: "The cover and a glow behind it move with the music on this TV"
                    onActivated: app.visualizerEnabled = !app.visualizerEnabled
                }
                SettingRow {
                    id: sourceRow
                    objectName: "beatSourceRow"
                    label: "Beat source"
                    value: app.beatSourceLabel
                    hint: "What the visualizer listens to: this TV's music, one output, or a microphone"
                    onActivated: page.pick("Listen for the beat on", app.beatSources, sourceRow,
                                           function(id) { app.setBeatSource(id) })
                }
                SettingRow {
                    objectName: "beatIntensityRow"
                    label: "Beat intensity"
                    value: app.visualizerIntensity.toFixed(2)
                    hint: "How hard the Visualizer hits on each beat · Left and Right change it"
                    adjust: true
                    onAdjusted: (direction) => app.visualizerIntensity = app.visualizerIntensity + 0.05 * direction
                    onActivated: {
                        var steps = [0.5, 1.0, 1.5, 2.0]
                        var next = steps[0]
                        for (var i = 0; i < steps.length; i++) if (steps[i] > app.visualizerIntensity + 0.001) { next = steps[i]; break }
                        app.visualizerIntensity = next
                    }
                }
                SettingRow {
                    id: vizColoursRow
                    objectName: "vizColoursRow"
                    label: "Colours"
                    value: app.visualizerColoursLabel
                    hint: "The theme's two colours, the whole rainbow, or a new colour on every beat"
                    onActivated: page.pick("Visualizer colours", app.visualizerColourChoices, vizColoursRow,
                                           function(id) { app.setVisualizerColours(id) })
                }
                SettingRow {
                    label: "Edge lights on every picture"
                    value: app.visualizerEdges ? "On" : "Off"
                    hint: "The Edge Lights border over Radial, Flow and Bars too, running with the tempo"
                    onActivated: app.visualizerEdges = !app.visualizerEdges
                }
                SettingRow {
                    label: "Party lights"
                    value: app.partyLights ? "On" : "Off"
                    hint: "Party mode: colour along the screen edges that jumps on every beat"
                    onActivated: app.partyLights = !app.partyLights
                }
            }

            ColumnLayout {
                visible: page.category === 4
                Layout.fillWidth: true
                spacing: 20 * page.u
                Heading { text: "Lyrics" }
                SettingRow {
                    label: "Show lyrics"
                    value: app.lyricsEnabled ? "On" : "Off"
                    onActivated: app.lyricsEnabled = !app.lyricsEnabled
                }
                SettingRow {
                    label: "Visualizer behind the lyrics"
                    value: app.lyricsVisualizer ? "On" : "Off"
                    hint: "On Now Playing, the visualizer moves behind the words (off: the blurred cover)"
                    onActivated: app.lyricsVisualizer = !app.lyricsVisualizer
                }
                SettingRow {
                    label: "Size"
                    value: ({ small: "Small", medium: "Medium", large: "Large" })[app.lyricsSize]
                    onActivated: app.cycleLyricsSize()
                }
                SettingRow {
                    label: "Language"
                    value: ({ romanized: "Romanized", original: "Original", english_only: "English only" })[app.lyricsLanguage]
                    hint: ({ romanized: "Other scripts written in English letters",
                             original: "As sung, in the song's own script",
                             english_only: "Songs not sung in English show the artwork instead" })[app.lyricsLanguage]
                    onActivated: app.cycleLyricsLanguage()
                }
                SettingRow {
                    label: "English underneath"
                    value: app.lyricsTranslate ? "On" : "Off"
                    hint: "A translation under each line, for songs not in English"
                    onActivated: app.toggleLyricsTranslate()
                }
                SettingRow {
                    visible: app.lyricsTranslate
                    label: "Translation service"
                    value: ({ google: "Google", deepl: "DeepL", libretranslate: "LibreTranslate" })[app.translateService]
                    hint: ({ google: "No setup · unofficial, may stop working",
                             deepl: app.hasDeeplKey ? "Using your DeepL key" : "Needs a free DeepL API key (below)",
                             libretranslate: app.libretranslateUrl !== "" ? app.libretranslateUrl
                                                                          : "Needs your LibreTranslate address (below)" })[app.translateService]
                    onActivated: app.cycleTranslateService()
                }
                Note {
                    visible: app.lyricsTranslate && app.translateService === "deepl"
                    text: "DeepL API key — free at deepl.com/pro-api (keys ending in :fx are free keys)"
                }
                TvField {
                    id: deeplField
                    visible: app.lyricsTranslate && app.translateService === "deepl"
                    placeholderText: app.hasDeeplKey ? "Saved — press OK to replace it" : "Press OK to enter the key"
                    echoMode: TextInput.Password
                    inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText | Qt.ImhSensitiveData
                    onAccepted: { app.saveDeeplKey(text); text = "" }
                }
                Note {
                    visible: app.lyricsTranslate && app.translateService === "libretranslate"
                    text: "LibreTranslate address, e.g. http://192.168.30.3:5000"
                }
                TvField {
                    id: libreField
                    visible: app.lyricsTranslate && app.translateService === "libretranslate"
                    placeholderText: "Press OK to enter the address"
                    inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoAutoUppercase
                    onAccepted: app.setLibretranslateUrl(text)
                }
            }

            ColumnLayout {
                visible: page.category === 5
                Layout.fillWidth: true
                spacing: 20 * page.u
                Heading { text: "Look" }
                SettingRow {
                    id: coloursRow
                    objectName: "coloursRow"
                    label: "Colours"
                    value: {
                        var all = app.accents
                        for (var i = 0; i < all.length; i++) if (all[i].current) return all[i].label
                        return ""
                    }
                    hint: "The two colours used for focus, progress and the visualizer"
                    onActivated: page.pick("Colours", app.accents, coloursRow, function(id) { app.setAccent(id) })
                }
            }

            ColumnLayout {
                visible: page.category === 6
                Layout.fillWidth: true
                spacing: 20 * page.u
                Heading { text: "Updates" }
                SettingRow {
                    label: "Couchside " + app.appVersion
                    value: app.updateState === "available" ? "Install" : ""
                    hint: app.updateText
                    onActivated: app.installUpdate()
                }
                SettingRow {
                    label: "Sendspin"
                    hint: app.sendspinVersionText + " — new Sendspin versions arrive as Couchside updates"
                }
            }
        }
    }
}
