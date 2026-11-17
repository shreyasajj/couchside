import QtQuick

// The song, small, in the top-left corner (party mode, and Now Playing while the lyrics
// show): the cover beside the title, artist and who added it. It drifts gently up and
// down so it reads as floating over the picture, out of the way of the words. Only to
// look at. The drift runs on the graphics thread (an animator): no work for the app.
Item {
    id: card
    property real u: 1
    property bool running: true        // drift (on screen, app in front)
    readonly property real cover: 120 * u

    implicitWidth: 960 * u
    implicitHeight: cover

    Item {
        id: drift
        width: card.width
        height: card.height
        SequentialAnimation on y {
            running: card.running && card.visible
            loops: Animation.Infinite
            YAnimator { from: 0; to: -10 * card.u; duration: 3200; easing.type: Easing.InOutSine }
            YAnimator { from: -10 * card.u; to: 0; duration: 3200; easing.type: Easing.InOutSine }
        }

        Cover {
            id: art
            width: card.cover
            height: card.cover
            radius: 16 * card.u
            source: app.artUrl
        }
        Column {
            anchors { left: art.right; leftMargin: 24 * card.u; right: parent.right; verticalCenter: art.verticalCenter }
            spacing: 2 * card.u
            Text {
                textFormat: Text.PlainText
                width: parent.width
                text: app.title
                color: Theme.text
                font.pixelSize: Theme.heading * card.u
                font.weight: Font.ExtraBold
                elide: Text.ElideRight
            }
            Text {
                textFormat: Text.PlainText
                width: parent.width
                visible: text !== ""
                text: [app.artist, app.album].filter(s => s !== "").join(" — ")
                color: Theme.textDim
                font.pixelSize: Theme.body * card.u
                font.weight: Font.Medium
                elide: Text.ElideRight
            }
            Text {
                textFormat: Text.PlainText
                width: parent.width
                visible: app.nowPlayingCredit !== ""
                text: "Added by " + app.nowPlayingCredit
                color: Theme.a1
                font.pixelSize: Theme.label * card.u
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
        }
    }
}
