Bleak backends
==============

Bleak supports the following operating systems:

* Windows 10, version 16299 (Fall Creators Update) and greater
* Linux distributions with BlueZ >= 5.43
* OS X/macOS support via Core Bluetooth API, from at least version 10.11

However, there are platform specific differences from and/or additions to the interface API in the difference OS backend implementations.


Windows backend
---------------

The Windows backend of bleak is written using the `Python for .NET <https://pythonnet.github.io/>`_
package. Combined with a thin bridge library (`BleakUWPBridge <https://github.com/hbldh/bleak/tree/master/BleakUWPBridge>`_)
that is bundled with bleak, the .NET Bluetooth components can be used from Python.

The Windows backend implements a ``BleakClient`` in the module ``bleak.backends.dotnet.client``, a ``discover``
method in the ``bleak.backends.dotnet.discovery`` module. There are also backend-specific implementations of the
``BleakGATTService``, ``BleakGATTCharacteristic`` and ``BleakGATTDescriptor`` classes.

Finally, some .NET/``asyncio``-connectivity methods are available in the ``bleak.backends.dotnet.utils`` module.

.. note::

    A problem with memory leakage is present in the Windows backend (`Issue #255 <https://github.com/hbldh/bleak/issues/255>`_).
    For now, try to run long running Bleak programs in separate processes If possible, so that memory is released when these processes are closed.

Specific features for the Windows backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``BleakClient``: The constructor keyword ``address_type`` which can have the values ``"public"`` or ``"random"``. This value
   makes sure that the connection is made in a fashion that suits the peripheral.


macOS backend
-------------

The macOS backend of Bleak is written with
`pyobjc <https://pyobjc.readthedocs.io/en/latest/>`_ directives for interfacing
with `Foundation <https://pyobjc.readthedocs.io/en/latest/apinotes/Foundation.html>`_
and `CoreBluetooth <https://pyobjc.readthedocs.io/en/latest/apinotes/CoreBluetooth.html>`_ APIs.

Specific features for the macOS backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most noticeable difference between the other
backends of bleak and this backend, is that CoreBluetooth doesn't scan for
other devices via MAC address. Instead, UUIDs are utilized that are often
unique between the device that is scanning and the device that is being scanned.

In the example files, this is handled in this fashion:

.. code-block:: python

    mac_addr = (
        "24:71:89:cc:09:05"
        if platform.system() != "Darwin"
        else "243E23AE-4A99-406C-B317-18F1BD7B4CBE"
    )

As stated above, this will however only work the macOS machine that performed
the scan and thus cached the device as ``243E23AE-4A99-406C-B317-18F1BD7B4CBE``.


Linux backend
-------------

The Linux backend of Bleak is written using the
`TxDBus <https://github.com/cocagne/txdbus>`_
package. It is written for
`Twisted <https://twistedmatrix.com/trac/>`_, but by using the
`twisted.internet.asyncioreactor <https://twistedmatrix.com/documents/current/api/twisted.internet.asyncioreactor.html>`_
one can use it with `asyncio`.


Special handling for ``write_gatt_char``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``type`` option to the ``Characteristic.WriteValue``
method was added to
`Bluez in 5.50 <https://git.kernel.org/pub/scm/bluetooth/bluez.git/commit?id=fa9473bcc48417d69cc9ef81d41a72b18e34a55a>`_
Before that commit, ``Characteristic.WriteValue`` was only "Write with response".

``Characteristic.AcquireWrite`` was added in
`Bluez 5.46 <https://git.kernel.org/pub/scm/bluetooth/bluez.git/commit/doc/gatt-api.txt?id=f59f3dedb2c79a75e51a3a0d27e2ae06fefc603e>`_
which can be used to "Write without response", but for older versions of Bluez (5.43, 5.44, 5.45), it is not possible to "Write without response".
