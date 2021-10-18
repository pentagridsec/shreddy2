``shreddy2.py`` -- The Raspberry Pi storage scrub station for USB thumb drives.

.. contents:: 
   :local:

About
======

Operate your own USB memory stick cleaning station by running this piece of
software on a Raspberry PI. USB storage media attached to it is overwritten
according to NIST 800-88. The overwriting cycle is 0x00, 0xff and then random
data as final pass.

Read the full story at https://pentagrid.ch/en/blog/XXXXXXXXXXXXXXXXXXXX


Setup
======

Set up the Raspberry Pi
-------------------------

Set up a Raspberry Pi and install the Raspberry Pi OS according to the
documentation on  https://www.raspberrypi.org/software/. Do this in a
safe environment.

Log in to the Raspberry PI. Ensure the default password of the Raspberry
Pi is changed. Otherwise, this is a risk for the data attached as USB sticks.

Install dependencies
---------------------

Install dependencies:

::
   
   sudo apt install python3-pyudev coreutils parted dosfstools


If you like to use a busylight, run the following commands to install software:

::
   
   git clone https://github.com/nitram2342/pyBusylight.git
   cd pyBusylight/
   sudo python3 setup.py install

Shreddy will probe for the module, and if the module is not there, the
feature is not used.

Create a user that runs the software and adjust Udev rules
-----------------------------------------------------------

Create a user that will later run the software:

::
   
   sudo useradd -d /var/shreddy2 -m -s /usr/sbin/nologin shreddy2

   
Edit ``/etc/udev/rules.d/23-usb-storage-permissions.rules``:

::

   ACTION=="add", SUBSYSTEMS=="usb", SUBSYSTEM=="block", MODE="0660", OWNER="shreddy2"

Edit ``/etc/udev/rules.d/42-usb-busylight.rules`` if you like to use a
Kuando Busylight:

::

   SUBSYSTEM=="usb", ATTRS{idVendor}=="27bb", ATTRS{idProduct}=="3bc0", OWNER="shreddy2", MODE="0660"
   SUBSYSTEM=="usb", ATTRS{idVendor}=="27bb", ATTRS{idProduct}=="3bca", OWNER="shreddy2", MODE="0660"
   SUBSYSTEM=="usb", ATTRS{idVendor}=="27bb", ATTRS{idProduct}=="3bcc", OWNER="shreddy2", MODE="0660"
   SUBSYSTEM=="usb", ATTRS{idVendor}=="27bb", ATTRS{idProduct}=="3bcd", OWNER="shreddy2", MODE="0660"
   SUBSYSTEM=="usb", ATTRS{idVendor}=="27bb", ATTRS{idProduct}=="f848", OWNER="shreddy2", MODE="0660"

Reload udev rules:

::

   sudo udevadm control --reload-rules

Install Shreddy2
-----------------

Get Shreddy2 source code:

::
   
   git clone https://github.com/pentagridsec/shreddy2
   cd shreddy2
   
Install program files:

::
   
   sudo cp shreddy2.service /etc/systemd/system/
   sudo cp shreddy2.py shreddy2-partition.sh /usr/local/bin
   sudo chown root.root /usr/local/bin/shreddy2.py /usr/local/bin/shreddy2-partition.sh /etc/systemd/system/shreddy2.service


Allow Shreddy2 user to run ``/usr/local/bin/shreddy2-partition.sh`` in privileged mode. Therefore, edit ``/etc/sudoers.conf`` by running:

::

   sudo visudo

... and add the following line to the ``/etc/sudoers.conf`` configuration:

::
   
   shreddy2 ALL=(root) NOPASSWD:/usr/local/bin/shreddy2-partition.sh
   
Enable and run server:

::
   
   sudo systemctl daemon-reload
   sudo systemctl enable shreddy2
   sudo systemctl start shreddy2
   sudo systemctl status shreddy2


Security and operational notes
==============================

* Overwriting Flash memory does not guarantee that there are no data residues
  left. It only reduces the probability. It is best effort.
* If the shredding station is compromised and a storage medium is attached,
  information is exposed to the compromised station. You may want
  to run the shredding station in an air-gapped mode and using a Busylight for
  status signalling.
* If you operate the erasing station in a less trustworthy environment, the
  station could be compromised. If you leave USB sticks, they may be removed
  by other people, either before or after the clean up operation. Furthermore,
  USB sticks could be replaced by malicious hardware that has got implants.
* The erasing station should be labelled with a sufficiently noticeable warning.
  Otherwise, people think they could charge their phones.

Copyright and Licence
======================

This software is developed by Martin Schobert <martin.schobert@pentagrid.ch>.
It is published under BSD license with a non-military clause. Please read
``LICENSE`` for license details.
