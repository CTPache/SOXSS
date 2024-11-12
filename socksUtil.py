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
#        print('Socket index out of range, default to 0.')
#        current = 0
#        return sockets[current]


def listSockets():
    res = {}
    for i in range(sockets.__len__()):
        res[str(i)] = str(sockets[i].id)
    return res
