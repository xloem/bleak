Basic usage
==============

.. note::

    A Bluetooth peripheral may have several characteristics with the same UUID, so
    the means of specifying characteristics by UUID or string representation of it
    might not always work in bleak version > 0.7.0. One can now also use the characteristic's
    handle or even the ``BleakGATTCharacteristic`` object itself in
    ``read_gatt_char``, ``write_gatt_char``, ``start_notify``, and ``stop_notify``.

Scanning
--------

To discover Bluetooth devices that can be connected to:

.. code-block:: python

    import asyncio
    from bleak import discover

    async def run():
        devices = await discover()
        for d in devices:
            print(d)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())

This will produce a printed list of detected devices:

.. code-block:: sh

    24:71:89:CC:09:05: CC2650 SensorTag
    4D:41:D5:8C:7A:0B: Apple, Inc. (b'\x10\x06\x11\x1a\xb2\x9b\x9c\xe3')

The first part, a MAC address in Windows and Linux and a UUID in macOS, is what is
used for connecting to a device using Bleak. The list of objects returned by the `discover`
method are instances of :py:class:`bleak.backends.device.BLEDevice` and has ``name``, ``address``
and ``rssi`` attributes, as well as a ``metadata`` attribute, a dict with keys ``uuids`` and ``manufacturer_data``
which potentially contains a list of all service UUIDs on the device and a binary string of data from
the manufacturer of the device respectively.

Connecting to a device
----------------------

One can use the ``BleakClient`` to connect to a Bluetooth device and read its model number
via the asyncronous context manager like this:

.. code-block:: python

    import asyncio
    from bleak import BleakClient

    address = "24:71:89:cc:09:05"
    MODEL_NBR_UUID = "00002a24-0000-1000-8000-00805f9b34fb"

    async def run(address):
        async with BleakClient(address) as client:
            model_number = await client.read_gatt_char(MODEL_NBR_UUID)
            print("Model Number: {0}".format("".join(map(chr, model_number))))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(address))

or one can do it without the context manager like this:

.. code-block:: python

    import asyncio
    from bleak import BleakClient

    address = "24:71:89:cc:09:05"
    MODEL_NBR_UUID = "00002a24-0000-1000-8000-00805f9b34fb"

    async def run(address):
        client = BleakClient(address)
        try:
            await client.connect()
            model_number = await client.read_gatt_char(MODEL_NBR_UUID)
            print("Model Number: {0}".format("".join(map(chr, model_number))))
        except Exception as e:
            print(e)
        finally:
            await client.disconnect()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(address))

Make sure you always get to call the disconnect method for a client before discarding it;
the Bluetooth stack on the OS might need to be cleared of residual data which is cached in the
``BleakClient``.

Notifications
-------------

TBW.

