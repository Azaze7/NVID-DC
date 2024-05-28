###############
# NVID-DC #
# Server  # 
###############
import socket
import select
import pickle
import time
import rsa
from Crypto.Cipher import AES

# IP address and port for the server
server_ip = socket.gethostbyname(socket.gethostname())
port = 8888

# Print server details
print('Server IP is ' + server_ip + '\nPort ' + str(port) + ' is being used')
print('Press ctrl + c to exit out of the program\n')

### Make keys ###
# (pubkey, prikey) = rsa.newkeys(1024)

# Create a TCP socket
tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_server_socket.setblocking(0)

# Bind the socket to the server address and port
try:
    tcp_server_socket.bind((server_ip, port))
    is_connected = True
except OSError:
    print('Port ' + str(port) + ' is busy')
    exit()

# Listen for incoming connections
tcp_server_socket.listen(100)

# Lists to keep track of inputs, outputs, and clients
inputs = [tcp_server_socket]
outputs = []

#This is the list of Clients. We Need to Maintain this here!
clients = []
# History of all actions taken by the clients
history = []

# Dictionary to keep track of clients and their requests
client_request_dict = {}

# Parses the incoming message
def incoming_message_parse(incoming):
    tokens = []
    col_data = False
    currword = bytearray()
    
    for byte in incoming:
        if len(tokens) >= 3:
            col_data = True
        if byte != ord(':'):
            currword.append(byte)
        elif col_data:
            currword.append(byte)
        elif len(tokens) < 3:
            tokens.append(currword)
            currword = bytearray()
            
    tokens.append(currword)
    
    print(len(tokens))
    return tokens

# Looks if the message is a hello message
def check_for_hello(incoming):
    if incoming[0] == ord('h'):
        return True
    else:
        return False

# Function to write the serialized clients to a file
def write_clients_to_file(serialized_clients, file_name):
    with open(file_name, 'wb') as file:
        file.write(serialized_clients)

# Main server loop
while True:
    # pickles the client list to send over network
    serialized_clients = pickle.dumps(clients)

    # Use select to monitor sockets for readable, writable, or exceptional conditions
    readable, writable, exceptional = select.select(inputs, outputs, inputs)

    # Handle sockets with incoming data
    for sock in readable:
        # if server looks for incoming message
        if sock is tcp_server_socket:
            print('Server looking for a request')
            # Accept incoming connection
            client_socket, addr = tcp_server_socket.accept()
            client_socket.setblocking(0)
            inputs.append(client_socket)
            # Adds the new socket to the dict with an empty list that acts a queue
            client_request_dict.update({client_socket: []})
            # print('Received a connection from:', addr)
        else:
            # Receive message from client
            print("Incoming message from " + str(sock))
            message = sock.recv(50000)
            print(message)
            if message:
                # stores the message
                stored_client_list = client_request_dict.get(sock)
                stored_client_list.append(message)
                client_request_dict[sock] = stored_client_list
                if sock not in outputs:
                    outputs.append(sock)
                print('Got Message')       
            else:
                # Close the socket if no message is received
                if sock in outputs:
                    outputs.remove(sock)
                inputs.remove(sock)
                sock.close()
                del client_request_dict[sock]

    # Handle sockets with pending messages to send
    for sock in writable:
        # checks that the client is the the dict with message
        if sock in client_request_dict.keys():
            print('Completing request for ' + str(sock) + '\n')
            stored_client_list = client_request_dict.get(sock)
            # small check to remove if needed
            if len(stored_client_list) <= 0:
                inputs.remove(sock)
                outputs.remove(sock)
                del client_request_dict[sock]
                sock.close()
                continue
            message = stored_client_list[0]
            stored_client_list = stored_client_list[1:]
            client_request_dict[sock] = stored_client_list
            # Handle special messages from client
            # checks for hello message
            if check_for_hello(message):
                tokens = incoming_message_parse(message)
                hostname = tokens[1].decode()
                hostIP = tokens[2].decode()
                hostpub = tokens[3]
                pair = (hostname, hostIP, hostpub)
                hist_message = time.strftime("%H:%M:%S", time.localtime()) + ' : ' + hostname + ' with IP ' + hostIP + ' joined'
                history.append(hist_message)
                if pair not in clients:
                    clients.append(pair)
                sock.sendall(b'DONE')
            # checks for update history message
            elif 'updatehistory:' in message.decode('utf-8'):
                message = message.decode('utf-8')
                tokens = message.split(':')
                hist_message = time.strftime("%H:%M:%S", time.localtime()) + ' : ' + tokens[1]
                history.append(hist_message)
                sock.sendall(b'DONE')
            # checks for send list message
            elif message == b'sendlist':
                # Send the serialized client list to the client
                sock.sendall(serialized_clients)
            # checks for send history
            elif message == b'sendhistory':
                # Send the a list of messages the client has received
                sock.sendall(pickle.dumps(history))
            # checks for update name message
            elif 'updatename' in message.decode('utf-8'):
                message = message.decode('utf-8')
                tokens = message.split(':')
                new_name = tokens[1]
                client_ip = tokens[2]
                for client in clients:
                    if client[1] == client_ip:
                        hist_message = time.strftime("%H:%M:%S", time.localtime()) + ' : ' + client[0] + ' changed name to ' + new_name
                        history.append(hist_message)
                        clients.remove(client)
                        clients.append((new_name, client_ip, client[2]))
                        break
                sock.sendall(b'DONE')
            # checks for leave message
            elif 'sendleave' in message.decode('utf-8'):
                # Remove client from the list
                message = message.decode('utf-8')
                tokens = message.split(':')
                hostname = tokens[1]
                hostIP = tokens[2]
                pair = ''
                for client in clients:
                    if client[0] == hostname and client[1] == hostIP:
                        pair = client
                        break 
                # if pair in clients:
                clients.remove(pair)
                del client_request_dict[sock]
                inputs.remove(sock)
                outputs.remove(sock)
                history.append(time.strftime("%H:%M:%S", time.localtime()) + ' : Host ' + hostname + ' with IP ' + hostIP + ' disconnected')
                sock.sendall(b'DONE')
                print('Client ' + str(sock) + ' removed.')
            print('Message has been sent to client\n')
        # if sock has no message it is removed
        else:
            if sock in outputs:
                print("removing")
                outputs.remove(sock)

    # Handle exceptional conditions
    for sock in exceptional:
        inputs.remove(sock)
        if sock in outputs:
            outputs.remove(sock)
        sock.close()
        del client_request_dict[sock]

# Close the server socket
tcp_server_socket.close()