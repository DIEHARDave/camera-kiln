# camera-kiln: state of the root part (root/, Kiln OS plugin API 1.6)
# that CAMERA_ON / CAMERA_OFF / CAMERA_RESTART (plugin.cfg) rely on,
# CAMERA_STATUS, and a console warning when it is missing, outdated or
# its watcher isn't running.
#
# Klipper runs as user klipper: this module only reads files. The
# cameras are started by Kiln's S64ad5x-camera (root) from
# /data/ad5x/camera.conf; root/camera-hook.sh, run as root from root's
# copy by the boot script S50camera, writes the settings there.
#
# Copyright (C) 2026  DIEHARDave
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
import os
import re

HOOK = "/data/ad5x/plugins-root/camera/camera-hook.sh"
BOOT = "/data/ad5x/plugins-root/init.d/S50camera"
OLD_HOOK = "/data/ad5x/camera-hook.sh"
V4L = "/sys/class/video4linux"
VERSION_RE = re.compile(r"^CAM_HOOK_VERSION=(\d+)", re.M)
CHECK_INTERVAL = 30.
ENABLE = "ENABLE_PLUGIN NAME=camera ROOT=1"
# Kiln runs boot scripts after S99ad5x-booted plus 15 s, a minute or two
# after Klipper is ready: no watcher before that is not a problem yet
BOOT_GRACE = 300.

def uptime():
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return BOOT_GRACE + 1.

def hook_version(path):
    """CAM_HOOK_VERSION of a hook file; None if unreadable, 0 if absent."""
    try:
        with open(path) as f:
            m = VERSION_RE.search(f.read())
    except OSError:
        return None
    return int(m.group(1)) if m else 0

def processes():
    """Command lines (argument lists) of all processes. Kiln runs with
    umask 077, so root's pid files can't be read; /proc cmdlines can."""
    out = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % (pid,), "rb") as f:
                args = f.read().split(b"\0")
        except OSError:
            continue
        out.append([a.decode("utf-8", "replace") for a in args if a])
    return out

def watcher_running(procs):
    return any(HOOK in args and "watch" in args for args in procs)

def stream_count(procs):
    return len([args for args in procs
                if args and os.path.basename(args[0]) == "ustreamer"])

def cameras():
    """Names of the UVC capture nodes (index 0), like S64ad5x-camera."""
    out = []
    try:
        nodes = sorted(os.listdir(V4L))
    except OSError:
        return out
    for node in nodes:
        d = os.path.join(V4L, node)
        try:
            with open(os.path.join(d, "index")) as f:
                if f.read().strip() != "0":
                    continue
            driver = os.path.basename(os.path.realpath(
                os.path.join(d, "device", "driver")))
            with open(os.path.join(d, "name")) as f:
                name = f.read().strip()
        except OSError:
            continue
        if driver == "uvcvideo":
            out.append("%s (%s)" % (node, name))
    return out

class KilnCamera:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        plugin_dir = os.path.dirname(os.path.dirname(
            os.path.realpath(__file__)))
        self.plugin_hook = os.path.join(plugin_dir, "root", "camera-hook.sh")
        self.problems = []
        self.printer.register_event_handler("klippy:ready", self._ready)
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command("CAMERA_STATUS", self.cmd_CAMERA_STATUS,
                               desc="Camera hook, cameras and streams")
    def _check(self):
        problems = []
        installed = hook_version(HOOK)
        wanted = hook_version(self.plugin_hook) or 0
        if installed is None or not os.path.exists(BOOT):
            problems.append("camera root part not installed: run "
                            "DISABLE_PLUGIN NAME=camera, then " + ENABLE)
        elif installed < wanted:
            problems.append("camera root part outdated (v%d, plugin has v%d):"
                            " run %s" % (installed, wanted, ENABLE))
        elif (not watcher_running(processes())
              and uptime() > BOOT_GRACE):
            problems.append("camera watcher not running: reboot, or run "
                            + ENABLE)
        if os.path.exists(OLD_HOOK):
            problems.append("old camera hook %s still there: run %s"
                            % (OLD_HOOK, ENABLE))
        self.problems = problems
        return problems
    def _ready(self):
        if self._check():
            msg = "KILN_Camera: " + "; ".join(self.problems)
            logging.warning(msg)
            self.printer.lookup_object('gcode').respond_info("!! " + msg)
        self.reactor.register_timer(self._timer,
                                    self.reactor.monotonic() + CHECK_INTERVAL)
    def _timer(self, eventtime):
        self._check()
        return eventtime + CHECK_INTERVAL
    def get_status(self, eventtime):
        return {'problems': list(self.problems)}
    def cmd_CAMERA_STATUS(self, gcmd):
        self._check()
        sv = self.printer.lookup_object('save_variables', None)
        saved = sv.allVariables if sv is not None else {}
        cams = cameras()
        procs = processes()
        streams = stream_count(procs)
        installed = hook_version(HOOK)
        lines = [
            "Root part: %s" % ("v%d" % installed if installed is not None
                               else "not installed"),
            "Watcher: %s" % ("running" if watcher_running(procs)
                             else "not running"),
            "Settings: %s, %s at %s fps" % (
                "off" if saved.get('camera_on', 1) in (0, False) else "on",
                saved.get('camera_resolution', "1280x720"),
                saved.get('camera_fps', 15)),
            "Cameras: %s" % (", ".join(cams) or "none"),
            "Streams running: %d (/webcam/%s)" % (
                streams, ", /webcam2/ ..." if streams > 1 else "")]
        lines += ["!! " + p for p in self.problems]
        gcmd.respond_info("\n".join(lines))

