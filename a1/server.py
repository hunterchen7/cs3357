import socket
import threading
import time
import os
from urllib.parse import unquote, parse_qs

class Server:
    def __init__(self, addr, port, timeout):
        """
        Initializes the server with the specified address, port, and timeout.
        Sets up the server socket and binds it to the address and port.
        Initializes the sessions dictionary to manage client sessions.
        """
        self.addr = addr
        self.port = port
        self.timeout = timeout
        self.sessions = {}    # Maps client addresses to their names
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.addr, self.port))
            self.server_socket.listen(5)
            print(f"Server started at {self.addr}:{self.port}")
        except Exception as e:
            print(f"Failed to bind server on {self.addr}:{self.port}: {e}")
            self.server_socket.close()
            raise e
        self.running = False
        self.last_activity = time.time()
        self.lock = threading.Lock()    # To manage access to sessions

    def start_server(self):
        """
        Starts the server to accept incoming connections.
        Handles each client connection in a separate thread.
        Monitors server activity and shuts down gracefully after a period of inactivity.
        """
        self.running = True
        while self.running:
            # Set timeout for accept based on remaining time before shutdown
            time_since_last = time.time() - self.last_activity
            remaining_time = self.timeout - time_since_last
            if remaining_time <= 0:
                print("Server timeout reached. Shutting down.")
                self.stop_server()
                break
            self.server_socket.settimeout(remaining_time)
            try:
                client_socket, client_address = self.server_socket.accept()
                with self.lock:
                    self.last_activity = time.time()
                print(f"Accepted connection from {client_address}")
                client_thread = threading.Thread(target=self.handle_request, args=(client_socket, client_address))
                client_thread.daemon = True
                client_thread.start()
            except socket.timeout:
                # No new connection within the remaining_time
                continue
            except Exception as e:
                print(f"Error accepting connections: {e}")
                continue

    def stop_server(self):
        """
        Stops the server by closing the server socket and terminating the server loop.
        """
        self.running = False
        try:
            self.server_socket.close()
            print("Server socket closed.")
        except Exception as e:
            print(f"Error closing server socket: {e}")

    def parse_request(self, request_data):
        """
        Parses raw HTTP request data into request line, headers, and body.
        Returns a tuple of (request_line, headers_dict, body).
        """
        try:
            # Decode bytes to string
            request_text = request_data.decode('utf-8')
            # Split request into lines
            lines = request_text.split("\r\n")
            # Extract request line
            request_line = lines[0]
            # Initialize headers dictionary
            headers = {}
            body = ""
            # Iterate over headers
            i = 1
            while i < len(lines):
                line = lines[i]
                if line == "":
                    # End of headers
                    i += 1
                    break
                parts = line.split(":", 1)
                if len(parts) == 2:
                    header_key = parts[0].strip()
                    header_value = parts[1].strip()
                    headers[header_key] = header_value
                i += 1
            # The rest is body
            body = "\r\n".join(lines[i:])
            return request_line, headers, body
        except Exception as e:
            print(f"Error parsing request: {e}")
            return None, {}, ""

    def handle_request(self, client_socket, client_address):
        """
        Handles incoming HTTP requests from a client.
        Determines the HTTP method and invokes the appropriate handler.
        Closes the client socket after processing the request.
        """
        try:
            # Receive data from client
            request_data = b""
            client_socket.settimeout(5)    # Timeout for receiving data
            while True:
                try:
                    chunk = client_socket.recv(1024)
                    if not chunk:
                        break
                    request_data += chunk
                    if b"\r\n\r\n" in request_data:
                        # End of headers
                        break
                except socket.timeout:
                    break
            if not request_data:
                print(f"No data received from {client_address}")
                client_socket.close()
                return
            # Parse the request
            request_line, headers, body = self.parse_request(request_data)
            if not request_line:
                print(f"Malformed request from {client_address}")
                client_socket.close()
                return
            # Extract method, path, and version
            parts = request_line.split()
            if len(parts) != 3:
                print(f"Invalid request line from {client_address}: {request_line}")
                client_socket.close()
                return
            method, path, version = parts
            # Default to index.html if path is '/'
            if path == "/":
                path = "/index.html"
            # URL decode the path
            path = unquote(path)
            # Handle the request based on the method
            if method.upper() == "GET":
                self.handle_get_request(client_socket, path, client_address)
            elif method.upper() == "POST":
                self.handle_post_request(client_socket, path, headers, body, client_address)
            else:
                self.handle_unsupported_method(client_socket, method)
        except Exception as e:
            print(f"Error handling request from {client_address}: {e}")
        finally:
            client_socket.close()

    def handle_get_request(self, client_socket, file_path, client_address):
        try:
            # If the requested path is "/", serve "index.html"
            if file_path == "/":
                file_path = "/index.html"

            # Construct the full file path
            assets_dir = os.path.join(os.getcwd(), "assets")
            full_path = os.path.join(assets_dir, file_path.lstrip("/"))

            # Check if the file exists
            if not os.path.isfile(full_path):
                # File not found
                response_body = "<h1>404 Not Found</h1>".encode('utf-8')
                response = (
                    "HTTP/1.1 404 Not Found\r\n"
                    f"Content-Length: {len(response_body)}\r\n"
                    "Content-Type: text/html\r\n"
                    "\r\n"
                ).encode('utf-8') + response_body
                client_socket.sendall(response)
                return

            # Read the file content
            with open(full_path, 'rb') as f:
                content = f.read()

            # If it's an HTML file, replace {{name}} with the client's name
            if full_path.endswith(".html"):
                content = content.decode('utf-8')
                with self.lock:
                    # Use client_address[0] as the session key
                    name = self.sessions.get(client_address[0], "Guest")
                    # Debug: print retrieved session data
                    print(f"Retrieved session for {client_address[0]}: {name}")
                content = content.replace("{{name}}", name)
                content = content.encode('utf-8')

            # Prepare and send HTTP response
            response_headers = (
                "HTTP/1.1 200 OK\r\n"
                f"Content-Length: {len(content)}\r\n"
                "Content-Type: text/html\r\n"
                "\r\n"
            ).encode('utf-8')
            client_socket.sendall(response_headers + content)

        except Exception as e:
            print(f"Error handling GET request for {file_path} from {client_address}: {e}")

    def handle_post_request(self, client_socket, path, headers, body, client_address):
        try:
            if path != "/change_name":
                # Unsupported POST path
                response_body = "<h1>404 Not Found</h1>".encode('utf-8')
                response = (
                    "HTTP/1.1 404 Not Found\r\n"
                    f"Content-Length: {len(response_body)}\r\n"
                    "Content-Type: text/html\r\n"
                    "\r\n"
                ).encode('utf-8') + response_body
                client_socket.sendall(response)
                return

            # Parse the form data
            content_length = int(headers.get("Content-Length", 0))
            while len(body.encode('utf-8')) < content_length:
                additional_data = client_socket.recv(1024).decode('utf-8')
                if not additional_data:
                    break
                body += additional_data

            form_data = parse_qs(body)
            name = form_data.get("name", ["Guest"])[0]

            # Use only the IP address (client_address[0]) as the session key
            with self.lock:
                self.sessions[client_address[0]] = name  # Update session

            # Debug: print session data after update
            print(f"Updated session: {self.sessions}")

            # Prepare response
            response_body = b"Name updated"
            response = (
                "HTTP/1.1 200 OK\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Content-Type: text/plain\r\n"
                "\r\n"
            ).encode('utf-8') + response_body
            client_socket.sendall(response)

        except Exception as e:
            print(f"Error handling POST request for {path} from {client_address}: {e}")



    def handle_unsupported_method(self, client_socket, method):
        """
        Handles HTTP methods that are not supported by the server.
        Sends a 405 Method Not Allowed response.
        """
        try:
            response_body = f"<h1>405 Method Not Allowed</h1><p>The method {method} is not allowed.</p>".encode('utf-8')
            response = (
                "HTTP/1.1 405 Method Not Allowed\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Content-Type: text/html\r\n"
                "Allow: GET, POST\r\n"
                "\r\n"
            ).encode('utf-8') + response_body
            client_socket.sendall(response)
        except Exception as e:
            print(f"Error handling unsupported method {method}: {e}")
