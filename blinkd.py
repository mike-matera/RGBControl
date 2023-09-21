"""
A silly little daemon to control my PC with OpenRGB
"""

## FIXME: Profiles are broken in the client. I can load profiles using the command
#  and not the client/server. Good enough for now. I should file a bug report because
# working with remote profiles is broken. 

import asyncio
import dbus_next 
import os 
import psutil
import openrgb
import signal
import subprocess

from dbus_next.aio import MessageBus
from openrgb.utils import RGBColor, DeviceType


async def main():
    """Run the daemon. Block."""

    rgbclient = None 
    infd = None
    openrgb_s = None 
    do_anim = True

    def do_stop():
        nonlocal rgbclient, infd, openrgb_s, do_anim
        print("Receieved signal, stopping LED services.")
        do_anim = False
        if rgbclient is not None:
            rgbclient.disconnect()
        if openrgb_s is not None:
            openrgb_s.terminate()
        if infd is not None:
            os.close(infd)

    asyncio.get_running_loop().add_signal_handler(signal.SIGINT, do_stop)
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, do_stop)

    bus = await MessageBus(bus_type=dbus_next.constants.BusType.SYSTEM, negotiate_unix_fd=True).connect()
    introspection = await bus.introspect('org.freedesktop.login1', '/org/freedesktop/login1')
    obj = bus.get_proxy_object('org.freedesktop.login1', '/org/freedesktop/login1', introspection)
    manager = obj.get_interface('org.freedesktop.login1.Manager')

    async def inhibit_sleep():
        nonlocal infd
        infd = await manager.call_inhibit("sleep", "RGB", "Wait a sec while I turn off the lights...", "delay")

    openrgb_s = await asyncio.create_subprocess_shell(
        "exec ./OpenRGB/openrgb -v --server --server-port 6742 --localconfig",
        stdin=asyncio.subprocess.DEVNULL,
        start_new_session=True, # Don't listen to my signals
    )

    await asyncio.sleep(5)
    rgbclient = openrgb.OpenRGBClient()

    # Listen for sleep/run
    def on_sleep_run(sleep_not_run):
        nonlocal infd
        if sleep_not_run:
            print("Requested sleep state...")
            subprocess.run('exec ./OpenRGB/openrgb --localconfig --noautoconnect -p sleeping', shell=True)
            os.close(infd)
            infd = None
        else:
            print("Requested run state...")
            subprocess.run('exec ./OpenRGB/openrgb --localconfig --noautoconnect -p running', shell=True)
            if infd == None:
                asyncio.create_task(inhibit_sleep())
        
    on_sleep_run(False)
    manager.on_prepare_for_sleep(on_sleep_run)

    async def frame():

        # Thanks: http://www.vendian.org/mncharity/dir3/blackbody/
        k_to_rgb = {
            1000: "#ff3800", 
            1200: "#ff5300", 
            1400: "#ff6500", 
            1600: "#ff7300", 
            1800: "#ff7e00", 
            2000: "#ff8912", 
            2200: "#ff932c", 
            2400: "#ff9d3f", 
            2600: "#ffa54f", 
            2800: "#ffad5e", 
            3000: "#ffb46b", 
            3200: "#ffbb78", 
            3400: "#ffc184", 
            3600: "#ffc78f", 
            3800: "#ffcc99", 
            4000: "#ffd1a3", 
            4200: "#ffd5ad", 
            4400: "#ffd9b6", 
            4600: "#ffddbe", 
            4800: "#ffe1c6", 
            5000: "#ffe4ce", 
            5200: "#ffe8d5", 
            5400: "#ffebdc", 
            5600: "#ffeee3", 
            5800: "#fff0e9", 
            6000: "#fff3ef", 
            6200: "#fff5f5", 
            6400: "#fff8fb", 
            6600: "#fef9ff", 
            6800: "#f9f6ff", 
            7000: "#f5f3ff", 
            7200: "#f0f1ff", 
            7400: "#edefff", 
            7600: "#e9edff", 
            7800: "#e6ebff", 
        }
        
        def to_rgb(st):
            color = int(st[1:], base=16)
            return (color & 0xff0000) >> 16, (color & 0xff00) >> 8, (color & 0xff) 

        def interp(a, b, s=0.5):
            a = to_rgb(a)
            b = to_rgb(b)
            return (
                round(a[0] + s * (b[0] - a[0])),
                round(a[1] + s * (b[1] - a[1])),
                round(a[2] + s * (b[2] - a[2])),
            )

        avg = [0] * 60
        idx = 0
        motherboard = rgbclient.get_devices_by_name('ASUS ROG STRIX X670E-E GAMING WIFI')[0]        
        nonlocal do_anim
        while do_anim:
            avg[idx] = psutil.cpu_percent() 
            idx = (idx + 1) % len(avg)
            cpu_percent = round(sum(avg) / len(avg)) 

            if cpu_percent <= 25:
                # Warm up to orange
                color = interp("#770000", k_to_rgb[1000], cpu_percent / 25)
            else:
                # Find a color
                color = "#ff3800"
                last = color
                for k in sorted(k_to_rgb):
                    if (cpu_percent - 25) <= ((k / 200) / len(k_to_rgb)) * 100:
                        color = k_to_rgb[k]
                        break
                    last = k_to_rgb[k]
                color = interp(last, color)

            #print("DEBUG:", cpu_percent, color)
            motherboard.set_color(RGBColor(red=color[0], green=color[1], blue=color[2]), fast=True)
            await asyncio.sleep(0.1)
        print("Finishing animation loop.")

    asyncio.create_task(frame())

    await openrgb_s.wait()
    print("OpenRGB exited with value:", openrgb_s.returncode)
    exit(openrgb_s.returncode)


if __name__ == '__main__':
    asyncio.run(main())