from base64 import b64decode, b64encode
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

#TODO: Genera una key por conexión y un iv por conexión, no uses estos valores en producción
secret_key = "UmFuZG9tS2V5Rm9yQUVTIQ=="
iv = "1020304050607080"

def decrypt(data: str) -> str:
    ciphertext = b64decode(data)
    derived_key = b64decode(secret_key)
    cipher = AES.new(derived_key, AES.MODE_CBC, iv.encode('utf-8'))
    decrypted_data = cipher.decrypt(ciphertext)
    print(unpad(decrypted_data, 16).decode("utf-8"))
    return unpad(decrypted_data, 16).decode("utf-8")

def encrypt(data: str) -> str:
    derived_key = b64decode(secret_key)
    cipher = AES.new(derived_key, AES.MODE_CBC, iv.encode('utf-8'))
    padded_data = data + (16 - len(data) % 16) * chr(16 - len(data) % 16)
    encrypted_data = cipher.encrypt(padded_data.encode('utf-8'))
    return b64encode(encrypted_data).decode("utf-8")

async def sendSecretMessage(websocket, msg):
    await websocket.send(encrypt(msg))
