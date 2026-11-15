# camera-kiln

> **Parts:** the printers, boards, readers and other gear that go with this project are listed at [projects.die-hard.net/gear](https://projects.die-hard.net/gear) (Amazon affiliate links).

A [Kiln OS](https://github.com/djvalic/kiln-os) plugin for the Flashforge
AD5X that adds zMod's camera macros and camera hotplug:

> **Needs Kiln OS 1.0 (plugin API 1.6).** Version 2.0 uses Kiln's own
> root scripts and boot hooks for plugins. On Kiln v0.0.x, stay on the
> `main` branch (1.x, the `screen.conf` hook).
> Coming from 1.x? See "Moving from 1.x" below.

```
CAMERA_ON                               on, with the last settings
CAMERA_ON WIDTH=1920 HEIGHT=1080 FPS=15 settings are kept across reboots
CAMERA_OFF                              stays off across reboots
CAMERA_RESTART
CAMERA_STATUS                           root part, cameras, streams
```

Kiln OS already streams USB cameras: its `S64ad5x-camera` service runs
one ustreamer per UVC camera, behind nginx at `/webcam/`, `/webcam2/`, ...
(Fluidd and HelixScreen list them). This plugin doesn't replace that; it
adds:

- **The zMod macro names**, so habits and macros from zMod keep working.
  zMod's `VIDEO=`, `STREAMER=`, `FORMAT=` and `FS=` are accepted and
  ignored: every UVC camera is streamed, as MJPEG by ustreamer.
- **Hotplug.** Kiln looks for cameras only at boot, so a camera plugged
  in later stays dark until a reboot. With this plugin it starts within
  about 6 seconds, and an unplugged one is stopped.

Defaults (nothing saved yet): 1280x720 at 15 fps, Kiln's own defaults.

## Install

The plugin has a small root part (`root/`) that sets the cameras up and
watches for hotplug; Kiln asks before it runs anything as root. It isn't
in Kiln's plugin catalog yet, so clone it over SSH (Kiln's default
password is `root`):

```sh
cd /data/ad5x/plugins
su klipper -s /bin/sh -c 'git clone -b kiln-v1 https://github.com/DIEHARDave/camera-kiln.git camera'
```

Then in the console (Fluidd, HelixScreen or a macro):

```
ENABLE_PLUGIN NAME=camera ROOT=1
```

`ROOT=1` is your consent to run `root/install.sh` as root; read `root/`
first if you like. Kiln runs it, enables the plugin and restarts Klipper.
Run `CAMERA_STATUS` to check: it should say `Root part: v3` and
`Watcher: running`. When the root part is missing, outdated or its
watcher isn't running, the console shows a `KILN_Camera:` warning with
the command that fixes it.

## Updates

Fluidd > Settings > Software Updates lists `camera-kiln`. After an
update, `RESTART` Klipper: when `root/` changed, Kiln runs
`root/update.sh` by itself (you agreed to that with `ROOT=1`).

## Moving from 1.x

1.x installed its root part by hand (`sh install.sh` over SSH, a line in
`/data/ad5x/screen.conf`). After updating to 2.0 Kiln warns that the
plugin "got root scripts": run

```
DISABLE_PLUGIN NAME=camera
ENABLE_PLUGIN NAME=camera ROOT=1
```

`root/install.sh` removes the old `screen.conf` line,
`/data/ad5x/camera-hook.sh` and the old watcher, then starts the new one.
Your camera settings (in `variables.cfg`) stay.

## Renamed for Kiln OS 1.0

This repository was `KILN_Camera` until 2026-11-15; old links and clones keep
working (GitHub redirects them), and Moonraker switches an installed
copy to the new address by itself at its next update check.

Since v0.1.0-rc1, Kiln OS keeps names that start with `kiln_` or
`ad5x_` for itself and refuses plugins that use them. This plugin's
Klipper section and status object are now `camera_kiln` (was `kiln_camera`),
and its Software Updates entry is `camera-kiln` (was `kiln-camera`).

Nothing to do by hand: at the first start after the update, the plugin
renames `[kiln_camera]` in your config files (the `.cfg` files in the
config folder; a `.before-rename` copy of each changed file is kept),
uses the old settings for that start, and shows a red ⚠️🚨 line in the
console and a warning in Fluidd/Mainsail. Reboot the printer (or
`RESTART` Klipper) when you see it. If a file can't be changed, the
message says to rename the section by hand. Macros or dashboards that
read `printer.kiln_camera` need `printer.camera_kiln`.

## How it works

Kiln's system partition is read-only and Klipper can't run shell
commands. `S64ad5x-camera` (root) reads its settings from
`/data/ad5x/camera.conf` (`CAMERA`, `RESOLUTION`, `FPS`, checked, never
run). Kiln's plugin API 1.6 copies the plugin's `root/` to
`/data/ad5x/plugins-root/camera` (root-owned, so root never runs code from
the clone user `klipper` can change) and runs its scripts there:

- `install.sh` (at `ENABLE_PLUGIN ... ROOT=1`) and `update.sh` (after an
  update that changed `root/`) put the boot script `S50camera` into
  `/data/ad5x/plugins-root/init.d` and start it.
- `S50camera` runs at every boot, a minute or so after the touch screen
  (`S69ad5x-plugin-boot`), and stops the watcher at shutdown.
- `uninstall.sh` (at `DISABLE_PLUGIN` / `REMOVE_PLUGIN`) stops the watcher
  and removes the settings block from `camera.conf`.

At boot (and when `install.sh` runs it), `camera-hook.sh start`:

- reads the `camera_on`, `camera_resolution` and `camera_fps` variables
  that the macros save with `SAVE_VARIABLE` in Klipper's `variables.cfg`.
  The values are parsed and checked, never run: that file is writable by
  `klipper`. It writes them into a marked block at the end of
  `camera.conf` and restarts the cameras if the block changed.
- starts a watcher that checks every 3 seconds whether a camera was
  plugged in or out, or whether a `camera_*` variable changed
  (`CAMERA_RESTART` bumps `camera_restart`). If so, it updates the block
  and restarts the camera service. It logs to `/var/log/messages` with
  the tag `ad5x-camera`; the root scripts log to
  `/data/ad5x/kiln-log/plugins-root.log`.

Settings written in `camera.conf` by hand (`RESOLUTION_2=`, ...) still
work; keep them above the `# KILN_Camera settings` block. A setting saved
by a macro wins over the same one written by hand.

## Extra cameras listed (`camera1`, `camera2`)

Kiln's camera service now adds each camera to Moonraker by itself at
boot: the first as `Chamber/Bed`, the next ones as `Camera 2`, ... This
plugin doesn't add or change any webcam entries.

Older Kiln versions instead put `[webcam camera1]` (`/webcam/`) and
`[webcam camera2]` (`/webcam2/`) in `moonraker.conf`. Kiln only writes
that file when it's missing, so after an update those sections stay and
Fluidd lists the same camera twice, plus `camera2` as an error. Delete
both sections from `/home/klipper/printer_data/config/moonraker.conf` and
restart Moonraker.

## Uninstall

```
REMOVE_PLUGIN NAME=camera
```

(or `DISABLE_PLUGIN NAME=camera` to keep the clone). Kiln runs
`root/uninstall.sh` first: the watcher stops and the cameras go back to
`camera.conf`'s own settings. The `camera_*` variables stay in
`variables.cfg` but nothing reads them.

## License

GPLv3, like Klipper and Kiln OS.
