"""macOS Keychain only; no env/file fallback and no secrets in subprocess argv."""
import ctypes as C
import sys


class MacOSKeychain:
    SERVICE = b'FinalEditorPro'

    def __init__(self):
        if sys.platform != 'darwin':
            raise RuntimeError('macOS Keychain is required')
        self._security = C.CDLL('/System/Library/Frameworks/Security.framework/Security')
        self._core = C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        self._core.CFRelease.argtypes = [C.c_void_p]
        self._security.SecKeychainFindGenericPassword.argtypes = [
            C.c_void_p, C.c_uint32, C.c_char_p, C.c_uint32, C.c_char_p,
            C.POINTER(C.c_uint32), C.POINTER(C.c_void_p), C.POINTER(C.c_void_p)]
        self._security.SecKeychainFindGenericPassword.restype = C.c_int32
        self._security.SecKeychainItemFreeContent.argtypes = [C.c_void_p, C.c_void_p]
        self._security.SecKeychainAddGenericPassword.argtypes = [
            C.c_void_p, C.c_uint32, C.c_char_p, C.c_uint32, C.c_char_p,
            C.c_uint32, C.c_void_p, C.POINTER(C.c_void_p)]
        self._security.SecKeychainAddGenericPassword.restype = C.c_int32
        self._security.SecKeychainItemModifyAttributesAndData.argtypes = [
            C.c_void_p, C.c_void_p, C.c_uint32, C.c_void_p]
        self._security.SecKeychainItemModifyAttributesAndData.restype = C.c_int32

    def _find(self, account):
        name = account.encode()
        length, data, item = C.c_uint32(), C.c_void_p(), C.c_void_p()
        status = self._security.SecKeychainFindGenericPassword(
            None, len(self.SERVICE), self.SERVICE, len(name), name,
            C.byref(length), C.byref(data), C.byref(item))
        return status, length, data, item

    def get(self, account):
        status, length, data, item = self._find(account)
        if status != 0:
            raise PermissionError(f'Keychain lookup failed (OSStatus {status})')
        try:
            return C.string_at(data, length.value).decode()
        finally:
            self._security.SecKeychainItemFreeContent(None, data)
            self._core.CFRelease(item)

    def set(self, account, secret):
        if not account or not secret:
            raise ValueError('Account and secret required')
        value, name = secret.encode(), account.encode()
        status, _, data, item = self._find(account)
        if status == 0:
            self._security.SecKeychainItemFreeContent(None, data)
            try:
                result = self._security.SecKeychainItemModifyAttributesAndData(item, None, len(value), value)
            finally:
                self._core.CFRelease(item)
        elif status == -25300:  # errSecItemNotFound
            result = self._security.SecKeychainAddGenericPassword(
                None, len(self.SERVICE), self.SERVICE, len(name), name, len(value), value, None)
        else:
            result = status
        if result != 0:
            raise PermissionError(f'Keychain write failed (OSStatus {result})')
