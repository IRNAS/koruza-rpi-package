#!/bin/bash

/usr/bin/rpdo pkg-config $* | sed 's/\/usr/\/rpxc\/sysroot\/usr/g'

