import QtQuick

// Image that keeps the old picture until the new one has loaded, then cross-fades.
// An empty source, or a source that fails to load, fades the picture out.
Item {
    id: root
    property url source
    property int fillMode: Image.PreserveAspectCrop
    property size sourceSize: Qt.size(0, 0)
    property int duration: 500

    property bool showFront: true
    readonly property Image shownLayer: showFront ? front : back
    readonly property Image hiddenLayer: showFront ? back : front
    readonly property bool hasImage: shownLayer.status === Image.Ready && shownLayer.source != ""
    readonly property url shownSource: hasImage ? shownLayer.source : ""

    onSourceChanged: {
        if (source == "") {
            front.source = ""
            back.source = ""
            return
        }
        if (shownLayer.source == source) return              // already on screen
        if (hiddenLayer.source == source) {                    // e.g. Next then Previous
            if (hiddenLayer.status === Image.Ready) showFront = !showFront
            else if (hiddenLayer.status === Image.Error) shownLayer.source = ""
            return                                             // still loading: onStatusChanged flips
        }
        hiddenLayer.source = source
    }

    function settle(layer) {
        if (layer.source != root.source) return               // a stale load finishing
        if (layer.status === Image.Ready && layer !== shownLayer) showFront = !showFront
        else if (layer.status === Image.Error) shownLayer.source = ""
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
        onStatusChanged: root.settle(front)
    }
    Layer {
        id: back
        opacity: !root.showFront && status === Image.Ready ? 1 : 0
        onStatusChanged: root.settle(back)
    }
}
