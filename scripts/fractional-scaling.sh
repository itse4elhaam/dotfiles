#!/bin/bash
# usage: ./scaling.sh on   --> enable 125% zoom
#        ./scaling.sh off  --> disable 100% zoom

if [ "$1" == "on" ]; then
    echo "Enabling fractional scaling and setting zoom to 125%"
    gsettings set org.gnome.mutter experimental-features "['scale-monitor-framebuffer']"
    gsettings set org.gnome.desktop.interface text-scaling-factor 1.25
elif [ "$1" == "off" ]; then
    echo "Disabling fractional scaling and setting zoom to 100%"
    gsettings set org.gnome.mutter experimental-features "[]"
    gsettings set org.gnome.desktop.interface text-scaling-factor 1.0
else
    echo "Usage: $0 {on|off}"
    exit 1
fi
