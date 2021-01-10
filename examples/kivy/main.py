#!/usr/bin/env python3

from kivy.app import App
#from kivy.core.window import Window
from kivy.logger import Logger
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

import asyncio
import bleak
import logging

class ExampleApp(App):
    def __init__(self):
        super().__init__()
        self.label = None
        self.running = True

    def build(self):
        print('build')
        self.scrollview = ScrollView(do_scroll_x=False, scroll_type=['bars', 'content'])
        self.label = Label(font_size='10sp')
        self.scrollview.add_widget(self.label)
        return self.scrollview

    def line(self, text, empty = False):
        Logger.info('example:' + text)
        if self.label is None:
            return
        text += '\n'
        if empty:
            self.label.text = text
        else:
            self.label.text += text

    def on_stop(self):
        self.running = False

    async def example(self):
        print('example')
        scanner = bleak.BleakScanner()
        while self.running:
            try:
                self.line('scanning')
                scanned_devices = await scanner.discover(1)
                self.line('scanned', True)

                if len(scanned_devices) == 0:
                    raise bleak.exc.BleakError('no devices found')

                for device in scanned_devices:
                    self.line('{0} "{1}" {2}dB'.format(device.address, device.name, device.rssi))

                for device in scanned_devices:
                    self.line('Connecting to {0} "{1}" ...'.format(device.address, device.name))
                    client = bleak.BleakClient(device.address)
                    try:
                        await client.connect()

                        services = await client.get_services()
                        for service in services.services.values():
                            self.line('  service {0}'.format(service.uuid))
                            for characteristic in service.characteristics:
                                self.line('  characteristic {0} {1}'.format(characteristic.uuid, hex(characteristic.handle)))
                                for descriptor in characteristic.descriptors:
                                    self.line('  descriptor {0} {1}'.format(descriptor.uuid, hex(descriptor.handle)))
                        if device.name[:4] == 'Muse':
                            # let's get a version request and stream a channel
                            serial='273e0001-4c4d-454d-96be-f03bac821358'
                            channel='273e0003-4c4d-454d-96be-f03bac821358'
                            # subscribe to both
                            #def serial_data(handle, data):
                            #    self.line(data.decode('utf-8'))
                            #self.line('starting notify 1')
                            #await client.start_notify(serial, serial_data)
                            #future = asyncio.get_event_loop().create_future()
                            #def channel_data(handle, data):
                            #    self.line(data)
                            #    future.set_result(True)
                            #self.line('starting notify 2')
                            #await client.start_notify(channel, channel_data)
                            self.line('writing data ' + str(client))
                            for char in '\x02s\n':
                                data = bytearray([ord(char)])
                                self.line('writing ' + str(data))
                                await client.write_gatt_char(serial, data)
                            self.line('done')

                        await client.disconnect()
                    except bleak.exc.BleakError as e:
                        self.line('  error {0}'.format(e))
            except bleak.exc.BleakError as e:
                self.line('ERROR {0}'.format(e))
                asyncio.sleep(1)
        self.line('example loop terminated', True)


if __name__ == '__main__':
    print('main')
    # bind bleak's python logger into kivy's logger?
    logging.Logger.manager.root = Logger
    logging.basicConfig(level=logging.DEBUG)

    # app running on one thread with two async coroutines
    app = ExampleApp()
    loop = asyncio.get_event_loop()
    coroutines = (
        app.async_run('asyncio'),
        app.example()
    )
    firstexception = asyncio.wait(coroutines, return_when=asyncio.FIRST_EXCEPTION)
    results, ongoing = loop.run_until_complete(firstexception)
    for result in results:
        result.result() # raises exceptions from asyncio.wait
