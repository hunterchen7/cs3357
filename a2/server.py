# to run in terminal: python server.py
from chatroom import ServerTCP
server = ServerTCP(12345)
server.run()