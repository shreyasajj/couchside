import QtQuick

// Background for the screens behind Now Playing: the app's dark colour with a soft wash of
// the playing album's colour at the top, so every screen belongs to the music. Still (no
// blur, no animation).
Rectangle {
    id: bg
    property color tint: Theme.bg
    color: Theme.bg   // Kirigami's page transitions read this (opaque = slide behind)
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: parent.height * 0.6
        opacity: 0.55
        gradient: Gradient {
            GradientStop { position: 0.0; color: bg.tint }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }
}
