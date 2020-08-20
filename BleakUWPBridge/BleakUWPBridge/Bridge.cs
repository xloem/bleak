using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Windows.Devices.Bluetooth;
using Windows.Devices.Bluetooth.Advertisement;
using Windows.Devices.Bluetooth.GenericAttributeProfile;
using Windows.Foundation;

namespace BleakBridge
{
    public class Bridge: IDisposable
    {
        public TypedEventHandler<BluetoothLEAdvertisementWatcher, BluetoothLEAdvertisementReceivedEventArgs> receivedCallback;
        public TypedEventHandler<BluetoothLEAdvertisementWatcher, BluetoothLEAdvertisementWatcherStoppedEventArgs> stoppedCallback;
        public TypedEventHandler<BluetoothLEDevice, object> connectionStatusChangedCallback;
        public Dictionary<ushort, TypedEventHandler<GattCharacteristic, GattValueChangedEventArgs>> callbacks;

        public Bridge()
        {
            callbacks = new Dictionary<ushort, TypedEventHandler<GattCharacteristic, GattValueChangedEventArgs>>();
        }

        public void Dispose()
        {
            this.receivedCallback = null;
            this.stoppedCallback = null;
            callbacks.Clear();
        }

        #region BLE Device Event Handlers Handling

        public void AddConnectionStatusChangedHandler(BluetoothLEDevice device, TypedEventHandler<BluetoothLEDevice, object> connectionStatusChangedCallback)
        {
            this.connectionStatusChangedCallback = connectionStatusChangedCallback;
            device.ConnectionStatusChanged += this.connectionStatusChangedCallback;
        }
        public void RemoveConnectionStatusChangedHandler(BluetoothLEDevice device)
        {
            device.ConnectionStatusChanged -= this.connectionStatusChangedCallback;
            this.connectionStatusChangedCallback = null;
        }

        #endregion

        #region BLE Advertisement Watcher Event Handlers Handling

        public void AddWatcherEventHandlers(
            BluetoothLEAdvertisementWatcher watcher,
            TypedEventHandler<BluetoothLEAdvertisementWatcher, BluetoothLEAdvertisementReceivedEventArgs> receivedCallback,
            TypedEventHandler<BluetoothLEAdvertisementWatcher, BluetoothLEAdvertisementWatcherStoppedEventArgs> stoppedCallback
        )
        {
            this.receivedCallback = receivedCallback;
            watcher.Received += this.receivedCallback;
            this.stoppedCallback = stoppedCallback;
            watcher.Stopped += this.stoppedCallback;
        }

        public void RemoveWatcherEventHandlers(BluetoothLEAdvertisementWatcher watcher)
        {
            watcher.Received -= this.receivedCallback;
            this.receivedCallback = null;
            watcher.Stopped -= this.stoppedCallback;
            this.stoppedCallback = null;
        }

        #endregion

        #region Notifications Handlers Handling

        public void AddValueChangedCallback(GattCharacteristic characteristic, TypedEventHandler<GattCharacteristic, GattValueChangedEventArgs> callback)
        {
            this.callbacks[characteristic.AttributeHandle] = callback;
            characteristic.ValueChanged += callback;
        }

        public void RemoveValueChangedCallback(GattCharacteristic characteristic)
        {
            if (this.callbacks.ContainsKey(characteristic.AttributeHandle))
            {
                var stored_callback = this.callbacks[characteristic.AttributeHandle];
                this.callbacks.Remove(characteristic.AttributeHandle);
                characteristic.ValueChanged -= stored_callback;
            }
        }

        #endregion

        /// <summary>
        /// Method is not actually used, merely here to enable the bridge to provide Python.NET access to the Windows namespace.
        /// </summary>
        /// <param name="characteristic">GATTCharacteristic</param>
        /// <returns></returns>
        private async Task<GattCommunicationStatus> DummyMethod(GattCharacteristic characteristic)
        {
            await Task.Delay(1);
            return GattCommunicationStatus.Success;
        }


    }
}
