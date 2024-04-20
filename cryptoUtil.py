from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64

def encrypt(text):
    # TODO
    return text


def decrypt(cipher):
    # TODO
    return cipher


async def sendSecretMessage(websocket, msg):
    # TODO
    await websocket.send(msg)
