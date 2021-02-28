#!/usr/bin/env python3
#
# Shreddy2 - The Raspberry Pi storage scrub station for USB thumb drives.
#
# -----------------------------------------------------------------------------
# Copyright (c) 2021 Martin Schobert, Pentagrid AG
#
# All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
#  ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#  The views and conclusions contained in the software and documentation are those
#  of the authors and should not be interpreted as representing official policies,
#  either expressed or implied, of the project.
#
#  NON-MILITARY-USAGE CLAUSE
#  Redistribution and use in source and binary form for military use and
#  military research is not permitted. Infringement of these clauses may
#  result in publishing the source code of the utilizing applications and
#  libraries to the public. As this software is developed, tested and
#  reviewed by *international* volunteers, this clause shall not be refused
#  due to the matter of *national* security concerns.
# -----------------------------------------------------------------------------

import pyudev
import subprocess
import threading
import socketserver
import time
import os
import string
from timeit import default_timer as timer

from enum import Enum


# TCP server port to use (using None disables the server)
port = 2342
# The host/IP address to bind the server
host = ""

# log
last_devices = []

# busylight handler
bl_handler = None

# -------------------------------------------------------------------------
# Device
# -------------------------------------------------------------------------


class DeviceStatus(Enum):
    NONE = 0  # off
    REMOVED = 1  # off
    DONE = 2  # green
    INSERTED = 3  # yellow
    RUNNING = 4  # red
    ERROR = 5  # red - blink

    def __lt__(self, other):
        # https://stackoverflow.com/questions/39268052/how-to-compare-enums-in-python/39269589
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


class Device:
    """
    We keep some information about the device under shred in the Device class.
    """

    def __init__(self, device_path, model):
        self.device_path = device_path
        self.model = "".join(filter(lambda x: x in string.printable, model))
        self.status = DeviceStatus.NONE
        self.error_msg = None
        self.start = timer()

    def get_path(self):
        return self.device_path

    def get_model(self):
        return self.model

    def get_model(self):
        return self.model

    def set_status(self, status, message):
        self.status = status
        self.message = message

    def set_error(self, message):
        self.message = message
        self.status = DeviceStatus.ERROR

    def has_error(self):
        return self.status == DeviceStatus.ERROR

    def get_status(self):
        return self.status

    def get_status_as_str(self):
        if self.status == DeviceStatus.REMOVED:
            return "Removed"

        if self.status == DeviceStatus.DONE:
            return "Done"

        if self.status == DeviceStatus.INSERTED:
            return "Inserted"

        if self.status == DeviceStatus.RUNNING:
            return self.message

        if self.status == DeviceStatus.ERROR:
            return f"Error ({self.message})"

        return "None"


# -------------------------------------------------------------------------
# Output part
# -------------------------------------------------------------------------


class BusylightHandler(threading.Thread):
    def __init__(self, busylight):
        self.bl = busylight
        self.states = {}
        self.event = threading.Event()

        if self.bl:
            self.bl.keep_alive()

            threading.Thread.__init__(self)
            self.start()

    def set_status(self, medium, state):
        self.states[medium] = state
        self.event.set()

    def run(self):

        max_level = DeviceStatus.NONE

        while True:

            self.event.wait(None if max_level != DeviceStatus.ERROR else 2)
            self.event.clear()

            max_level = DeviceStatus.NONE
            for m in self.states:
                if self.states[m] > max_level:
                    max_level = self.states[m]

            print(max_level)
            if self.bl:
                if max_level == DeviceStatus.NONE:
                    color = (0, 0, 0)
                elif max_level == DeviceStatus.REMOVED:
                    color = (0, 0, 0)
                elif max_level == DeviceStatus.INSERTED:
                    color = (100, 100, 0)
                elif max_level == DeviceStatus.RUNNING:
                    color = (100, 0, 0)
                elif max_level == DeviceStatus.DONE:
                    color = (0, 100, 0)

                if max_level == DeviceStatus.ERROR:
                    self.bl.blink(rgb=(255, 0, 0), interval=0.5, count=10)
                else:
                    self.bl.set_rgb(color)
                    self.bl.send()


