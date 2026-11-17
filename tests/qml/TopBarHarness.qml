import QtQuick
import "../../src/couchside/ui/qml"

// The top bar on its own, the size it has on a 1080p TV.
Item {
    width: 1920; height: 1080
    property var went: []
    property int guestToggles: 0
    property int downs: 0
    TopBar {
        id: bar
        objectName: "bar"
        width: parent.width
        screen: "queue"
        speakerName: "Living Room TV"
        onGo: (name) => { var w = parent.went.slice(); w.push(name); parent.went = w }
        onToggleGuest: parent.guestToggles++
        onLeaveDown: parent.downs++
    }
}
