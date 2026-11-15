#!/bin/sh
# camera-kiln: undo install.sh. Kiln runs it (root's copy) at
# DISABLE_PLUGIN / REMOVE_PLUGIN, then deletes root's copy and the boot
# script. The cameras go back to camera.conf's own settings.
CAM_CONF=/data/ad5x/camera.conf

/bin/sh ./camera-hook.sh stop
if [ -f $CAM_CONF ]; then
	sed -i -e '/^# KILN_Camera settings, /,/^# KILN_Camera end$/d' $CAM_CONF
	grep -qv '^[[:space:]]*\(#.*\)\{0,1\}$' $CAM_CONF || rm -f $CAM_CONF
fi
/etc/init.d/S64ad5x-camera restart
echo "camera-kiln: root part removed"
exit 0
