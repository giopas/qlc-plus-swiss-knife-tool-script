# Stage Monitor: the QLC+ web socket protocol

What the Stage Monitor page (`core/stage_page/page.html`) relies on, read in the QLC+ source (`webaccess/src/webaccess-qml.cpp`, `qmlui/virtualconsole/vccuelist.cpp`, tags `QLC+_5.2.2` and `QLC+_5.3.0`, which are the same here) and checked on 17 October 2026 against QLC+ 5.3.0 built from that tag and run headless with `-w`. Every string below sits in the page's `PROTOCOL` block, so a change in QLC+ is a change in one place.

## Connection

- QLC+ started with web access: `qlcplus -w` (5.3: `qlcplus5 -w`). It listens on port 9999.
- Web socket: `ws://<host>:9999/qlcplusWS`.
- QLC+ does not check the `Origin` header, so a page served from another port (8080) or another computer can connect.
- QLC+ sends no CORS header, so a page from another port cannot *read* `http://<host>:9999/vc.json`. It can still *request* it (`fetch(…, {mode: "no-cors"})`), and the request is what matters (next section).
- Several clients at once (QLC+'s own web page, the stage page, a second tablet) work: QLC+ sends every push to every client.

## Switching the pushes on

QLC+ 5 connects a widget's signals to the web socket only when it has drawn that widget for a web client, that is when someone requests `/vc.json` (QLC+'s own web page does). Until then a cue list sends nothing, whoever moves it. Checked live: before `/vc.json`, `NEXT` gave only `FUNCTION|…` messages; after it, `CUE` and `CUE_STATE` came too.

The page therefore requests `/vc.json` when it connects and again every 60 seconds (QLC+ may have been restarted or loaded another project; on a big show the reply is about 55 kB). It also asks for the status of every list every 2 seconds, so even with no pushes the page is at most 2 seconds behind.

## Messages

Steps count from 0. −1 means no step.

| Direction | Message | Meaning |
|---|---|---|
| → | `QLC+API\|getWidgetStatus\|<id>` | Ask a widget's state |
| ← | `QLC+API\|getWidgetStatus\|<id>\|PLAY\|<n>` | Cue list playing step n |
| ← | `QLC+API\|getWidgetStatus\|<id>\|STOP` | Stopped or paused (no step number) |
| ← | `QLC+API\|getWidgetStatus\|` | No widget with that ID in the show QLC+ has open |
| ← | `QLC+API\|getWidgetStatus\|<id>\|0` | That ID is a widget, but not a cue list (a button gives 0, 127 or 255) |
| ← | `<id>\|CUE\|<n>` | The cue list moved to step n (pedal, mouse, another client) |
| ← | `<id>\|CUE_STATE\|<status>\|<n>\|<next>\|<side>\|<top>` | Status 0 stopped, 1 playing, 2 paused; the current and the next step; side fader level and which side is on top |
| ← | `FUNCTION\|<fid>\|Running` / `Stopped` | Any function started or stopped (ignored by the page) |
| → | `<id>\|PLAY`, `<id>\|STOP`, `<id>\|PREV`, `<id>\|NEXT` | Press the cue list's buttons |
| → | `<id>\|STEP\|<n>` | Select step n; see below |

### What one pedal press looks like

```
<< 4001|CUE|1
<< 4001|CUE_STATE|1|1|2|100|1
<< FUNCTION|2318|Stopped
<< FUNCTION|2319|Running
```

From the probe to the page showing the new step: 35 to 50 ms on one computer.

### Stop, and stop again

The first `STOP` stops the chaser and keeps the step selected (`CUE_STATE|0|1|2|…`): *Play* would start from it, and the page shows it with a dashed outline. A second `STOP` clears it (`CUE|-1`). `getWidgetStatus` says only `STOP` in both cases, so after a reconnect a stopped list shows no selected step until it moves.

### Why the page has no jump to a step

`<id>|STEP|<n>` sets the selected step but, while the chaser plays, does not change what plays: checked live, `STEP|5` reported step 5 while step 2 kept playing, and the next `PREV` went to step 1. Jumping would need `STOP`, `STEP|n`, `PLAY`, which goes through a stop on stage. The page offers *Previous* and *Next* only.

## Questions left for the Mac

- A cue list on a page of a multipage frame that is not shown: does it still report? (`/vc.json` covers every page, so it should.)
- The MIDI pedal and a real tablet over the computer's own Wi-Fi: under 300 ms?
- Two hours with the screen on: no drift.

`tools/stage_probe.html` answers them: open it in a browser next to QLC+, press the pedal, read the log.
