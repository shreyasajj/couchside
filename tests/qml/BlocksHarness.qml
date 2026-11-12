import QtQuick
import "../../src/couchside/ui/qml"

// Loads the Kirigami-free building blocks together, the way a page uses them.
Item {
    width: 1920; height: 1080
    property int clicks: 0
    property int rowHits: 0
    FocusButton { id: button; objectName: "button"; iconName: "shuffle"; text: "Shuffle off"; onClicked: parent.clicks++ }
    FocusButton { id: playButton; objectName: "playButton"; x: 200; primary: true; iconName: "play"; text: "Play" }
    Icon { id: icon; objectName: "icon"; name: "queue" }
    UpNext { id: upNext; objectName: "upNext"; x: 600 }
    PageBackground { objectName: "background"; anchors.fill: parent; z: -1; tint: "#804020" }
    ListRow { id: row; objectName: "row"; y: 300; width: 900; title: "<i>Bobby</i>"; subtitle: "Skips left 2"
              badges: ["Admin"]; trailing: "3:05"; onActivated: parent.rowHits++ }
    MediaCardItem { objectName: "card"; x: 1000; y: 300; title: "Luna"; subtitle: "Bolier"; kind: "artist" }
    PillButton { objectName: "pill"; x: 1400; y: 300; text: "Save and connect"; onClicked: parent.clicks += 10 }
    EdgeLights { id: lights; objectName: "lights"; anchors.fill: parent }
}
