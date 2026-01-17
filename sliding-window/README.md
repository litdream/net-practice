# Sliding Window Protocol

This project implements a reliable data transmission protocol over UDP (an unreliable channel).
It simulates TCP-like behavior including connection establishment (SYN), data transfer, and connection termination (FIN).

## Features
- **Reliable File Transfer**: Transmits files over UDP.
- **Protocol Header**: 12-byte binary header with Sequence number, Ack number, Flags, and Window size.
- **Manual Segmentation**: Splits data into segments (Max 1012 bytes payload) to fit within the server's 1024-byte buffer.
- **Sliding Window**: Implements a sliding window mechanism for reliable data transfer.
- **Packet Loss Simulation**: Simulates packet loss for both incoming and outgoing packets (data, SYN, FIN, ACK).
- **Packet Duplication Simulation**: Simulates packet duplication for both incoming and outgoing packets.
- **Packet Delay Simulation**: Simulates variable network delay for both incoming and outgoing packets.
- **Packet Reordering Simulation**: Emerges as a natural consequence of variable packet delays.

## Protocol Specification
### Header Format (12 bytes)
```
  0                   1                   2                   3
  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |                        Sequence Number                        |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |                      Acknowledgment Number                    |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |             Flags             |           Window Size         |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```
- **Flags**: `SYN (0x01)`, `ACK (0x02)`, `FIN (0x04)`
- **Constraints**: 
    - `SERVER_BUFFER_SIZE`: 1024 bytes
    - `MAX_PAYLOAD_SIZE`: 1012 bytes

## Usage

### 1. Start the Server
The server listens on `0.0.0.0:9999` and writes received files to `data/<client_port>.in`.
```bash
python3 py/server.py
```

### 2. Run the Client
The client reads a file and sends it to the server.
```bash
python3 py/client.py <filename>
```

### 3. Verify
Compare the original file with the received file.
```bash
diff <filename> data/<client_port>.in
```

## Future Plans
- [x] Add packet loss/delay/duplication simulation to test reliability.
- [ ] Add packet corruption simulation.
- [ ] Implement Delayed ACK (RFC 1122) to reduce ACK traffic.

## Network Simulation
- **Packet Drop Probability**: Configurable via `DROP_PROBABILITY` in `py/shared.py` (default: 0.1).
- **Packet Duplication Probability**: Configurable via `DUPLICATE_PROBABILITY` in `py/shared.py` (default: 0.1).
- **Packet Delay Probability**: Configurable via `DELAY_PROBABILITY` in `py/shared.py` (default: 0.1).
- **Minimum/Maximum Delay**: Configurable via `MIN_DELAY` (default: 0.5s) and `MAX_DELAY` (default: 2.0s) in `py/shared.py`.
- **Packet Reordering**: Naturally occurs due to the variable packet delay simulation.

## Design Notes
### How TCP Handles Out-of-Order ACKs
A core principle of TCP that makes it resilient to network reordering is the use of **cumulative acknowledgments**. An ACK number does not just acknowledge a single packet; it acknowledges the successful receipt of all data bytes *up to* that sequence number.

This design gracefully handles out-of-order ACKs. For example:
1. A client sends packets {1, 2, 3, 4, 5, 6, 7, 8}.
2. The server processes them and sends back `ack(4)` and later `ack(8)`.
3. Due to network conditions, `ack(8)` arrives at the client first. The client sees this and knows that all data up to packet 7 has been received. It slides its window forward and cancels retransmission timers for packets 1-7.
4. Later, the delayed `ack(4)` arrives. The client's internal state already knows that data up to 7 is confirmed. Since `4` is less than `8`, this ACK provides old, redundant information.
5. The client simply **discards the late `ack(4)`**. It has no negative impact on the connection's state.

### Sequence Number Wrap-Around (The 4 GiB Limit)
Our protocol uses a 4-byte (32-bit) sequence number, which allows for 2^32 unique byte offsets. This imposes a theoretical file size limit of 4 GiB. In a real-world TCP implementation, this is not a hard limit because sequence numbers are designed to **wrap around** (from `2^32 - 1` back to `0`).

TCP handles this using two primary mechanisms:
1.  **The Sliding Window**: The sequence number space is treated like a circular clock face. A receiver only accepts packets that fall within its current "receive window"—a small arc on the clock face. This logic correctly handles the transition from high sequence numbers to low ones during a wrap-around and rejects most old duplicates.
2.  **Protection Against Wrapped Sequence numbers (PAWS)**: In very high-speed networks, an old packet from a previous "lap" around the clock could be delayed and arrive when its sequence number is valid again, leading to data corruption. The PAWS algorithm (RFC 1323) solves this. When the TCP Timestamps option is used, each packet is tagged with a timestamp. The receiver tracks the latest timestamp seen and will discard any packet with a valid sequence number but a stale (older) timestamp.

Our simulation implements the sliding window but not the PAWS algorithm, so for this project, the 4 GiB file size is a practical limit.
