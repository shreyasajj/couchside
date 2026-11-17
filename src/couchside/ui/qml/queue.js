.pragma library

// The songs after the one playing, for the Up Next card: [{title, subtitle, imageUrl,
// trailing}]. `rows` is the queue (app.queueRows); `next` the next song's {title, artist,
// imageUrl} for before the queue has loaded; `fmt` formats seconds as a time.
function upcoming(rows, next, fmt) {
    var at = -1
    for (var i = 0; i < rows.length; i++) if (rows[i].current) { at = i; break }
    var out = []
    for (var j = at + 1; j < rows.length; j++)
        out.push({ title: rows[j].title, subtitle: rows[j].subtitle, imageUrl: rows[j].imageUrl,
                   trailing: rows[j].duration > 0 ? fmt(rows[j].duration) : "" })
    if (out.length === 0 && next.title !== "")   // the queue isn't loaded yet
        out.push({ title: next.title, subtitle: next.artist, imageUrl: next.imageUrl, trailing: "" })
    return out
}
