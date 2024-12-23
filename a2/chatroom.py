import socket
import threading
import sys
import select

class ServerTCP:
    def __init__(self, server_port):
        self.server_port = server_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        addr = socket.gethostbyname(socket.gethostname())
        self.server_socket.bind((addr, self.server_port))
        self.server_socket.listen()

        self.clients = {}
        self.run_event = threading.Event()
        self.handle_event = threading.Event() 

    def accept_client(self):
        client_socket = self.server_socket.accept()[0]
        name = client_socket.recv(1024).decode()

        if name in self.clients.values():
            client_socket.send("Name already taken".encode())
            client_socket.close()
            return False
        else:
            client_socket.send("Welcome".encode())
            self.clients[client_socket] = name
            self.broadcast(client_socket, "join")
            return True

    def close_client(self, client_socket):
        if client_socket in self.clients:
            self.broadcast(client_socket, "exit")
            del self.clients[client_socket]
            client_socket.close()
            return True
        return False

    def broadcast(self, client_socket_sent, message):
        if message == "join":
            msg_to_broadcast = f"User {self.clients[client_socket_sent]} joined"
        elif message == "exit":
            msg_to_broadcast = f"User {self.clients[client_socket_sent]} left"
        else:
            msg_to_broadcast = f"{self.clients[client_socket_sent]}: {message}"

        for client_socket in self.clients:
            if client_socket != client_socket_sent:
                try:
                    client_socket.send(msg_to_broadcast.encode())
                except:
                    self.close_client(client_socket)

    def shutdown(self):
        shutdown_message = "server-shutdown"
        for client_socket in self.clients:
            try:
                client_socket.send(shutdown_message.encode())
                client_socket.close()
            except:
                pass

        self.run_event.set()
        self.handle_event.set()
        self.server_socket.close()

    def get_clients_number(self):
        return len(self.clients)

    def handle_client(self, client_socket):
        while not self.handle_event.is_set():
            try:
                # Use select with a timeout of 1 second
                readable, _, exceptional = select.select([client_socket], [], [client_socket], 1.0)
                
                if client_socket in readable:
                    message = client_socket.recv(1024).decode()
                    if message == "exit":
                        self.close_client(client_socket)
                        break
                    elif message:  # Only broadcast non-empty messages
                        self.broadcast(client_socket, message)
                    else:  # Empty message means client disconnected
                        self.close_client(client_socket)
                        break
                
                if client_socket in exceptional:
                    self.close_client(client_socket)
                    break
                    
            except Exception as e:
                print(f"Error handling client: {e}")
                self.close_client(client_socket)
                break

    def run(self):
        print("Server is running...")
        self.run_event.clear()
        self.handle_event.clear()

        try:
            while not self.run_event.is_set():
                # Use select to monitor server socket for new connections
                readable, _, exceptional = select.select([self.server_socket], [], [], 1.0)

                if self.server_socket in readable:
                    if self.accept_client():
                        client_socket = list(self.clients.keys())[-1]
                        # Start a thread for the new client
                        client_thread = threading.Thread(
                            target=self.handle_client, 
                            args=(client_socket,)
                        )
                        client_thread.start()

        except KeyboardInterrupt:
            print("Server shutting down...")
            self.shutdown()

class ClientTCP:
    def __init__(self, client_name, server_port):
        self.server_addr = socket.gethostbyname(socket.gethostname())
        self.server_port = server_port
        self.client_name = client_name
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.exit_run = threading.Event()
        self.exit_receive = threading.Event()

    def connect_server(self):
        try:
            self.client_socket.connect((self.server_addr, self.server_port))
            self.client_socket.send(self.client_name.encode())
            response = self.client_socket.recv(1024).decode()

            if 'Welcome' in response:
                print("Connected to the chatroom.")
                return True
            else:
                print("Failed to join the chatroom:", response)
                return False
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def send(self, text):
        try:
            self.client_socket.send(text.encode())
        except Exception as e:
            print(f"Error sending message: {e}")

    def receive(self):
        while not self.exit_receive.is_set():
            try:
                message = self.client_socket.recv(1024).decode()
                if message == 'server-shutdown':
                    print("Server is shutting down.")
                    self.exit_run.set()
                    self.exit_receive.set()
                    break
                else:
                    sys.stdout.write(f"\r{message}\n")
                    sys.stdout.flush()
                    sys.stdout.write(f"{self.client_name}: ")
                    sys.stdout.flush()
            except Exception as e:
                print(f"Error receiving message: {e}")
                break

    def run(self):
        if not self.connect_server():
            return

        receive_thread = threading.Thread(target=self.receive)
        receive_thread.start()

        try:
            while not self.exit_run.is_set():
                message = input(f"{self.client_name}: ")
                if message == 'exit':
                    self.send('exit')
                    self.exit_receive.set()
                    break
                self.send(message)
        except KeyboardInterrupt:
            self.send('exit')
            self.exit_receive.set()
        finally:
            self.client_socket.close()

