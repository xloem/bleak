package com.github.hbldh.bleak;

import java.net.ConnectException;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CancellationException;
import java.util.concurrent.ExecutionException;
import java.util.HashMap;
import java.util.UUID;

import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothProfile;


public final class PythonBluetoothGattCallback extends BluetoothGattCallback
{
    public interface Interface
    {
        public void onConnectionStateChange(int status, int newState);
        public void onServicesDiscovered(int status);
    }
    private Interface callback;
        
    public PythonBluetoothGattCallback(Interface pythonCallback)
    {
        callback = pythonCallback;
    }

    /*
    public void subscribe(UUID uuid, Runnable runnable)
    {
        notifiees.put(uuid, runnable);
    }

    public void unsubscribe(UUID uuid)
    {
        notifiees.remove(uuid);
    }

    public void reset()
    {
        future = new CompletableFuture<BluetoothGatt>();
    }

    public BluetoothGatt waitFor() throws ExecutionException, CancellationException
    {
        // this approach of wrapping futures could likely be heavily simplified by
        // somebody more familiar with java or python; please do so if interested.
        // i noticed java has a 'synchronized' primitive, and inherent notify/wait
        // methods on every object.  or the concept could be moved into python,
        // which would be easier if PythonJavaClass provided for inheritance.
        while (true) {
            try {
                return future.get();
            } catch(InterruptedException e) {}
        }
    }
    */

    @Override
    public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState)
    {
        callback.onConnectionStateChange(status, newState);
    }

    @Override
    public void onServicesDiscovered(BluetoothGatt gatt, int status)
    {
        callback.onServicesDiscovered(status);
    }

    /*

    @Override
    public void onCharacteristicWrite(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic, int status)
    {
        if (status == 0) {
            future.complete(gatt);
        } else {
            future.completeExceptionally(new Status(status));
        }
    }

    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic)
    {
        Runnable notifiee = notifiees.getOrDefault(characteristic.getUuid(), null);
        if (notifiee != null) {
            notifiee.run();
        }
    }
    */
}
