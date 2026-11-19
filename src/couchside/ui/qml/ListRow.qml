pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts

// One focusable list row: art or icon, title, subtitle, badges, trailing text.
// OK/Enter/Select emits activated(). The focused row is tinted with the accents, outlined
// and a touch larger; its text stays white.
FocusScope {
    id: row
    property real u: 1
    property string imageUrl: ""
    property string iconName: "music"
    property string title: ""
    property string subtitle: ""
    property var badges: []
    property string trailing: ""
    property string hint: ""     // a word shown at the right of the focused row ("PLAY")
    property bool dimmed: false
    property bool marked: false  // e.g. the song playing now
    property bool roundArt: false
    property real thumb: 96 * u
    property int titleSize: Theme.body
    signal activated()
    readonly property color ink: Theme.text

    implicitHeight: thumb + 36 * u
    activeFocusOnTab: true
    scale: activeFocus ? 1.012 : 1
    z: activeFocus ? 1 : 0
    Behavior on scale { NumberAnimation { duration: Theme.focusMs; easing.type: Easing.OutCubic } }

    Keys.onReturnPressed: (event) => { if (!event.isAutoRepeat) activated() }
    Keys.onEnterPressed: (event) => { if (!event.isAutoRepeat) activated() }
    Keys.onPressed: (event) => { if (event.key === Qt.Key_Select) { if (!event.isAutoRepeat) activated(); event.accepted = true } }

    Rectangle {  // soft ring outside the focused row
        visible: row.activeFocus
        anchors.fill: parent
        anchors.margins: -4 * row.u
        radius: 26 * row.u
        color: "transparent"
        border.width: 4 * row.u
        border.color: Theme.tint(Theme.a1, 0.16)
    }
    Rectangle {
        anchors.fill: parent
        radius: 22 * row.u
        color: Theme.surface
        border.width: 2 * row.u
        border.color: row.activeFocus ? Theme.a1 : "#0fffffff"
        gradient: row.activeFocus ? focusFill : null
    }
    Gradient {
        id: focusFill
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: Theme.tint(Theme.a1, 0.32) }
        GradientStop { position: 1; color: Theme.tint(Theme.a2, 0.2) }
    }
    Rectangle {  // the marked row's bar
        visible: row.marked
        anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 6 * row.u }
        width: 6 * row.u
        height: parent.height * 0.5
        radius: width / 2
        color: Theme.a1
    }

    RowLayout {
        anchors { fill: parent; leftMargin: 26 * row.u; rightMargin: 30 * row.u }
        spacing: 28 * row.u
        opacity: row.dimmed ? 0.5 : 1

        Rectangle {
            Layout.preferredWidth: row.thumb
            Layout.preferredHeight: row.thumb
            radius: row.roundArt ? width / 2 : 14 * row.u
            color: Theme.surfaceHigh
            clip: true
            Icon {
                anchors.centerIn: parent
                size: parent.width * 0.5
                name: row.iconName
                color: row.ink
                opacity: 0.7
                visible: art.status !== Image.Ready
            }
            Image {
                id: art
                anchors.fill: parent
                source: row.imageUrl
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize: Qt.size(208, 208)
                visible: status === Image.Ready
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4 * row.u
            RowLayout {
                Layout.fillWidth: true
                spacing: 16 * row.u
                Text {
                    textFormat: Text.PlainText
                    Layout.fillWidth: true
                    text: row.title
                    color: row.marked ? Theme.a1 : row.ink
                    font.pixelSize: row.titleSize * row.u
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                }
                Repeater {
                    model: row.badges
                    delegate: Rectangle {
                        required property string modelData
                        radius: height / 2
                        color: Theme.tint(Theme.a1, 0.14)
                        border.width: Math.max(1, row.u)
                        border.color: Theme.tint(Theme.a1, 0.5)
                        implicitHeight: badge.implicitHeight + 8 * row.u
                        implicitWidth: badge.implicitWidth + 32 * row.u
                        Text {
                            id: badge
                            textFormat: Text.PlainText
                            anchors.centerIn: parent
                            text: parent.modelData
                            color: Theme.a1
                            font.pixelSize: Theme.label * row.u
                            font.weight: Font.DemiBold
                        }
                    }
                }
            }
            Text {
                textFormat: Text.PlainText
                Layout.fillWidth: true
                visible: text !== ""
                text: row.subtitle
                color: Theme.textDim
                font.pixelSize: Theme.label * row.u
                font.weight: Font.Medium
                elide: Text.ElideRight
            }
        }

        Text {
            textFormat: Text.PlainText
            visible: text !== ""
            text: row.trailing
            color: Theme.textDim
            font.pixelSize: Theme.label * row.u
            font.features: { "tnum": 1 }
        }
        Text {
            objectName: "rowHint"
            textFormat: Text.PlainText
            visible: row.activeFocus && row.hint !== ""
            text: row.hint
            color: Theme.a1
            font.pixelSize: Theme.label * row.u
            font.weight: Font.Bold
            font.letterSpacing: 1 * row.u
        }
    }

    MouseArea { anchors.fill: parent; onClicked: { row.forceActiveFocus(); row.activated() } }
}
