import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import "typing.js" as Typing

// Settings: Music Assistant connection and lyrics. Up/Down move between rows (the page
// scrolls to follow), OK changes a row. Text fields only start editing on OK, because
// Bigscreen's on-screen keyboard takes the arrow keys while a field is being edited;
// the keyboard's Enter or Back stops editing.
Kirigami.Page {
    id: page
    property real u: 1
    signal done()
    signal openGuests()
    property Item returnTo: null  // the row to focus when coming back from a page opened here

    padding: 0
    globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None
    background: Rectangle { color: "#0d0b1a" }

    function focusDefault() {
        if (returnTo && returnTo.visible) { returnTo.forceActiveFocus(); returnTo = null; return }
        (app.hasToken ? saveButton : tokenField).forceActiveFocus()
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
    function move(from, forward) {
        var next = from.nextItemInFocusChain(forward)
        if (!next) return
        var a = from.mapToItem(column, 0, 0).y, b = next.mapToItem(column, 0, 0).y
        if (forward ? b > a : b < a) next.forceActiveFocus()
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
        Keys.onUpPressed: page.move(tv, false)
        Keys.onDownPressed: page.move(tv, true)
        QQC2.TextField {
            id: input
            anchors.fill: parent
            focus: false
            // typing on a real keyboard: keep Bigscreen's on-screen keyboard out of the way
            Keys.onPressed: (event) => { if (Typing.typed(event)) Typing.hideKeyboard() }
            activeFocusOnTab: false
            font.pixelSize: 32 * page.u
            color: "#ffffff"
            placeholderTextColor: "#99ffffff"
            padding: 20 * page.u
            onAccepted: { tv.stopEditing(); tv.accepted() }
            background: Rectangle {
                radius: 10 * page.u
                color: input.activeFocus ? "#33ffffff" : "#22ffffff"
                border.width: tv.activeFocus ? 5 * page.u : 0
                border.color: "#4fc3f7"
            }
        }
    }

    // A row that toggles or cycles a setting with OK.
    component SettingRow: Rectangle {
        id: row
        property string label: ""
        property string value: ""
        property string hint: ""
        signal activated()
        Layout.fillWidth: true
        implicitHeight: (hint !== "" ? 124 : 96) * page.u
        radius: 12 * page.u
        activeFocusOnTab: true
        color: activeFocus ? "#33ffffff" : "#1affffff"
        border.width: activeFocus ? 5 * page.u : 0
        border.color: "#4fc3f7"
        Keys.onReturnPressed: activated()
        Keys.onEnterPressed: activated()
        Keys.onPressed: (event) => { if (event.key === Qt.Key_Select) { activated(); event.accepted = true } }
        Keys.onUpPressed: page.move(row, false)
        Keys.onDownPressed: page.move(row, true)
        ColumnLayout {
            anchors { fill: parent; leftMargin: 28 * page.u; rightMargin: 28 * page.u }
            spacing: 2 * page.u
            RowLayout {
                Layout.fillWidth: true
                QQC2.Label {
                    textFormat: Text.PlainText
                    Layout.fillWidth: true
                    text: row.label
                    color: "#ffffff"
                    font.pixelSize: 32 * page.u
                }
                QQC2.Label {
                    textFormat: Text.PlainText
                    text: row.value
                    color: "#4fc3f7"
                    font.pixelSize: 32 * page.u
                    font.weight: Font.Bold
                }
            }
            QQC2.Label {
                textFormat: Text.PlainText
                Layout.fillWidth: true
                visible: row.hint !== ""
                text: row.hint
                color: "#ffffff"
                opacity: 0.6
                font.pixelSize: 26 * page.u
                elide: Text.ElideRight
            }
        }
        MouseArea { anchors.fill: parent; onClicked: { row.forceActiveFocus(); row.activated() } }
    }

    component Heading: QQC2.Label {
        Layout.topMargin: 24 * page.u
        color: "#ffffff"
        font.pixelSize: 40 * page.u
        font.weight: Font.Bold
    }
    component Note: QQC2.Label {
        Layout.fillWidth: true
        color: "#ffffff"
        opacity: 0.8
        font.pixelSize: 28 * page.u
        wrapMode: Text.WordWrap
    }

    Flickable {
        id: flick
        anchors.fill: parent
        contentHeight: column.implicitHeight + 144 * page.u
        interactive: false
        clip: true
        Behavior on contentY { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        ColumnLayout {
            id: column
            x: (flick.width - width) / 2
            y: 72 * page.u
            width: Math.min(flick.width - 144 * page.u, 1300 * page.u)
            spacing: 24 * page.u

            QQC2.Label {

                textFormat: Text.PlainText
                text: "Settings"
                color: "#ffffff"
                font.pixelSize: 56 * page.u
                font.weight: Font.Bold
            }

            Heading { text: "Music Assistant" }
            QQC2.Label {
                textFormat: Text.PlainText
                Layout.fillWidth: true
                visible: app.connState === "auth_failed" && app.hasToken
                text: "Music Assistant did not accept the token. Create a new one and enter it below."
                color: "#ffd479"
                font.pixelSize: 30 * page.u
                wrapMode: Text.WordWrap
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
            QQC2.Button {
                id: saveButton
                Layout.alignment: Qt.AlignLeft
                text: "Save and connect"
                font.pixelSize: 32 * page.u
                padding: 24 * page.u
                Keys.onReturnPressed: clicked()
                Keys.onEnterPressed: clicked()
                Keys.onUpPressed: page.move(saveButton, false)
                Keys.onDownPressed: page.move(saveButton, true)
                background: Rectangle {
                    radius: 12 * page.u
                    color: (tokenField.text.trim() !== "" || app.hasToken) ? "#ffffff" : "#55ffffff"
                    border.width: saveButton.activeFocus ? 6 * page.u : 0
                    border.color: "#4fc3f7"
                }
                contentItem: QQC2.Label {
                    text: saveButton.text
                    font: saveButton.font
                    color: "#000000"
                    horizontalAlignment: Text.AlignHCenter
                }
                onClicked: {
                    if (tokenField.text.trim() === "" && !app.hasToken) return
                    app.saveConnection(urlField.text, tokenField.text)
                    tokenField.text = ""
                    page.done()
                }
            }

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

            Heading { text: "Sendspin speaker" }
            Note { text: "Player name — how this TV appears in Music Assistant" }
            TvField {
                id: playerNameField
                placeholderText: "Living Room TV"
                onAccepted: { app.setPlayerName(text); text = app.playerName }
            }
            SettingRow {
                label: "Audio output"
                value: app.audioDevice
                hint: "Changes restart the speaker for a moment"
                onActivated: app.cycleAudioDevice()
            }
            SettingRow {
                label: "Sync delay"
                value: app.sendspinDelay === 0 ? "Off" : app.sendspinDelay + " ms"
                hint: "Delay this TV's sound to line up with other speakers"
                onActivated: app.cycleSendspinDelay()
            }

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

            Heading { text: "Visualizer" }
            SettingRow {
                label: "Beat pulse"
                value: app.visualizerEnabled ? "On" : "Off"
                hint: "A glow behind the artwork that pulses with the music on this TV"
                onActivated: app.visualizerEnabled = !app.visualizerEnabled
            }
            SettingRow {
                label: "Party lights"
                value: app.partyLights ? "On" : "Off"
                hint: "Party mode: colour along the screen edges that jumps on every beat"
                onActivated: app.partyLights = !app.partyLights
            }

            Heading { text: "Lyrics" }
            SettingRow {
                label: "Show lyrics"
                value: app.lyricsEnabled ? "On" : "Off"
                onActivated: app.lyricsEnabled = !app.lyricsEnabled
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
    }
}
