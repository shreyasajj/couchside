import QtQuick

// QR code from rows of "0"/"1" (app.qrRows), dark modules on white with the 4-module quiet
// zone scanners need; drawn crisply at whole-pixel module sizes.
Rectangle {
    id: qr
    property var rows: []
    property real size: 200
    readonly property int modules: rows.length + 8  // + quiet zone on each side
    readonly property real cell: modules > 8 ? Math.floor(size / modules) : 1

    width: cell * modules
    height: width
    color: "#ffffff"
    radius: cell * 1.5

    Canvas {
        id: canvas
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.fillStyle = "#000000"
            var r = qr.rows
            for (var y = 0; y < r.length; y++)
                for (var x = 0; x < r[y].length; x++)
                    if (r[y][x] === "1") ctx.fillRect((x + 4) * qr.cell, (y + 4) * qr.cell, qr.cell, qr.cell)
        }
    }
    onRowsChanged: canvas.requestPaint()
    onCellChanged: canvas.requestPaint()
}
