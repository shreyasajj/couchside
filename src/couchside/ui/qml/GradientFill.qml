pragma ComponentBehavior: Bound
import QtQuick

// The look's signature: a fill running from the first accent to the second, left to right.
Rectangle {
    gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: Theme.a1 }
        GradientStop { position: 1; color: Theme.a2 }
    }
}
