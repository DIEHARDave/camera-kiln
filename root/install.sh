#!/bin/sh
# camera-kiln: root's part, Kiln OS plugin API 1.6. Kiln runs it as root
# from /data/ad5x/plugins-root/camera (root's copy of root/) at
#   ENABLE_PLUGIN NAME=camera ROOT=1
# and, as update.sh, after each update that changes root/.
#  1. removes what camera-kiln before 2.0 installed by hand: the line in
#     /data/ad5x/screen.conf, /data/ad5x/camera-hook.sh, the old watcher,
#     the "stat" shim in /run
#  2. puts the boot script S50camera in place and runs it: settings into
#     camera.conf, cameras restarted if they changed, watcher started
set -e
ROOTDIR=/data/ad5x/plugins-root
OLD_HOOK=/data/ad5x/camera-hook.sh
SCREEN=/data/ad5x/screen.conf
CAM_CONF=/data/ad5x/camera.conf
WATCH_PID=/run/ad5x-camera-watch.pid

# the watcher (old or new) runs the old code: stop it, the hook starts
# the new one
start-stop-daemon -K -q -p $WATCH_PID 2>/dev/null || true
rm -f $WATCH_PID

for CONF in $SCREEN $CAM_CONF; do
	grep -qxF ". $OLD_HOOK" $CONF 2>/dev/null || continue
	sed -i -e '/^# KILN_Camera plugin/d' -e "\|^\. $OLD_HOOK\$|d" $CONF
	echo "removed the old hook line from $CONF"
	# nothing left but comments and blank lines: it was ours
	grep -qv '^[[:space:]]*\(#.*\)\{0,1\}$' $CONF || rm -f $CONF
done
rm -f $OLD_HOOK
rm -rf /run/kiln-camera-bin

mkdir -p $ROOTDIR/init.d
cp S50camera $ROOTDIR/init.d/S50camera.new
chmod 755 $ROOTDIR/init.d/S50camera.new
mv $ROOTDIR/init.d/S50camera.new $ROOTDIR/init.d/S50camera
$ROOTDIR/init.d/S50camera start
echo "camera-kiln: boot script installed, watcher started"
