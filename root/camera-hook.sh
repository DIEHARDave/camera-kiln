#!/bin/sh
#####################################################################
# camera-kiln root part: camera settings + hotplug for Kiln OS (AD5X)
#
# Kiln OS plugin API 1.6 runs it as root from root's copy of the
# plugin's root/ folder (/data/ad5x/plugins-root/camera), never from the
# clone user klipper owns:
#   camera-hook.sh start   boot script S50camera (and install.sh):
#                          writes the settings CAMERA_ON / CAMERA_OFF
#                          keep in Klipper's variables.cfg into a marked
#                          block at the end of /data/ad5x/camera.conf, as
#                          the KEY=value lines Kiln reads, restarts the
#                          cameras if the block changed, starts the watcher
#   camera-hook.sh stop    stops the watcher
#   camera-hook.sh watch   the watcher: the same, and a camera service
#                          restart when a camera is plugged in or out or a
#                          camera_* variable changes (CAMERA_RESTART bumps
#                          camera_restart). Kiln itself scans only at boot.
# variables.cfg is writable by user klipper: it is parsed and checked,
# never sourced.
#####################################################################

# Bump when this file changes: CAMERA_STATUS compares it with root's
# copy (Kiln runs update.sh after a git update, so they should match)
CAM_HOOK_VERSION=3

CAM_CONF=/data/ad5x/camera.conf
CAM_BEGIN="# KILN_Camera settings, from CAMERA_ON and CAMERA_OFF (the hook rewrites them)"
CAM_END="# KILN_Camera end"
CAM_VARS=/home/klipper/printer_data/config/variables.cfg
CAM_HOOK=/data/ad5x/plugins-root/camera/camera-hook.sh
CAM_WATCH_PID=/run/ad5x-camera-watch.pid
CAM_SERVICE=/etc/init.d/S64ad5x-camera

# cam_var NAME: a save_variables value, quotes stripped
cam_var() {
	awk -F' = ' -v n="$1" '$1 == n {
		v = $2; gsub(/^["\047]|["\047]$/, "", v); print v; exit
	}' $CAM_VARS 2>/dev/null
}

# What the watcher compares: video nodes present + the camera_* variables
cam_state() {
	ls -d /sys/class/video4linux/video* 2>/dev/null | tr '\n' ' '
	grep '^camera_' $CAM_VARS 2>/dev/null
}

# cam_settings: the KEY=value lines for camera.conf, checked like Kiln
# does (a value that isn't valid is left out: Kiln's default applies)
cam_settings() {
	cam_v=$(cam_var camera_on)
	case "$cam_v" in 0|False) echo CAMERA=off ;; 1|True) echo CAMERA=on ;; esac
	cam_v=$(cam_var camera_resolution)
	echo "$cam_v" | grep -qx '[0-9]\{3,4\}x[0-9]\{3,4\}' && echo "RESOLUTION=$cam_v"
	cam_v=$(cam_var camera_fps)
	echo "$cam_v" | grep -qx '[1-9][0-9]\{0,1\}' && [ "$cam_v" -le 60 ] && echo "FPS=$cam_v"
}

# cam_write: camera.conf with our block brought up to date (hand-written
# lines kept; ours last, so they win). True when the file changed. Kiln
# reads it only if owned by root and not writable by group or others.
cam_write() {
	cam_new=$CAM_CONF.kiln-camera
	{
		[ -f $CAM_CONF ] && sed -e "/^$CAM_BEGIN\$/,/^$CAM_END\$/d" $CAM_CONF
		cam_s=$(cam_settings)
		[ -n "$cam_s" ] && printf '%s\n%s\n%s\n' "$CAM_BEGIN" "$cam_s" "$CAM_END"
	} > $cam_new
	if cmp -s $cam_new $CAM_CONF 2>/dev/null ||
	   { [ ! -f $CAM_CONF ] && [ ! -s $cam_new ]; }; then
		rm -f $cam_new
		return 1
	fi
	chown root:root $cam_new
	chmod 644 $cam_new
	mv $cam_new $CAM_CONF
	return 0
}

cam_restart() {
	$CAM_SERVICE restart 2>&1 | logger -t ad5x-camera
}

cam_watch() {
	last=$(cam_state)
	while sleep 3; do
		[ "$(cam_state)" = "$last" ] && continue
		# let a camera finish enumerating (two video nodes appear)
		sleep 3
		last=$(cam_state)
		logger -t ad5x-camera "change seen, restarting cameras"
		cam_write
		cam_restart
	done
}

cam_running() {
	[ -f $CAM_WATCH_PID ] && kill -0 "$(cat $CAM_WATCH_PID)" 2>/dev/null
}

case "$1" in
watch)
	cam_watch
	;;
stop)
	start-stop-daemon -K -q -p $CAM_WATCH_PID 2>/dev/null
	rm -f $CAM_WATCH_PID
	;;
start)
	# S64ad5x-camera has already started the cameras from camera.conf:
	# restart them only if our block changed
	if cam_write; then
		logger -t ad5x-camera "settings changed, restarting cameras"
		cam_restart
	fi
	cam_running ||
		start-stop-daemon -S -b -m -p $CAM_WATCH_PID -x /bin/sh -- $CAM_HOOK watch
	;;
*)
	echo "usage: $0 start|stop|watch"
	exit 1
	;;
esac
exit 0
