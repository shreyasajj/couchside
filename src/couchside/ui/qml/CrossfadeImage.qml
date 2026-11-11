import QtQuick

// Image that keeps the old picture until the new one has loaded, then cross-fades.
// An empty source fades the picture out.
Item {
    id: root
    property url source
    property int fillMode: Image.PreserveAspectCrop
    property size sourceSize: Qt.size(0, 0)
    property int duration: 500
    readonly property bool hasImage: (front.status === Image.Ready && front.opacity > 0)
                                     || (back.status === Image.Ready && back.opacity > 0)

    property bool showFront: true

    onSourceChanged: {
        var target = showFront ? back : front
        target.source = source
        if (source == "") {  // nothing to load: fade both out
            front.source = ""
            back.source = ""
        }
    }

    component Layer: Image {
        anchors.fill: parent
        fillMode: root.fillMode
        sourceSize: root.sourceSize
        asynchronous: true
        cache: true
        smooth: true
        Behavior on opacity { NumberAnimation { duration: root.duration; easing.type: Easing.InOutQuad } }
    }

    Layer {
        id: front
        opacity: root.showFront && status === Image.Ready ? 1 : 0
        onStatusChanged: if (status === Image.Ready && source == root.source && !root.showFront) root.showFront = true
    }
    Layer {
        id: back
        opacity: !root.showFront && status === Image.Ready ? 1 : 0
        onStatusChanged: if (status === Image.Ready && source == root.source && root.showFront) root.showFront = false
    }
}
