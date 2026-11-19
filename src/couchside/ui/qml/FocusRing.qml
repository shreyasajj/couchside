pragma ComponentBehavior: Bound
import QtQuick

// The focus mark: a ring in the first accent with a soft glow outside it. Fill the item
// it marks (anchors.fill) and bind `shown` to that item's focus.
Item {
    id: ring
    property real u: 1
    property real radius: 0
    property bool shown: false
    visible: shown

    Rectangle {  // glow
        anchors.fill: parent
        anchors.margins: -9 * ring.u
        radius: ring.radius + 9 * ring.u
        color: "transparent"
        border.width: 6 * ring.u
        border.color: Theme.tint(Theme.a1, 0.2)
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: -3 * ring.u
        radius: ring.radius + 3 * ring.u
        color: "transparent"
        border.width: 3 * ring.u
        border.color: Theme.a1
    }
}
