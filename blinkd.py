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

from dbus_next.aio import MessageBus
from openrgb import OpenRGBClient


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

    #openrgb_s = await asyncio.create_subprocess_shell(
    #    "./OpenRGB/openrgb -v --server --server-port 6742 --localconfig",
    #)

    #await asyncio.sleep(2)
    #openrgb = OpenRGBClient()
    
    # Listen for sleep/run
    def on_sleep_run(sleep_not_run):
        nonlocal infd
        if sleep_not_run:
            print("Requested sleep state...")
            #openrgb.load_profile('sleep')
            subprocess.run('./OpenRGB/openrgb --localconfig -p sleeping', shell=True)
            os.close(infd)
            infd = None
        else:
            print("Requested run state...")
            #openrgb.load_profile('run')
            subprocess.run('./OpenRGB/openrgb --localconfig -p running', shell=True)
            if infd == None:
                asyncio.create_task(inhibit_sleep())

    on_sleep_run(False)
    manager.on_prepare_for_sleep(on_sleep_run)

    # Remove me when the bug is fixed.
    while True:
        await asyncio.sleep(10)

    await openrgb_s.wait()
    exit(openrgb_s.returncode)


if __name__ == '__main__':
    asyncio.run(main())