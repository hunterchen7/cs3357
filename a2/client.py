# to run in terminal: python client.py --name 
from chatroom import ClientUDP as Client
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--name', '-n', type=str, help='Client name')
args = parser.parse_args()
client = Client(args.name, 12345)
client.run()