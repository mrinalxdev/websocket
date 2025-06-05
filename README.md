# WebSocket Chat Application
### Overview
This is a simple WebSocket-based chat application implemented in Python, following the RFC 6455 WebSocket protocol. It allows multiple clients to connect to a server, send messages, and receive broadcasts in real-time. The codebase includes frame encoding/decoding, server and client implementations, and a basic chat interface via the console.

What have I done till now :

- WebSocket Protocol: Compliant with RFC 6455 for handshake and frame handling.
- Multi-Client Support: Server manages multiple clients using threading.
- Message Broadcasting: Messages from one client are sent to all other connected clients.
- Control Frames: Supports ping/pong and close frames for connection management.
- Simple Interface: Clients interact via console input; server runs in the background.
- Graceful Shutdown: Handles disconnections and server termination cleanly.

What needs to be added :

- [ ] secure communication
- [ ] PM messaging
- [ ] Type indications

### Libraries I have used and their specific work

- socket: For TCP socket communication.
- threading: For handling multiple clients concurrently.
- hashlib: For SHA-1 hashing during WebSocket handshake.
- base64: For encoding/decoding WebSocket keys.
- struct: For packing/unpacking frame data.
- select: For non-blocking socket reads.
- json: Included but not used (potential for future extensions).
- time: For generating masking keys and timing.
- sys: For command-line argument parsing.

There is no external libraries used but to ensure you can run this command
```bash
uv sync
```

for running the project

1. For Server part
```bash
uv run main.py server
```

2. For client on different terminal
```bash
uv run main.py client <username>
```

### Here is the full breakdown 

Usage
The application can run in two modes: server or client, controlled via command-line arguments.
Running the Server

Command: 
```bash
uv run main.py server
```

- Description: Starts a WebSocket server on `127.0.0.1:8000`.
- Behavior:
    1. Listens for incoming client connections.
    2. Performs WebSocket handshake per RFC 6455.
    3. Accepts a username as the first message from each client.
    4. Broadcasts join/leave messages and chat content to all clients.
    5. Runs until interrupted (e.g., Ctrl+C), then shuts down gracefully.


Output: Prints "WebSocket server listening on 127.0.0.1:8000" on start.

- Description: Connects to the server at 127.0.0.1:8000 with the specified username.
- Behavior:
    1. Performs WebSocket handshake.
    2. Sends the username as the first message.
    3. Receives and displays broadcast messages from the server.
    4. Accepts console input for sending messages.
    5. Type /exit to disconnect gracefully.


Output: Displays received messages and a >  prompt for input.

Example

1. Open a terminal and start the server:
```bash
uv run main.py server
```

2. Output: WebSocket server listening on 127.0.0.1:8000
Open another terminal and start a client :
```bash
uv run main.py client <your name>
```


3. Output: Server broadcasts "X joined the chat" to all clients.
Open a third terminal for another client :
```bash
uv run main.py client <your second name>
```

Output: Server broadcasts "Second X joined the chat".

4. Type messages in either client terminal (e.g., "Hello, X!"):
Message appears in all other clients’ terminals.


5. Type /exit in a client to disconnect:
Server broadcasts " has left the chat".

### Code Structure

1. WebSocketFrame Class:
Handles frame encoding/decoding per RFC 6455.
Supports opcodes: text (0x1), close (0x8), ping (0x9), pong (0xA).
create_frame: Builds masked frames for sending.
parse_frame: Decodes incoming frames, handles masking.


2. WebSocketServer Class:
Manages server-side logic: binds to host/port, accepts clients.
Performs handshake, tracks clients (socket: username).
Broadcasts messages; handles ping/pong and close frames.
Methods: start, stop, broadcast, close_client.


4. WebSocketClient Class:
Connects to the server, performs handshake.
Sends username and chat messages; receives broadcasts.
Methods: connect, send, receive, close.


5. Chat Application:
run_chat_server: Runs the server in a thread.
run_chat_client: Runs the client, handles input/output.
Main block parses arguments to launch server or client.



### How It Works

1. Handshake:
Client sends HTTP GET with WebSocket headers (e.g., Sec-WebSocket-Key).
Server responds with HTTP 101, computed Sec-WebSocket-Accept key.


2. Framing:
Messages are sent as WebSocket frames (FIN bit, opcode, payload).
Clients mask payloads; server unmasks them.


3. Communication:
Server broadcasts each client’s messages to others.
Supports control frames (close, ping/pong) for connection health.


4. Termination:
Clients send close frames or use /exit.
Server closes connections and shuts down on interrupt.



### These things needs to be done ASAP for resume worthy like project

- Security: No encryption (e.g., WSS); runs over plain TCP.
- Masking: Server doesn’t strictly enforce client masking (RFC 6455 requirement).
- Scalability: Thread-per-client model may not scale for many users.
- Error Handling: Basic; lacks detailed logging or robust frame validation.
- Port: Hardcoded to 8000; no configuration option.

### Things I am planning rn to make it a good OSS project

- Add WSS (WebSocket Secure) with TLS for encryption.
- Enforce client-side masking on the server.
- Use async I/O (e.g., asyncio) for better scalability.
- Add configuration for host/port via arguments or a config file.
- Improve error handling with logging and user feedback.
- Support JSON for structured messages (e.g., timestamps, user roles).

