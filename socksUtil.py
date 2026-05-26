import config
sockets = []
current = 0


def addSocket(websocket):
    sockets.append(websocket)


def removeSocket(websocket):
    sockets.remove(websocket)

def getCurrent():
    try:
        return sockets[current]
    except:
        return None


def listSockets():
    res = {}
    for i in range(len(sockets)):
        s = sockets[i]
        # In websockets.asyncio, path is in s.request.path
        sid = s.request.path.strip("/") if hasattr(s, "request") else "unknown"
        res[str(i)] = {
            "index": i,
            "id": str(s.id),
            "sid": sid,
            "ip": getattr(s, "remote_ip", "unknown"),
            "mitmUrl": f"http://{config.MITM_HOST}:{config.MITM_PORT}/{sid}/"
        }
    return res
def getSocketBySid(sid):
    for s in sockets:
        if hasattr(s, "request") and s.request.path.strip("/") == sid:
            return s
    return None
