"""
A silly little daemon to control my PC with OpenRGB
"""

## FIXME: Profiles are broken in the client. I can load profiles using the command
#  and not the client/server. Good enough for now. I should file a bug report because
# working with remote profiles is broken. 

import asyncio
import dbus_next 
import subprocess
import os 
import psutil
import openrgb

from dbus_next.aio import MessageBus
from openrgb.utils import RGBColor, DeviceType


async def main():
    """Run the daemon. Block."""

    bus = await MessageBus(bus_type=dbus_next.constants.BusType.SYSTEM, negotiate_unix_fd=True).connect()
    introspection = await bus.introspect('org.freedesktop.login1', '/org/freedesktop/login1')
    obj = bus.get_proxy_object('org.freedesktop.login1', '/org/freedesktop/login1', introspection)
    manager = obj.get_interface('org.freedesktop.login1.Manager')

    infd = None

    async def inhibit_sleep():
        nonlocal infd
        infd = await manager.call_inhibit("sleep", "RGB", "Wait a sec while I turn off the lights...", "delay")

    openrgb_s = await asyncio.create_subprocess_shell(
        "./OpenRGB/openrgb -v --server --server-port 6742 --localconfig",
    )

    await asyncio.sleep(5)
    rgbclient = openrgb.OpenRGBClient()
    
    # Listen for sleep/run
    def on_sleep_run(sleep_not_run):
        nonlocal infd
        if sleep_not_run:
            print("Requested sleep state...")
            subprocess.run('./OpenRGB/openrgb --localconfig --noautoconnect -p sleeping', shell=True)
            os.close(infd)
            infd = None
        else:
            print("Requested run state...")
            subprocess.run('./OpenRGB/openrgb --localconfig --noautoconnect -p running', shell=True)
            if infd == None:
                asyncio.create_task(inhibit_sleep())

    on_sleep_run(False)
    manager.on_prepare_for_sleep(on_sleep_run)

    async def frame():
        avg = [0] * 20
        idx = 0
        motherboard = rgbclient.get_devices_by_name('ASUS ROG STRIX X670E-E GAMING WIFI')[0]        
        while True:
            avg[idx] = psutil.cpu_percent() 
            idx = (idx + 1) % len(avg)
            cpu_percent = sum(avg) / len(avg) 

            # temperature == busy 
            #hue = 236 - round(2.36 * cpu_percent)
            # sat = 100 
            # val = 100 
            
            # red to white! 
            hue = int(0 + (cpu_percent / 15))
            sat = int(min(100, 190 - cpu_percent))
            val = int(min(100, 10 + cpu_percent))

            motherboard.set_color(RGBColor.fromHSV(hue, sat, val), fast=True)
            await asyncio.sleep(0.1)

    asyncio.create_task(frame())

    await openrgb_s.wait()
    exit(openrgb_s.returncode)


if __name__ == '__main__':
    asyncio.run(main())