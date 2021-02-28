#!/bin/sh

DISK=$1

if case "${DISK}" in /dev/sd*) ;; *) false;; esac; then
    
    /sbin/parted -a optimal "${DISK}" --script -- mklabel msdos mkpart primary fat32 0% 100%
    exit $?
fi

exit 1
