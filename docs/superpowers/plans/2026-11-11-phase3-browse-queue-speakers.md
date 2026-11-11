# Phase 3: Search, Queue, Recents, Speakers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** From the TV remote: search Music Assistant and play results (now / next / add to queue), see recently played and recently added, view and edit the queue, and pick, sync, group and hand the queue between speakers.

**Architecture:** Three Qt-free core modules turn MA objects into plain rows and run the commands: `core/library.py` (search, recents, play), `core/queue.py` (queue rows, jump/move/remove), `core/speakers.py` (speaker rows, select, sync, groups, transfer). The controller exposes each as a JS-array property with its own change signal (`libraryChanged`, `queueChanged`, `speakersChanged`) so Now Playing does not re-render for them. Three new pages (Library, Queue, Speakers) open from buttons on the Now Playing bar; one reusable `ActionSheet` gives every row its actions.

**Tech Stack:** Python 3.13, PySide6 6.11, QML + Kirigami, music-assistant-client 1.8.0 against MA 2.10.9 (schema 65).

**Spec:** [docs/superpowers/specs/2026-11-10-couchside-design.md](../specs/2026-11-10-couchside-design.md), [Agents.md](../../../Agents.md) "Speaker / group picker" and "Search and browse".

**Branch:** `phase3-browse-queue-speakers` from `main`.

## Verified on the live server (2026-11-11)

- `music.search(q, limit=N)` → `SearchResults` with `tracks albums artists playlists radio` (library + Tidal + Spotify). Items have `name`, `uri`, `image`, tracks `artist_str`, `duration`, `album`.
- `music.recently_played(limit)` → `ItemMapping`s (artists, albums, playlists, tracks) with `uri`, `media_type`, `image`.
- `music.recently_added_tracks` needs schema 101 (**not available** on 2.10.9) → use `music.get_library_tracks(limit, order_by="timestamp_added_desc")`.
- `player_queues.play_media(queue_id, uri_or_item, QueueOption.PLAY|NEXT|ADD)`; `get_queue_items(queue_id)` returns items in queue order (`sort_index`); `play_index(queue_id, item_id)`, `move_up/move_down/move_next(queue_id, item_id)`, `delete_item(queue_id, item_id)`, `transfer_queue(src, dst, auto_play)`.
- Players: `type` (player/group), `group_members`, `can_group_with`, `synced_to`, `active_group`, `enabled`, `available`. Available now: this TV (`upa0dd8b65`) and "Shreyas's Mac mini" (`up2846df56a3c3`), each `can_group_with` the other and `supported_features` includes `set_members`. Player providers include `sync_group` (permanent groups).
- Sync: `players.set_members(target, player_ids_to_add=[…], player_ids_to_remove=[…])`. Named group: `players.create_group_player("sync_group", name, members)`; delete with `players.remove_group_player(id)`.

## Global Constraints

- Every action reachable with D-pad + OK + Back only; focus ring `#4fc3f7`; focus never gets lost, including when a list updates under the focused row.
- Minimum body text ~28 px at 1080p (`* u`); large targets; no hover-only UI.
- Back always goes to the previous screen.
- Never crash on a missing server or missing fields; every MA call is caught and logged; a failed action shows a short on-screen message.
- Groups created while testing are removed afterwards; existing groups are left alone.
- Commit messages never mention Claude Code; they end with the Co-Authored-By line.

## Decisions (my calls; changeable)

- **Navigation:** the Now Playing bar gains Search, Queue and Speakers buttons beside Settings (right side). Each opens a page; Back returns to the button.
- **Results:** search runs 500 ms after typing stops or on OK. Results show as horizontal rows by type (Tracks, Albums, Artists, Playlists, Radio), Up/Down between rows, Left/Right within. With an empty query the page shows "Recently played" and "Recently added".
- **Actions:** OK on any result opens the action sheet: Play now, Play next, Add to queue. No drilling into albums/artists in this phase.
- **Queue page:** upcoming items in order, the current one marked. OK on a row: Play this now, Play next, Move up, Move down, Remove.
- **Speakers page:** one row per enabled player and group, available first; shows "This TV", "Controlling", "Synced with …" and what it is playing. OK on a row: Control this speaker, Move the queue here, Sync with the controlled speaker / Stop syncing. A "New group" button opens a member checklist and creates a `sync_group` named from its members ("Living Room TV + Mac mini"); a group row adds Edit members and Delete group.
- **Controlled speaker** choice lasts for the session; on launch the app always starts on this TV (spec: auto-select).
- **Recents** refresh when the Library page opens and after any play action.

## Review Focus

