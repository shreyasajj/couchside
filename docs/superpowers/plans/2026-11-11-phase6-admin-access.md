# Phase 6: Admin Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** The host can make a guest an admin from the TV (a one-time 6-digit code entered on the phone, or by promoting a connected guest). Admins get unlimited skips, full queue control (reorder, remove, shuffle), volume, speaker switching, and can remove a guest or reset their limits. The host can revoke admin at any time.

**Architecture:** Admin is a flag on the guest (by device id) in `GuestSession`, so it lasts across reconnects from the same phone and ends with guest mode. `core/guests.py` gains the code, promote/revoke, remove (with a ban for the session) and reset. `core/admin_actions.py` (Qt-free) runs admin actions through a small `AdminHost` the controller provides (volume, shuffle, speakers, switching the controlled speaker), so the server stays testable with fakes. The guest server adds `/api/admin/*` endpoints that refuse non-admins (403) and `/api/code`. The phone page grows an admin panel. The TV gets a Guests page (from Settings → Guest mode) and a large code overlay.

**Spec:** [Agents.md](../../../AGENTS.md) "Admin access", [design](../specs/2026-11-10-couchside-design.md) (admin status attaches to the device id until revoked or guest mode ends).

**Branch:** `phase6-admin-access` from `main` (after PR #8).

## Decisions (spec + my calls)

- Admin code: 6 digits from `secrets`, shown large on the TV with "Open the guest page on your phone → Admin code". One use; valid 10 minutes; cancelled when the host closes it. After 5 wrong tries (all phones together) the code is cancelled and the TV says so, so guessing is pointless (5 in a million). Entering a code needs the guest to have joined (they reach the page through the guest QR; admin rights come only from the host).
- Promote: Settings → Guest mode → "Guests and admins" lists connected guests; OK on one opens Make admin / Remove admin, Reset limits, Remove from party.
- Each guest gets a random public id for lists; device ids (the phone's secret) never leave the server.
- Admins: unlimited skips and boosts, no waiting limit or cooldown (they can reorder anything anyway); queue Play now / Play next / Move up / Move down / Remove on any song; shuffle on/off; volume (± and set); speaker list with "Control this speaker" (switches what the TV and guests control) and "Move music here" (transfer). Groups stay TV-only.
- Admins can remove guests and reset their limits, but not act on other admins; only the host grants or revokes admin.
- Removing a guest: forgotten and blocked from rejoining until guest mode restarts; their songs stay in the queue (the host or an admin can remove them) and keep their credit.
- Guest mode off (or on again, new token) ends every admin.

## Global Constraints

- Every admin endpoint checks token, device and admin flag on the server; a non-admin gets 403 with a JSON error. Inputs are size-checked; actions go through the session lock like guest actions.
- Phone page stays one file, no external requests, no innerHTML with server text.
- TV UX rules (D-pad only, focus never lost, ≥ 28 px text, plain-text labels for guest names).
- Commit messages never mention Claude Code; they end with the Co-Authored-By line.

## Review Focus

- A non-admin calling any `/api/admin/*` route or skipping past limits must be refused.
- Code guessing: wrong tries cancel the code; an expired or used code never works.
- A removed guest rejoining with the same or a new name on the same device is refused.
- Revoke while the phone is open: the next action is refused and the panel disappears on refresh.
- Admin acting on an admin (remove/reset) is refused.

## Tasks

1. **Session: admin, code, remove, reset** — `core/guests.py`: `Guest.admin`, `Guest.public_id`; `GuestSession.new_admin_code(now) -> str`, `cancel_admin_code()`, `admin_code` / `code_expires`, `redeem_code(guest, code, now)` (wrong tries counted, 5 cancels), `promote(public_id)`, `revoke(public_id)`, `remove(public_id)` (ban device), `reset(public_id)`, `by_public_id`; join refuses banned devices; `check_add` / `use_skip` / `use_boost` skip limits for admins; `added_by` keeps names of removed guests. Tests for each.
2. **Admin actions** — `core/admin_actions.py`: `AdminHost` dataclass of callables (`volume() -> int|None`, `set_volume(int)`, `shuffle() -> bool|None`, `set_shuffle(bool)`, `speakers() -> list[dict]`, `control(player_id)`, `transfer(player_id)`); `queue_action(client, queue_id, session, guest, item_id, action)`, `guest_action(session, actor, public_id, action)` (reset/remove; not on admins), `admin_state(...)` (guests list, speakers, volume, shuffle). Tests with fakes.
3. **Server** — `POST /api/code`, `POST /api/admin/queue`, `/shuffle`, `/volume`, `/speaker`, `/guest`; `state` includes `admin: bool` and, for admins, `adminInfo` and all upcoming songs with ids. Rate-limit code tries per device. Tests: 403 for non-admins on every route, code flow, removed guest refused, admin skip unlimited.
4. **Phone page** — "Admin code" entry; admin badge; queue rows with controls; shuffle, volume, speakers, guests (Reset / Remove). jsdom check against a test server.
5. **TV** — controller: `guestRows`, `promoteGuest`, `revokeGuest`, `resetGuest`, `removeGuest`, `showAdminCode` / `adminCode` / `closeAdminCode`, `AdminHost` wiring, toast when someone becomes admin or a code is cancelled; QML: `GuestsPage.qml`, admin code overlay in Main, Settings row "Guests and admins", "Admin" mark on queue/credits not needed. Tests for controller slots and the page; TV check with simulated phones.
6. **Docs + PR** — README admin section and API notes; PR, CI, merge on approval.
