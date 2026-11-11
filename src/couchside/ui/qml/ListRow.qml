import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// One focusable list row: art or icon, title, subtitle, badges, trailing text.
// OK/Enter/Select emits activated().
FocusScope {
    id: row
    property real u: 1
    property string imageUrl: ""
    property string iconName: "media-optical-audio"
    property string title: ""
    property string subtitle: ""
    property var badges: []
    property string trailing: ""
    property bool dimmed: false
    property bool marked: false  // e.g. the song playing now
    signal activated()

    implicitHeight: 128 * u
    activeFocusOnTab: true

    Keys.onReturnPressed: activated()
    Keys.onEnterPressed: activated()
    Keys.onPressed: (event) => { if (event.key === Qt.Key_Select) { activated(); event.accepted = true } }

    Rectangle {
        anchors.fill: parent
        radius: 14 * row.u
        color: row.activeFocus ? "#33ffffff" : (row.marked ? "#1fffffff" : "transparent")
        border.width: row.activeFocus ? 5 * row.u : 0
        border.color: "#4fc3f7"
    }

    RowLayout {
        anchors { fill: parent; leftMargin: 20 * row.u; rightMargin: 28 * row.u }
        spacing: 28 * row.u
        opacity: row.dimmed ? 0.5 : 1

        Rectangle {
            Layout.preferredWidth: 96 * row.u
            Layout.preferredHeight: 96 * row.u
            radius: 10 * row.u
            color: "#2b2163"
            clip: true
            Kirigami.Icon {
                anchors.centerIn: parent
                width: parent.width * 0.5
                height: width
                source: row.iconName
                color: "#aaffffff"
                isMask: true
                visible: art.status !== Image.Ready
            }
            Image {
                id: art
                anchors.fill: parent
                source: row.imageUrl
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize: Qt.size(192, 192)
                visible: status === Image.Ready
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6 * row.u
            RowLayout {
                Layout.fillWidth: true
                spacing: 16 * row.u
                QQC2.Label {
                    Layout.fillWidth: true
                    text: row.title
                    color: "#ffffff"
                    font.pixelSize: 32 * row.u
                    font.weight: row.marked ? Font.Bold : Font.Normal
                    elide: Text.ElideRight
                }
                Repeater {
                    model: row.badges
                    delegate: Rectangle {
                        required property string modelData
                        radius: height / 2
                        color: "#334fc3f7"
                        implicitHeight: badge.implicitHeight + 8 * row.u
                        implicitWidth: badge.implicitWidth + 28 * row.u
                        QQC2.Label {
                            id: badge
                            anchors.centerIn: parent
                            text: parent.modelData
                            color: "#bfeaff"
                            font.pixelSize: 24 * row.u
                        }
                    }
                }
            }
            QQC2.Label {
                Layout.fillWidth: true
                visible: text !== ""
                text: row.subtitle
                color: "#ffffff"
                opacity: 0.7
                font.pixelSize: 26 * row.u
                elide: Text.ElideRight
            }
        }

        QQC2.Label {
            visible: text !== ""
            text: row.trailing
            color: "#ffffff"
            opacity: 0.7
            font.pixelSize: 28 * row.u
        }
    }

    MouseArea { anchors.fill: parent; onClicked: { row.forceActiveFocus(); row.activated() } }
}
