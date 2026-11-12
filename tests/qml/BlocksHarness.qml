import QtQuick
import "../../src/couchside/ui/qml"

// Loads the Kirigami-free building blocks together, the way a page uses them.
Item {
    width: 1920; height: 1080
    property int clicks: 0
    FocusButton { id: button; objectName: "button"; iconName: "shuffle"; text: "Shuffle off"; onClicked: parent.clicks++ }
    FocusButton { id: playButton; objectName: "playButton"; x: 200; primary: true; iconName: "play"; text: "Play" }
    Icon { id: icon; objectName: "icon"; name: "queue" }
    UpNext { id: upNext; objectName: "upNext"; x: 600 }
    EdgeLights { id: lights; objectName: "lights"; anchors.fill: parent }
}
