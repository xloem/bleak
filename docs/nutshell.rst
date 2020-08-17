.. _nutshell:

What Bleak is and what it isn't
===============================

The state of BLE in Python when I started to implement Bleak was such that no package worked in Windows, macOS and
Linux-distributions, at least not without installing a lot of non-pip software and compilers to be able to install it.
I found that discouraging and wanted to see if something could be done about that.

I wanted to implement a Bluetooth Low-Energy Central/Client API which fulfiled the following criteria:

1. Bleak should be possible to use on Windows, macOS and Linux-distributions
2. Bleak should have a identical API with as few as possible of functional differences between OS implementations
3. Bleak should be pip-installable with no install-time compilations
4. Bleak should use only OS native BLE components, preferably ones installed as default in the OS so no extra non-pip installations are necessary
5. Bleak should use the ``asyncio`` standard library and its event loops, at least where the Bleak user is concerned

This package is the results. It is not the best Python BLE package when it comes to number of features or




