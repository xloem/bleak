#!/usr/bin/env python3

from kivy.app import App
from kivy.uix.label import Label

import async_to_sync as sync
import bleak

import sys
import time

from android.permissions import request_permissions, Permission

class MyApp(App):

    def build(self):
        scanner = sync(bleak.BleakScanner())
        scanned_devices = scanner.discover(5)
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
        return Label(text = summary, font_size='10sp')


if __name__ == '__main__':
    app = MyApp()
    app.run()