class ConnectionHandler(socketserver.StreamRequestHandler):

    """
    The ConnectionHandler class is our interface to show the shredding status of current and past attached devices.
    """

    # A few color definitions
    clear_screen = "\x1b[2J\x1b[1;1H"
    off = "\x1b[0m"
    red = "\x1b[31m"
    green = "\x1b[32m"
    cyan = "\x1b[36m"
    white = "\x1b[37m"
    yellow = "\x1b[33m"
    mangenta = "\x1b[35m"

    version_col = red
    logo_col = yellow

    def _render_page(self, enable_colors=True):
        """
        Function to render the info screen.
        """

        response = (
            self.clear_screen
            + self.logo_col
            + "   _______  __   __  ______    _______  ______   ______   __   __ "
            + self.version_col
            + "   _______ \n"
            + self.logo_col
            + "  |       ||  | |  ||    _ |  |       ||      | |      | |  | |  |"
            + self.version_col
            + "  |       |\n"
            + self.logo_col
            + "  |  _____||  |_|  ||   | ||  |    ___||  _    ||  _    ||  |_|  |"
            + self.version_col
            + "  |____   |\n"
            + self.logo_col
            + "  | |_____ |       ||   |_||_ |   |___ | | |   || | |   ||       |"
            + self.version_col
            + "   ____|  |\n"
            + self.logo_col
            + "  |_____  ||       ||    __  ||    ___|| |_|   || |_|   ||_     _|"
            + self.version_col
            + "  | ______|\n"
            + self.logo_col
            + "   _____| ||   _   ||   |  | ||   |___ |       ||       |  |   |  "
            + self.version_col
            + "  | |_____ \n"
            + self.logo_col
            + "  |_______||__| |__||___|  |_||_______||______| |______|   |___|  "
            + self.version_col
            + "  |_______|\n"
            + f"{self.cyan}  +++ Shreddy, ready, go! +++  {self.white}           Pentagrid AG - https://pentagrid.ch\n\n"
            + f"{self.red}  Disclaimer: There is no guarantee that all data is completely deleted.{self.off}"
            + f"\n\n"
        )

        if last_devices:
            response += "{:16} {:30} {:30}\n".format("Device", "Model", "Status")
            response += "{:16} {:30} {:30}\n\n".format("-" * 16, "-" * 30, "-" * 30)

            for dev in reversed(last_devices[-10:]):
                if dev:
                    color = self.off

                    if dev.get_status() == DeviceStatus.DONE:
                        color = self.green
                    elif dev.get_status() == DeviceStatus.REMOVED:
                        color = self.off
                    elif dev.get_status() == DeviceStatus.INSERTED:
                        color = self.yellow
                    elif dev.has_error():
                        color = self.red
                    else:
                        color = self.white

                    response += "{:16} {:30} {}{:30}{}\n".format(
                        dev.get_path(),
                        dev.get_model(),
                        color,
                        dev.get_status_as_str(),
                        self.off,
                    )
        else:
            response += "No device(s).\n"

        response += "\n\n"

        self.request.sendall(bytearray(response, "utf-8"))

    def handle(self):
        while True:
            self._render_page()
            time.sleep(5)


def create_tcp_server(host, port):

    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.ThreadingTCPServer((host, port), ConnectionHandler)

    t = threading.Thread(target=server.serve_forever)
    t.start()


# -------------------------------------------------------------------------
# Shredding part
# -------------------------------------------------------------------------


def run_command(command):
    ret = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if ret.returncode != 0:
        print(f"+ Command {command} failed with return code {ret.returncode}.")
        return False
    else:
        return True


def check_commands_available(commands):
    for cmd in commands:
        if not run_command(cmd):
            print(f"+ Error: command {cmd[0]} not available.")
            return False
    return True


def wait_for_device(path):
    for retry in range(1, 20):
        print(f"+ Check device availability {path}")
        if os.path.exists(path):
            # Check if we can open the device file
            try:
                os.close(os.open(path, os.O_RDONLY))
                return True
            except IOError:
                pass
        print("+ Wait ...")
        time.sleep(1)
    print("+ Device not found")
    return False


