# Hardware

Control-box wiring: [WIRING_GUIDE.md](WIRING_GUIDE.md) (step by step) · [HARDWARE_SETUP_CHECKLIST.md](HARDWARE_SETUP_CHECKLIST.md) (background, power, open questions) · [BOM.md](BOM.md) (parts) · [SAFETY.md](SAFETY.md).

## Controller

Raspberry Pi 3 Model B, Raspberry Pi OS (Debian 13), powered from the ALITOVE 5V 60A supply. GPIO via `lgpio` on `/dev/gpiochip0`; NeoPixels via `spidev` on `/dev/spidev0.0`.

## Pin map (BCM)

| GPIO | Header pin | Use | Wiring | Config |
|---|---|---|---|---|
| 17 | 11 | Tabletop index microswitch (V-153-1C25) | C + **NC** to GND, pull-up + external 2.2kΩ to 3.3V | `rotation_index`, `active_low: false` |
| 27 | 13 | Performer ready button | **NO** to GND, pull-up | `performer_button`, `active_low: true` |
| 22 | 15 | E-stop monitor contact (NC #2, ZBE102) | **NC** to GND, pull-up | `estop_monitor`, `active_low: false`, `safety.estop_pin` |
| 18 | 12 | Relay board IN (HLS8L 5V, high-trigger) → contactor coil | → relay board IN | `phone_booth_rotation`, `active_low: false` |
| 10 | 19 | NeoPixel data (SPI0 MOSI) | → Adafruit Pixel Shifter → 330Ω → DIN | `main_strip`, `pin: 10` |
| 8, 9, 11 | 24, 21, 23 | Reserved by SPI0 | do not use | — |

Rule of thumb for inputs: wire **NO** when a broken wire should mean "nothing happened" (performer button). Wire **NC** when a broken wire should mean "stop" (index, e-stop).

## Drivers

`config/default.yaml` → `hardware`: `gpio_driver`, `relay_driver`, `pixel_driver` are each `simulated` or `rpi` and can be switched independently. `gpio_chip` selects `/dev/gpiochipN` (0 on a Pi 3).

## Bench tool

`.venv/bin/parade-hwcheck inputs | relay [ID] [--seconds N] | pixels test | pixels color R G B`. Uses the real drivers and the config. Stop the service first. The relay check honours the e-stop monitor.
