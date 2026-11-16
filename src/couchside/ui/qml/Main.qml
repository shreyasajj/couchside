import QtQuick
import org.kde.kirigami as Kirigami

// The window. Everything on screen is the Shell (top bar, screens, overlays), which is
// Kirigami-free so it can be loaded in tests; Kirigami's own page stack stays empty.
Kirigami.ApplicationWindow {
    id: root
    title: "Couchside"
    visibility: Window.FullScreen
    color: Theme.bg

    // `flatpak run io.github.shreyasajj.Couchside --debug-focus` logs every focus change.
    readonly property bool debugFocus: Qt.application.arguments.indexOf("--debug-focus") >= 0
    onActiveFocusItemChanged: if (debugFocus) console.log("focus ->", activeFocusItem,
                                                          activeFocusItem ? activeFocusItem.objectName : "")

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.None

    Shell {
        id: shell
        anchors.fill: parent
        z: 1
        focus: true
        onRaiseRequested: {
            root.showFullScreen()
            root.raise()
            root.requestActivate()
        }
    }

    // Kirigami's page stack binds the Back key too (StandardKey.Back); two shortcuts on
    // one key make Qt rotate presses between them, so switch Kirigami's off and keep
    // Couchside's rules (close overlays, go back, confirm exit: Shell.goBack).
    Component.onCompleted: {
        var found = 0
        for (const list of [pageStack.resources, pageStack.data]) {
            if (!list) continue
            for (var i = 0; i < list.length; i++) {
                var o = list[i]
                if (o && o.sequences !== undefined && o.hasOwnProperty("autoRepeat")
                        && o.sequences.indexOf(StandardKey.Back) >= 0 && o.enabled) {
                    o.enabled = false
                    found++
                }
            }
        }
        console.info("Kirigami Back shortcuts disabled:", found)
    }
}