def erase_medium(device):

    path = device.get_path()

    bl_handler.set_status(path, DeviceStatus.RUNNING)

    num_passes = 3
    patterns = ["0", "255"]

    for i in range(1, 2):
        start = timer()
        print(f"+ Run pass {i} on {path}")
        device.set_status(DeviceStatus.RUNNING, f"overwriting pass {i}/{num_passes}")
        if not run_command(["badblocks", "-w", "-p", "1", "-t", patterns[i], path]):
            device.set_error("Erasing failed.")
            bl_handler.set_status(path, DeviceStatus.ERROR)
            return False
        print(
            "%s - Time for overwrite pass %d was: %.2f s" % (path, i, timer() - start)
        )

    start = timer()
    print(f"+ Run pass 3 on {path}")
    device.set_status(DeviceStatus.RUNNING, f"overwriting pass 3/{num_passes}")
    if not run_command(["shred", "-vn", "1", path]):
        device.set_error("Erasing failed.")
        bl_handler.set_status(path, DeviceStatus.ERROR)
        return False
    print("%s - Time for overwrite pass %d was: %.2f s" % (path, 3, timer() - start))

    time.sleep(3)

    start = timer()
    print(f"+ Partition disk {path}")
    # While 'parted' could be run for the device, it is not able
    # to inform the kernel about the change.
    device.set_status(DeviceStatus.RUNNING, "partitioning disk")
    if not run_command(["sudo", "shreddy2-partition.sh", path]):
        device.set_error("Partitioning disk failed")
        bl_handler.set_status(path, DeviceStatus.ERROR)
        return False
    print(
        "%s - Time for %s was: %.2f s"
        % (path, "shreddy2-partition.sh", timer() - start)
    )

    start = timer()
    print(f"+ Wait for file system {path} to appear ...")
    fs_device = f"{path}1"

    # Sometimes the device is not immeditly available and
    # we need to wait.
    if not wait_for_device(fs_device):
        device.set_error(f"Device {fs_device} does not appear")
        bl_handler.set_status(path, DeviceStatus.ERROR)
        return False
    print("%s - Time for %s was: %.2f s" % (path, "waiting", timer() - start))

    print(f"+ Create file system {path}")
    start = timer()
    device.set_status(DeviceStatus.RUNNING, "Creating file system")
    if not run_command(["mkfs.vfat", fs_device]):
        device.set_error("Creating file system failed")
        bl_handler.set_status(path, DeviceStatus.ERROR)
        return False
    print("%s - Time for %s was: %.2f s" % (path, "mkfs.vfat", timer() - start))

    print("+ Completed")
    device.set_status(DeviceStatus.DONE, "done")
    bl_handler.set_status(path, DeviceStatus.DONE)

    return True


# -------------------------------------------------------------------------
# Monitoring part
# -------------------------------------------------------------------------


def monitor_events():
    monitor = pyudev.Monitor.from_netlink(pyudev.Context())
    monitor.filter_by(subsystem="block")

    for action, device in monitor:

        if device.device_type == "disk":

            if device.action == "add":

                print(
                    "+ Device attached: {0} (dev-type: {1}, id-type: {2}, usb-driver: {3})".format(
                        device.device_node,
                        device.device_type,
                        device.properties["ID_TYPE"],
                        device.properties["ID_USB_DRIVER"],
                    )
                )

                if (
                    device.properties["ID_TYPE"] == "disk"
                    and device.properties["ID_USB_DRIVER"] == "usb-storage"
                ):
                    print(f"+ Enqueue erase operation for {device.device_node}")

                    dev = Device(device.device_node, device.properties["ID_MODEL"])
                    bl_handler.set_status(dev.get_path(), DeviceStatus.INSERTED)
                    last_devices.append(dev)

                    t = threading.Thread(target=erase_medium, args=(dev,))
                    t.start()

            elif device.action == "remove":
                print("+ Device detached: {}".format(device.device_node))
                if last_devices:
                    for d in reversed(last_devices):
                        if d.get_path() == device.device_node:
                            bl_handler.set_status(d.get_path(), DeviceStatus.REMOVED)
                            d.set_status(DeviceStatus.REMOVED, "removed")


# -------------------------------------------------------------------------
# Program start
# -------------------------------------------------------------------------


def main():
    global bl_handler

    # First check if required commands are available. Therefore, we
    # run them in a safe manor and check what the return code is.
    if not check_commands_available(
        [
            ["shred", "--version"],
            ["parted", "-v"],
            # ['badblocks'],
            ["mkfs.vfat", "--help"],
        ]
    ):
        # When a command is not available, we stop
        return False
    else:

        try:
            from pybusylight import pybusylight

            bl = pybusylight.busylight()
        except ImportError:
            # Library is not present
            bl = None
            pass
        except ValueError:
            # Device is not present
            bl = None
            pass

        bl_handler = BusylightHandler(bl)

        if port is not None:
            print("+ Start TCP server.")
            create_tcp_server(host, port)
        print(f"+ Start device monitor. Waiting for devices.")
        monitor_events()


if __name__ == "__main__":
    main()
