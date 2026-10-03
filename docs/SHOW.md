# Phone Booth Show

The booth runs one fixed sequence. Its looks and timings are live settings you change from the dashboard's **Show** tab while it runs. Code: `src/parade/show/`. Settings: `config/show.yaml` (written by the Show tab). Wiring to hardware: `show` in `config/default.yaml`.

## The cycle

```
ROTATING ──performer button──► ARMED ──index──┬─ index < "extra revolution" window after the button ─► EXTRA REV ──index──► STOPPED
                                               └─ otherwise ──────────────────────────────────────────────────────────────► STOPPED
STOPPED ──"stop for" time──► ROTATING (performer flag cleared)
```

| | Rotating / Armed | Extra revolution | Stopped |
|---|---|---|---|
| Motor | on | on | **off** |
| Sparks | on/off bursts | same | **off** |
| Fog | periodic | **boost (100 / 100)** | **boost** until "keep going after the stop" (10 s), then periodic (optional) |
| Exterior | its "while turning" effect (default off) | fog look | fog look **while the boost runs**, or for **the whole stop** ("During the stop" setting) |
| Interior (`top` group) | lightning: each fixture flashes on its own | same | dark at once, then **pulses for the whole stop**; at "fade up after" (3 s) the pulse fades up to full |
| NeoPixel sides 1–4 | each side's own effect | same | same as interior |

- The **fog boost** starts at the first index pass after the performer button, including the one that triggers the extra revolution.
- **Exterior lights** have two looks. The *fog look* (Exterior: fog boost & stop) runs during the fog boost, and optionally for the whole stop. The *while turning* look (default off) runs the rest of the time the booth turns. The master switch turns both off.
- The button does nothing while stopped or during the extra revolution.

## Running it

- **RUNNING** starts the booth turning immediately. **Leaving RUNNING** (PAUSED, SAFE, E-STOP, FAULT) blacks out the show's lights and sets sparks and fog to zero. The SafetyMonitor turns the motor off. Going back to RUNNING starts again from ROTATING, with the performer flag cleared.
- **Index watchdog:** while the motor is on, an index pass must arrive within *factor* × the measured revolution time (default 2.5×), or within 60 s before a revolution has been measured. If none arrives (stuck switch, cut wire, jammed booth), the motor goes off and the system goes to **FAULT**. Check the booth, then go SAFE to reset.
- The Show tab's status card shows the phase, the time left in a stop, the motor, sparks, fog, boost, the measured revolution time and the watchdog countdown. The OLED's show page shows the phase too, e.g. `STOPPED 12/30s`.
- Every setting is saved as soon as it changes. Anyone on the WiFi can change it. Another device viewing the Show tab sees the change after a reload.

## Spark powder

The Show tab's **Spark Powder** card counts spark-on time since the hopper was last refilled. It's saved across restarts in `config/spark_usage.json`, which is not in git. Higher spark levels use more powder, so it also counts *level-weighted* spark-seconds (on time × level).

Calibrate once:
1. Fill and weigh the hopper. Enter the weight as **Hopper filled with**, and press **Hopper refilled**.
2. Run the show for a while, then weigh the hopper again.
3. Grams used ÷ the "level-weighted spark-s" tile = **grams per spark-second**. Enter it.

The card then estimates grams left, use per hour of turning, hours until empty, powder needed for the whole parade, and the gap between bursts that would make the hopper last the parade. Estimates assume the booth turns the whole time; stops use none.

## NeoPixel sides

`show.pixel_sides` in `config/default.yaml` lists which strip indices belong to each side (`start`, `count`, `reverse` for chase direction). The current split of the 50-pixel strip is a **placeholder** (13/12/13/12). Replace it with the real layout. Pixels outside every side stay off.

## Cues and the Builder

With `show.enabled: true`, cue files are loaded but not run, and the Builder tab is hidden. Set `show.enabled: false` to go back to cues.
