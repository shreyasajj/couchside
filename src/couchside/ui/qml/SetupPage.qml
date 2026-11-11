import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Music Assistant server + token. Every field reachable with up/down; OK opens the on-screen keyboard.
Kirigami.Page {
    id: page
    property real u: 1
    signal done()

    padding: 0
    globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None
    background: Rectangle { color: "#0d0b1a" }

    function focusDefault() { (app.hasToken ? saveButton : tokenField).forceActiveFocus() }
    Component.onCompleted: {
        urlField.text = app.serverUrl
        focusDefault()
    }

    component TvField: QQC2.TextField {
        Layout.fillWidth: true
        font.pixelSize: 32 * page.u
        color: "#ffffff"
        placeholderTextColor: "#99ffffff"
        padding: 20 * page.u
        background: Rectangle {
            radius: 10 * page.u
            color: "#22ffffff"
            border.width: parent.activeFocus ? 5 * page.u : 0
            border.color: "#4fc3f7"
        }
    }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 144 * page.u, 1300 * page.u)
        spacing: 28 * page.u

        QQC2.Label {
            text: "Connect to Music Assistant"
            color: "#ffffff"
            font.pixelSize: 56 * page.u
            font.weight: Font.Bold
        }
        QQC2.Label {
            Layout.fillWidth: true
            visible: app.connState === "auth_failed" && app.hasToken
            text: "Music Assistant did not accept the token. Create a new one and enter it below."
            color: "#ffd479"
            font.pixelSize: 30 * page.u
            wrapMode: Text.WordWrap
        }

        QQC2.Label { text: "Server address"; color: "#ffffff"; opacity: 0.8; font.pixelSize: 30 * page.u }
        TvField {
            id: urlField
            placeholderText: "Leave empty to find it automatically"
            inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoAutoUppercase
            KeyNavigation.down: tokenField
        }

        QQC2.Label {
            Layout.fillWidth: true
            text: "Access token — in the Music Assistant web app: Settings → your profile → Long-lived access tokens"
            color: "#ffffff"
            opacity: 0.8
            font.pixelSize: 30 * page.u
            wrapMode: Text.WordWrap
        }
        TvField {
            id: tokenField
            placeholderText: app.hasToken ? "Saved — leave empty to keep it" : "Paste or type the token"
            echoMode: TextInput.Password
            inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText | Qt.ImhSensitiveData
            KeyNavigation.up: urlField
            KeyNavigation.down: saveButton.enabled ? saveButton : lyricsRow
        }

        QQC2.Button {
            id: saveButton
            Layout.alignment: Qt.AlignLeft
            text: "Save and connect"
            font.pixelSize: 32 * page.u
            padding: 24 * page.u
            KeyNavigation.up: tokenField
            KeyNavigation.down: lyricsRow
            Keys.onReturnPressed: clicked()
            Keys.onEnterPressed: clicked()
            enabled: tokenField.text.trim() !== "" || app.hasToken
            background: Rectangle {
                radius: 12 * page.u
                color: saveButton.enabled ? "#ffffff" : "#55ffffff"
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
                app.saveConnection(urlField.text, tokenField.text)
                tokenField.text = ""
                page.done()
            }
        }

        QQC2.Label {
            Layout.topMargin: 24 * page.u
            text: "Display"
            color: "#ffffff"
            font.pixelSize: 40 * page.u
            font.weight: Font.Bold
        }
        // OK toggles; takes effect on Now Playing straight away.
        Rectangle {
            id: lyricsRow
            Layout.fillWidth: true
            implicitHeight: 96 * page.u
            radius: 12 * page.u
            activeFocusOnTab: true
            color: activeFocus ? "#33ffffff" : "#1affffff"
            border.width: activeFocus ? 5 * page.u : 0
            border.color: "#4fc3f7"
            KeyNavigation.up: saveButton.enabled ? saveButton : tokenField
            Keys.onReturnPressed: app.lyricsEnabled = !app.lyricsEnabled
            Keys.onEnterPressed: app.lyricsEnabled = !app.lyricsEnabled
            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Select) { app.lyricsEnabled = !app.lyricsEnabled; event.accepted = true }
            }
            RowLayout {
                anchors { fill: parent; leftMargin: 28 * page.u; rightMargin: 28 * page.u }
                QQC2.Label {
                    Layout.fillWidth: true
                    text: "Show lyrics"
                    color: "#ffffff"
                    font.pixelSize: 32 * page.u
                }
                QQC2.Label {
                    text: app.lyricsEnabled ? "On" : "Off"
                    color: app.lyricsEnabled ? "#4fc3f7" : "#99ffffff"
                    font.pixelSize: 32 * page.u
                    font.weight: Font.Bold
                }
            }
            MouseArea { anchors.fill: parent; onClicked: app.lyricsEnabled = !app.lyricsEnabled }
        }
    }
}
