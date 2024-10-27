# to run in terminal: python server.py
from chatroom import ServerUDP as Server
server = Server(12345)
server.run()