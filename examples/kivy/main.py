#!/usr/bin/env python3

from kivy.app import App
from kivy.uix.label import Label

import asyncio
import bleak

import sys
import time

from android.permissions import request_permissions, Permission

def acall(coroutine):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coroutine)
def pump(seconds):
    acall(asyncio.sleep(seconds))

class MyApp(App):

    def build(self):
        scanner = bleak.BleakScanner()
        try:
            print('scanning ...')
            scanned_devices = acall(scanner.discover(1))
            print('scanned')
            if len(scanned_devices) == 0:
                print('no devices found')
                return Label(text = 'no devices found')
            summary = ''
            for scanned_device in scanned_devices:
                summary += scanned_device.address + ' ' + scanned_device.name + ':\n'
                client = bleak.BleakClient(scanned_device.address)
                acall(client.connect())
                services = client.get_services()
                for service in services.services.values():
                    summary += '  service ' + service.uuid + '\n'
                    for characteristic in service.characteristics:
                        summary += '  characteristic ' + characteristic.uuid + '\n'
                acall(client.disconnect())
            print(summary)
        except bleak.exc.BleakError as e:
            summary = str(e)
        return Label(text = summary, font_size='10sp')


if __name__ == '__main__':
    app = MyApp()
    app.run()
