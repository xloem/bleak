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
        print('build')
        scanner = bleak.BleakScanner()
        try:
            scanned_devices = acall(scanner.discover(1))
            if len(scanned_devices) == 0:
                print('no devices found')
                return Label(text = 'no devices found')
            summary = ''
            for scanned_device in scanned_devices:
                summary += scanned_device.address + scanned_device.name + ':\n'
                #scanned_device.connect()
                #scanned_device.discover()
            
                #for service in scanned_device.services.values():
                #    summary += '  service ' + str(service.uuid) + '\n'
                #for characteristic in scanned_device.characteristics.values():
                #    summary += '  characteristic ' + str(characteristic.uuid) + '\n'
                #print(summary)
        except bleak.exc.BleakError as e:
            summary = str(e)
        return Label(text = summary, font_size='10sp')


if __name__ == '__main__':
    app = MyApp()
    app.run()