class ServerUDP:
    def __init__(self, server_port):
        self.server_port = server_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = socket.gethostbyname(socket.gethostname())
        self.server_socket.bind((addr, self.server_port))
        self.server_socket.setblocking(False)

        self.clients = {}
        self.messages = []
        
    def broadcast(self):
        if self.messages:
            sender_addr, message = self.messages[-1]
            for client_addr in self.clients:
                if client_addr != sender_addr:
                    sender = ""
                    # not exit and not join
                    # format is 'User x left' and 'User x joined'
                    # check if first 4 characters are 'User' and last 4 characters are 'left'
                    # or first 4 characters are 'User' and last 5 characters are 'joined'
                    if message[:4] == "User" and (message[-4:] == "left" or message[-6:] == "joined"):
                        sender = ""
                    else:
                        sender = f"{self.clients[sender_addr]}: "
                    
                    try:
                        self.server_socket.sendto(f"{sender}{message}".encode(), client_addr)
                    except Exception as e:
                        print(f"Error broadcasting message: {e}")
    
    def accept_client(self, client_addr, message):
        name = message[5:]
        if name in self.clients.values():
            self.server_socket.sendto(b"Name already taken", client_addr)
            return False
        
        self.clients[client_addr] = name
        self.server_socket.sendto(b"Welcome", client_addr)
        self.messages.append((client_addr, f"User {name} joined"))
        self.broadcast()
        
        return True
    
    def close_client(self, client_addr):
        if client_addr in self.clients:
            self.messages.append((client_addr, f"User {self.clients[client_addr]} left"))
            del self.clients[client_addr]
            self.broadcast()
            return True
        return False
    
    def shutdown(self):
        shutdown_message = "server-shutdown"
        for client_addr in self.clients:
            self.server_socket.sendto(shutdown_message.encode(), client_addr)
        
        clients = list(self.clients.keys())
        for client_addr in clients:
            self.close_client(client_addr)

        self.server_socket.close()

    def get_clients_number(self):
        return len(self.clients)
    
    def run(self):
        try:
            print("Server is running...")
            while True:
                if not self.server_socket or self.server_socket.fileno() == -1:
                    continue

                readable, _, _ = select.select([self.server_socket], [], [], 1.0)
                
                if not readable:
                    continue
                
                try:
                    message, client_addr = self.server_socket.recvfrom(1024)
                    message = message.decode()
                    
                    if message[:4] == "join":
                        self.accept_client(client_addr, message)
                    elif message == "exit":
                        self.close_client(client_addr)
                    else:
                        self.messages.append((client_addr, message))
                        self.broadcast()
                except BlockingIOError:
                    continue
                
        except KeyboardInterrupt:
            print("Server shutting down...")
            self.shutdown()

class ClientUDP:
    def __init__(self, client_name, server_port):
        self.server_addr = socket.gethostbyname(socket.gethostname())
        self.server_port = server_port
        self.client_name = client_name
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.exit_run = threading.Event()
        self.exit_receive = threading.Event()
        
    def connect_server(self):
        self.client_socket.sendto(f"join:{self.client_name}".encode(), (self.server_addr, self.server_port))
        
        try:
            response, _ = self.client_socket.recvfrom(1024)
            if 'Welcome' in response.decode():
                print("Connected to the chatroom.")
                return True
            else:
                print("Failed to join the chatroom:", response.decode())
                return False
        except Exception as e:
            print(f"Connection error: {e}")
            return False
        
    def send(self, text):
        self.client_socket.sendto(text.encode(), (self.server_addr, self.server_port))
        
    def receive(self):
        while not self.exit_receive.is_set():
            try:
                data, _ = self.client_socket.recvfrom(1024)
                message = data.decode()
                if 'server-shutdown' in message:
                    print("Server is shutting down.")
                    self.exit_run.set()
                    self.exit_receive.set()
                    break
                else:
                    sys.stdout.write(f"\r{message}\n")
                    sys.stdout.flush()
                    sys.stdout.write(f"{self.client_name}: ")
                    sys.stdout.flush()
            except Exception as e:
                print(f"Error receiving message: {e}")
                break
    
    def run(self):
        if self.connect_server():
            receive_thread = threading.Thread(target=self.receive)
            receive_thread.start()
            
            try:
                while not self.exit_run.is_set():
                    message = input(f"{self.client_name}: ")
                    if message == 'exit':
                        self.send('exit')
                        self.exit_receive.set()
                        break
                    self.send(message)
            except KeyboardInterrupt:
                self.send('exit')
                self.exit_receive.set()
            finally:
                self.client_socket.close()