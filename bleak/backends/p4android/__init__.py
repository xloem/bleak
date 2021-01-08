from jnius import autoclass

# considering workarounds for accessing java from new threads.  might be easiest to only do it from the main thread, which might mean not using an asyncio thread in the example or something
# https://github.com/kivy/pyjnius/issues/223
autoclass('org.jnius.NativeInvocationHandler')
# this line doesn't fix the issue the way the preceding line did.
#autoclass('org.kivy.android.PythonActivity$PermissionsCallback')