# Kiln OS 1.0 keeps kiln_ names for itself (v0.1.0-rc1 on), so this plugin's
# sections were renamed. A user config still naming the old ones is fixed
# here at the first start that sees them: the old options are used for this
# start, the section headers in the config folder's .cfg files are renamed
# (a .before-rename copy of each changed file is kept), and a red console
# line plus a warning in Fluidd/Mainsail ask for a reboot.
LEGACY_PLUGIN = 'KILN_Camera'
LEGACY_SECTIONS = {'kiln_camera': 'camera_kiln'}


def _renamed(section):
    """The new name for an old section name ("kiln_x" or "kiln_x name"),
    None for any other section."""
    head, _, rest = section.strip().partition(' ')
    new = LEGACY_SECTIONS.get(head.lower())
    if new is None:
        return None
    rest = rest.strip()
    return new + (' ' + rest if rest else '')


def _rename_in_files(cfg_file):
    """Renames the old section headers in the .cfg files of cfg_file's
    folder (and below; links to folders are not followed). Returns the
    changed files (relative paths) and the errors."""
    import os, re, shutil
    olds = sorted(LEGACY_SECTIONS, key=len, reverse=True)
    pat = re.compile(r'^(\s*(?:#\*#\s*)?\[\s*)(%s)((?:\s+[^\]]*?)?)(\s*\])'
                     % '|'.join(map(re.escape, olds)), re.I | re.M)
    def sub(m):
        return m.group(1) + LEGACY_SECTIONS[m.group(2).lower()] + m.group(3) + m.group(4)
    root = os.path.dirname(os.path.abspath(cfg_file))
    changed, errors = [], []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for name in files:
            if not name.endswith('.cfg'):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, encoding='utf-8', errors='surrogateescape',
                          newline='') as f:
                    text = f.read()
                new_text = pat.sub(sub, text)
                if new_text == text:
                    continue
                backup = path + '.before-rename'
                if not os.path.exists(backup):
                    shutil.copy2(path, backup)
                tmp = path + '.renaming'
                with open(tmp, 'w', encoding='utf-8', errors='surrogateescape',
                          newline='') as f:
                    f.write(new_text)
                shutil.copymode(path, tmp)
                os.replace(tmp, path)
                changed.append(os.path.relpath(path, root))
            except OSError as e:
                errors.append("%s: %s" % (path, e))
    return changed, errors


def migrate_legacy_sections(config):
    import logging
    fc = config.fileconfig
    found = [(s, _renamed(s)) for s in fc.sections() if _renamed(s)]
    if not found:
        return
    printer = config.get_printer()
    me = config.get_name().lower()
    for old, new in found:
        legacy = config.getsection(old)
        options = fc.options(old)
        for opt in options:
            if new.lower() == me:
                fc.set(config.get_name(), opt, fc.get(old, opt))
            legacy.get(opt)  # marks it used: no "not a valid section" stop
        if not options:
            config.access_tracking[(old.lower(), '__renamed__')] = 1
    pairs = ", ".join("[%s] \u2192 [%s]" % p for p in found)
    try:
        cfg_file = printer.get_start_args().get('config_file')
    except Exception:
        cfg_file = None
    changed, errors = _rename_in_files(cfg_file) if cfg_file else ([], [])
    if changed and not errors:
        msg = ("\u26a0\ufe0f\U0001f6a8 %s: Kiln OS 1.0 keeps kiln_ names for "
               "itself, so these sections were RENAMED in %s: %s. REBOOT the "
               "printer now (or RESTART Klipper) to use the new names. "
               "\U0001f6a8\u26a0\ufe0f" % (LEGACY_PLUGIN, ", ".join(changed), pairs))
    else:
        msg = ("\u26a0\ufe0f\U0001f6a8 %s: Kiln OS 1.0 keeps kiln_ names for "
               "itself. Rename these sections in your config BY HAND: %s, then "
               "REBOOT the printer (or RESTART Klipper).%s \U0001f6a8\u26a0\ufe0f"
               % (LEGACY_PLUGIN, pairs,
                  (" Could not change: " + "; ".join(errors)) if errors else ""))
    logging.warning(msg)
    try:
        printer.lookup_object('configfile').runtime_warning(msg)
    except Exception:
        pass
    def say(eventtime):
        try:
            printer.lookup_object('gcode').respond_raw('!! ' + msg)
        except Exception:
            logging.exception("%s: rename notice", LEGACY_PLUGIN)
        return printer.get_reactor().NEVER
    def ready():
        # Moonraker subscribes to the console a little after klippy:ready, so
        # a line sent at once only reaches klippy.log: send it twice, later
        reactor = printer.get_reactor()
        now = reactor.monotonic()
        for delay in (15., 60.):
            reactor.register_timer(say, now + delay)
    try:
        printer.register_event_handler('klippy:ready', ready)
    except Exception:
        pass


def load_config(config):
    migrate_legacy_sections(config)
    return KilnCamera(config)