1. **List updates under focus** (queue items change while a row is focused, e.g. a track ends) → focus stays on the same item if it still exists, else the nearest row; never lost. (Task 5 `restoreIndex` + TV check.)
2. **Speaker disappears** (controlled speaker goes unavailable or a group is deleted) → controls fall back to this TV; no crash. (Task 3 `test_controlled_speaker_falls_back_when_gone`.)
3. **Search while disconnected or failing** → empty results with "Search failed — check the connection", not an exception. (Task 1 `test_search_failure_returns_error`.)
4. **Actions on a queue-less source** (no MA queue for the controlled speaker) → queue page shows "Nothing queued"; play actions still work via the player's queue id. (Task 2 `test_no_queue_is_empty`.)
5. **Rapid repeated OK on an action** (double press) → one command per press, no duplicate sheet; sheet closes after the first. (Task 5 TV check.)

---

### Task 1: Library core (search, recents, play)

**Files:** Create `src/couchside/core/library.py`; Test `tests/test_library.py`.

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) MediaCard(key: str, kind: str, title: str, subtitle: str, image_url: str | None, uri: str)` — `kind` in `track album artist playlist radio`; `key` = uri.
  - `to_card(item) -> MediaCard | None` (None when no uri). Subtitle: track → `artist_str · album`, album → artist, playlist → owner, others "".
  - `async search(client, query: str, limit: int = 12) -> SearchOutcome` where `SearchOutcome(rows: list[tuple[str, list[MediaCard]]], error: str)`; rows in order Tracks, Albums, Artists, Playlists, Radio, empty rows dropped; blank query → no rows, no call.
  - `async recents(client, limit: int = 15) -> list[tuple[str, list[MediaCard]]]` → `("Recently played", …)`, `("Recently added", …)`, each failing independently to an empty row (dropped).
  - `async play(client, queue_id: str, uri: str, mode: str) -> bool` — mode `now|next|add` → `QueueOption.PLAY|NEXT|ADD`.
- Image: `item.image.path` when it is an http(s) URL, else MA proxy URL is not built here (None).

- [ ] **Step 1: failing tests** — `test_track_card_subtitle`, `test_card_without_uri_is_none`, `test_search_orders_and_drops_empty_rows`, `test_blank_query_does_not_call_server`, `test_search_failure_returns_error` (raises → `error == "Search failed — check the connection"`, rows empty), `test_recents_survive_one_failing_call`, `test_recently_added_uses_library_order` (asserts `get_library_tracks(limit=…, order_by="timestamp_added_desc")`), `test_play_modes_map_to_queue_options`, `test_play_failure_returns_false`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_library.py -q` → FAIL (module missing).
- [ ] **Step 3:** implement.
- [ ] **Step 4:** `.venv/bin/pytest -q` → all pass.
- [ ] **Step 5:** commit `feat: library search, recents and play actions`.

### Task 2: Queue core

**Files:** Create `src/couchside/core/queue.py`; Test `tests/test_queue.py`.

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) QueueRow(item_id: str, title: str, subtitle: str, image_url: str | None, duration: float | None, current: bool)`.
  - `async load_queue(client, queue_id: str | None, current_item_id: str | None) -> list[QueueRow]` — items from `get_queue_items` in order; rows **before** the current item are dropped (history), current first; title from `media_item.name` else `name`; subtitle `artist_str`. `None` queue → `[]`.
  - `async queue_action(client, queue_id, item_id, action: str) -> bool` — `play` → `play_index`, `next` → `move_next`, `up` → `move_up`, `down` → `move_down`, `remove` → `delete_item`.
- [ ] Step 1 tests: `test_rows_start_at_current`, `test_titles_prefer_media_item`, `test_no_queue_is_empty`, `test_actions_call_queue_api` (one per action), `test_unknown_action_is_false`, `test_action_failure_is_false`.
- [ ] Steps 2–5 as Task 1; commit `feat: queue rows and queue actions`.

### Task 3: Speakers core

**Files:** Create `src/couchside/core/speakers.py`; Modify `src/couchside/core/playback.py` (fallback); Test `tests/test_speakers.py`, `tests/test_playback.py`.

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) SpeakerRow(player_id, name, is_group: bool, available: bool, controlled: bool, local: bool, synced_to: str | None, members: tuple[str, ...], can_sync: bool, playing: str)` — `playing` = "Title — Artist" or "".
  - `speaker_rows(players, controlled_id, local_id) -> list[SpeakerRow]` — enabled players only (synced members included, with `synced_to` naming their leader); order: controlled, local, other available, unavailable; names sorted within.
  - `can_sync = target is available and player_id in controlled.can_group_with`.
  - `async speaker_action(client, controlled_id, player_id, action, members=()) -> bool` — `sync` → `set_members(controlled_id, player_ids_to_add=[player_id])`; `unsync` → `set_members(leader, player_ids_to_remove=[player_id])` (leader = `synced_to` or controlled); `transfer` → `player_queues.transfer_queue(src_queue, player_id, auto_play=True)` with src = controlled player's `active_source or player_id`; `create_group` → `create_group_player("sync_group", name, list(members))`, name = `" + ".join(member names)`; `edit_group` → `set_members(group_id, add, remove)` from the diff; `delete_group` → `remove_group_player`.
  - `Playback`: when `user_player_id` points at a player that no longer exists or is unavailable, fall back to the local player and clear `user_player_id`.
