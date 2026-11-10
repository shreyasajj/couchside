import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Phase 1 home: status, current track, transport. Phase 2 turns this into Now Playing (layout B).
Kirigami.Page {
    id: page
    property real u: 1
    signal openSetup()

    padding: 0
    globalToolBarStyle: Kirigami.ApplicationHeaderStyle.None
    background: Rectangle { color: "#0d0b1a" }

    function focusDefault() { playButton.forceActiveFocus() }
    Component.onCompleted: focusDefault()
    onVisibleChanged: if (visible) focusDefault()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 72 * page.u
        spacing: 24 * page.u

        RowLayout {
            Layout.fillWidth: true
            QQC2.Label {
                text: "Couchside"
                color: "#ffffff"
                opacity: 0.7
                font.pixelSize: 32 * page.u
                font.weight: Font.DemiBold
            }
            Item { Layout.fillWidth: true }
            FocusButton {
                id: settingsButton
                u: page.u
                size: 84 * page.u
                iconName: "configure"
                text: "Settings"
                KeyNavigation.down: playButton
                onClicked: page.openSetup()
            }
        }

        QQC2.Label {
            Layout.fillWidth: true
            visible: text !== ""
            text: app.statusText
            color: "#ffd479"
            font.pixelSize: 32 * page.u
            wrapMode: Text.WordWrap
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            spacing: 40 * page.u
            Layout.fillWidth: true

            Rectangle {
                Layout.preferredWidth: 280 * page.u
                Layout.preferredHeight: 280 * page.u
                radius: 12 * page.u
                color: "#2b2163"
                Image {
                    anchors.fill: parent
                    source: app.artUrl
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    visible: status === Image.Ready
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8 * page.u
                QQC2.Label {
                    Layout.fillWidth: true
                    text: app.title !== "" ? app.title : (app.hasLocalPlayer ? "Nothing playing" : "")
                    color: "#ffffff"
                    font.pixelSize: 72 * page.u
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: text !== ""
                    text: [app.artist, app.album].filter(s => s !== "").join(" · ")
                    color: "#ffffff"
                    opacity: 0.75
                    font.pixelSize: 40 * page.u
                    elide: Text.ElideRight
                }
            }
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 48 * page.u

            FocusButton {
                id: prevButton
                u: page.u
                iconName: "media-skip-backward"
                text: "Previous"
                KeyNavigation.right: playButton
                KeyNavigation.up: settingsButton
                onClicked: app.previous()
            }
            FocusButton {
                id: playButton
                u: page.u
                primary: true
                iconName: app.isPlaying ? "media-playback-pause" : "media-playback-start"
                text: app.isPlaying ? "Pause" : "Play"
                KeyNavigation.left: prevButton
                KeyNavigation.right: nextButton
                KeyNavigation.up: settingsButton
                onClicked: app.playPause()
            }
            FocusButton {
                id: nextButton
                u: page.u
                iconName: "media-skip-forward"
                text: "Next"
                KeyNavigation.left: playButton
                KeyNavigation.up: settingsButton
                onClicked: app.next()
            }
        }
    }
}
