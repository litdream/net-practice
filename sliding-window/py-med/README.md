# Network Mediator Project (py-med)

This project separates network simulation logic from the endpoints (Client/Server) by introducing a **Net Daemon** (Mediator). This creates a more realistic environment where the network itself is unreliable, rather than the endpoints simulating unreliability.

## Architecture

```
[ Client ] <---> [ Net Daemon ] <---> [ Server ]
(Port A)         (Port Net)           (Port B)
```

- **Client/Server**: Implementing "pure" Sliding Window Protocol logic. They assume they are talking to the network, which might lose packets. They do NOT simulate errors themselves.
- **Net Daemon**: Acts as a router/gateway. It receives packets, applies **Packet Loss, Duplication, and Delay**, and forwards them to the destination specified in the protocol header.

## Protocol Specification (v2)

To facilitate routing by the Net Daemon, we add **Source Port** and **Destination Port** to our custom header.

### Header Format (16 bytes)
```
  0                   1                   2                   3
  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |          Source Port          |       Destination Port        |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |                        Sequence Number                        |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |                      Acknowledgment Number                    |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |             Flags             |           Window Size         |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### Fields
- **Source Port (16-bit)**: The virtual port of the sender (e.g., Client: 43112, Server: 9999).
- **Destination Port (16-bit)**: The virtual port of the receiver.
- **Sequence Number (32-bit)**: Byte offset of the data.
- **Ack Number (32-bit)**: Next expected byte sequence.
- **Flags (16-bit)**: `SYN`, `ACK`, `FIN`.
- **Window Size (16-bit)**: Receiver window size.

## Component Roles

### 1. Net Daemon (`net.py`)
- **Listen Address**: `0.0.0.0:8000` (Default)
- **Functions**:
    - Maintains a **Mapping Table**: `Virtual Port -> Physical Address (IP, Port)`.
    - **Registration**:
        - Implicit: When a packet arrives from `IP:Port` with `SrcPort=X` in header, update mapping `X -> IP:Port`.
        - Explicit (Optional): Server sends a special packet to register immediately on startup.
    - **Forwarding**:
        - Packet arrives from A intended for B.
        - Lookup B in Mapping Table.
        - If B exists:
            - Apply **Network Simulation** (Random Drop, Duplicate, Delay).
            - Send to B's Physical Address.
        - If B unknown: Drop packet (or log error).

### 2. Server (`server.py`)
- **Physical Port**: `9999` (binds to this).
- **Virtual Port**: `9999` (in Header).
- **Behavior**:
    - Starts up and binds to UDP 9999.
    - Sends a "Hello" or Registration packet to Net Daemon so Net knows where it is.
    - Listens for packets.
    - Processes packets (SYN, Data, FIN) normally.
    - Sends ACKs to **Net Daemon Address**, with `DstPort` set to Client's Virtual Port.

### 3. Client (`client.py`)
- **Physical Port**: dynamic or fixed (e.g., `43112`).
- **Virtual Port**: matches Physical Port.
- **Behavior**:
    - Reads file to transfer.
    - Sends packets to **Net Daemon Address**.
    - Header sets `SrcPort=MyPort`, `DstPort=9999`.
    - Handles Retransmissions (Go-Back-N or Selective Repeat) based on timeouts.
    - Does **NOTICE** packet loss/delays (since Net causes them), but does not generate them.

## Usage

1. **Start Net Daemon**
   ```bash
   python3 py-med/net.py --port 8000
   ```

2. **Start Server**
   ```bash
   # Server listens on 9999, tells Net (on 8000) it is there
   python3 py-med/server.py --port 9999 --net-host localhost --net-port 8000
   ```

3. **Start Client**
   ```bash
   # Client sends file to Server(9999) via Net(8000)
   python3 py-med/client.py <filename> --net-host localhost --net-port 8000 --server-port 9999
   ```

## Simulation Parameters
Managed entirely within `net.py`:
- `DROP_PROBABILITY`
- `DUPLICATE_PROBABILITY`
- `DELAY_PROBABILITY` / `MIN_DELAY` / `MAX_DELAY`