- [ ] Step 1 tests: `test_rows_order_and_flags`, `test_disabled_players_hidden`, `test_playing_text`, `test_can_sync_uses_can_group_with`, `test_sync_and_unsync_calls`, `test_transfer_uses_active_queue`, `test_create_group_name_from_members`, `test_edit_group_diff`, `test_delete_group`, `test_action_failure_is_false`, `test_controlled_speaker_falls_back_when_gone` (playback).
- [ ] Steps 2–5; commit `feat: speaker rows, sync, groups and queue transfer`.

### Task 4: Controller

**Files:** Modify `src/couchside/ui/controller.py`; Test `tests/test_controller_props.py`.

**Interfaces:**
- Produces (JS arrays of plain dicts with camelCase keys):
  - `libraryRows` (`[{title, items:[{key, kind, title, subtitle, imageUrl, uri}]}]`), `libraryError`, `libraryBusy`, notify `libraryChanged`; slots `search(str)`, `loadRecents()`, `playUri(str uri, str mode)`.
  - `queueRows` (`[{itemId, title, subtitle, imageUrl, duration, current}]`), notify `queueChanged`; slots `loadQueue()`, `queueAction(str itemId, str action)`. Queue reloads on MA `queue_items_updated`/`queue_updated` for the controlled queue while the Queue page is open (`queueVisible` property set by QML).
  - `speakerRows` (`[{playerId, name, isGroup, available, controlled, local, syncedTo, members, canSync, playing}]`), notify `speakersChanged` (recomputed on player events); slots `controlSpeaker(id)`, `speakerAction(id, action)`, `createGroup(list ids)`, `editGroup(id, list ids)`.
  - `toast: str` + `toastChanged`: short message after a failed action ("Couldn't add to queue"), cleared after 4 s by QML.
  - Image URLs go through `art_url(…, 256)`.
- [ ] Step 1 tests: rows shape for each list, `search` sets error text on failure, `playUri` schedules `library.play` with the controlled queue id, `controlSpeaker` sets `playback.user_player_id` and refreshes, failed action sets `toast`.
- [ ] Steps 2–5; commit `feat: expose library, queue and speakers to QML`.

### Task 5: Pages

**Files:** Create `src/couchside/ui/qml/LibraryPage.qml`, `QueuePage.qml`, `SpeakersPage.qml`, `GroupEditor.qml`, `ActionSheet.qml`, `MediaCardItem.qml`, `ListRow.qml`, `Toast.qml`; Modify `NowPlayingPage.qml` (Search/Queue/Speakers buttons), `Main.qml` (page routing, toast).

Behaviour:
- **ActionSheet:** modal list of large buttons with a title; opens with focus on the first action; OK runs the action and closes; Back closes; returns focus to the row that opened it. Ignores OK while closing (no double run).
- **LibraryPage:** search `TextField` at top (OK opens the on-screen keyboard); below it a vertical `ListView` of rows, each a horizontal `ListView` of `MediaCardItem` (square art 240·u, title 28·u, subtitle 24·u). Down from the field goes to the first row; Up from the first row returns to the field. Busy and error text shown under the field.
- **QueuePage:** vertical list of `ListRow` (art 96·u, title 32·u, subtitle 26·u, duration); current row marked "Now playing". `restoreIndex()` after each model change: same `itemId` if present, else clamp to the old index.
- **SpeakersPage:** list of `ListRow` for speakers (icon: speaker or group; badges "This TV", "Controlling", "Synced with X"); a "New group" button at the bottom. `GroupEditor`: checklist of available speakers that can group, Save/Cancel.
- **Toast:** bottom-centre message for 4 s.
- Focus: every page's `focusDefault()`; Back via `Main.goBack()` (sheet first, then page).

- [ ] **Step 1: TV check** (deploy, keys via `evemu-event` on the remote's device, screenshots read):
  1. Search "love": rows appear; Down/Right moves across cards; OK → sheet; "Add to queue" adds it (Queue page shows it at the end).
  2. Empty query shows Recently played / Recently added.
  3. Queue: Move up/down reorders; Remove removes; focus stays on a row after each change; Play this now jumps.
  4. Speakers: TV row "This TV · Controlling"; select Mac mini → Now Playing shows Mac mini's state; select TV again.
  5. Sync Mac mini with TV → row shows "Synced with Living Room TV"; Stop syncing.
  6. New group (TV + Mac mini) → group row appears; Delete group → gone. **No test groups left behind.**
  7. Move the queue to the Mac mini and back to the TV.
  8. Back from each page returns focus to its Now Playing button.
- [ ] **Step 2:** commit `feat: library, queue and speaker pages`.

### Task 6: Docs

- [ ] README: status → Phase 3; remote section for the new pages; API notes (recently-added on schema < 101, group creation via `sync_group`, queue history hidden).
- [ ] `.venv/bin/pytest -q` → all pass; commit `docs: phase 3`.
