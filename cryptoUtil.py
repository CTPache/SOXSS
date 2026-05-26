from base64 import b64decode, b64encode
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
import asyncio
import os
from typing import Optional, Dict, Tuple
import base64

_sessions: Dict[str, Tuple[str, str]] = {}

def generate_key_iv():
    key = os.urandom(16)
    iv = os.urandom(16)
    return base64.b64encode(key).decode(), iv.hex()

def set_key_iv(sid: str, secret_key: str, iv: str):
    _sessions[sid] = (secret_key, iv)

def get_key(sid: str):
    return _sessions.get(sid, (None, None))[0]

def get_iv(sid: str):
    return _sessions.get(sid, (None, None))[1]


def decrypt(data: str, sid: str) -> str:
    secret_key, iv = _sessions.get(sid, (None, None))
    if not secret_key or not iv:
        raise ValueError(f"Secret key and IV must be set for session {sid} before decrypting.")
    ciphertext = b64decode(data)
    derived_key = b64decode(secret_key)
    cipher = AES.new(derived_key, AES.MODE_CBC, bytes.fromhex(iv))
    decrypted_data = cipher.decrypt(ciphertext)
    return unpad(decrypted_data, 16).decode("utf-8")


def encrypt(data: str, sid: str) -> str:
    secret_key, iv = _sessions.get(sid, (None, None))
    if not secret_key or not iv:
        raise ValueError(f"Secret key and IV must be set for session {sid} before encrypting.")
    derived_key = b64decode(secret_key)
    cipher = AES.new(derived_key, AES.MODE_CBC, bytes.fromhex(iv))
    padded_data = pad(data.encode('utf-8'), 16)
    encrypted_data = cipher.encrypt(padded_data)
    return b64encode(encrypted_data).decode("utf-8")

_send_lock = asyncio.Lock()

async def sendSecretMessage(websocket, msg):
    sid = websocket.request.path.strip("/") if hasattr(websocket, "request") else "unknown"
    async with _send_lock:
        await websocket.send(encrypt(msg, sid))
