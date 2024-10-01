import socket, threading, time
from server import Server
addr = '127.0.0.1'
port = 8080

def test_1():# Test 1: Check if the server is running by connecting to it
    with socket.create_connection((addr, port)) as client_socket:
        cond = client_socket is not None
    if cond:print("Test 1 passed")
    else:print("Test 1 failed")

def test_2():# Test 2: Test a simple GET request
    with socket.create_connection((addr, port)) as client_socket:
        client_socket.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        response = client_socket.recv(4096).decode()
        cond = "200 OK" in response and "Hello" in response
    if cond:print("Test 2 passed")
    else:print("Test 2 failed")

def test_3():# Test 3: Test a request for a nonexistent file
    with socket.create_connection((addr, port)) as client_socket:
        client_socket.sendall(b"GET /nonexistent.html HTTP/1.1\r\nHost: localhost\r\n\r\n")
        response = client_socket.recv(4096).decode()
        cond = "404 Not Found" in response
    if cond:print("Test 3 passed")
    else:print("Test 3 failed")

def test_4():# Test 4: Test a simple POST request
    with socket.create_connection((addr, port)) as client_socket:
        client_socket.sendall(b"POST /change_name HTTP/1.1\r\nHost: localhost\r\nContent-Length: 9\r\n\r\nname=Alice")
        response = client_socket.recv(4096).decode()
    with socket.create_connection((addr, port)) as client_socket:
        client_socket.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        response = client_socket.recv(4096).decode()
        cond = "200 OK" in response and "Alice" in response
    if cond:print("Test 4 passed")
    else:print("Test 4 failed")

if __name__ == "__main__":
    try:
        server = Server(addr, port, 5)
        server_thread = threading.Thread(target=server.start_server)
        server_thread.start()
        time.sleep(1)
    except Exception as e:
        print(e)
    test_1()
    test_2()
    test_3()
    test_4()
    try:
        server.stop_server()
        server_thread.join()
    except Exception:pass