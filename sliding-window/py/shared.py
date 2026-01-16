import struct

# Protocol Constants
# Header format: Sequence Number (4), Ack Number (4), Flags (2), Window Size (2)
# Total Header Size: 12 bytes
HEADER_FORMAT = "!IIHH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# Constraints
SERVER_BUFFER_SIZE = 1024
MAX_PAYLOAD_SIZE = SERVER_BUFFER_SIZE - HEADER_SIZE # 1012 bytes
WINDOW_SIZE = 5

# Simulation parameters
DROP_PROBABILITY = 0.1  # 10% packet drop probability
DUPLICATE_PROBABILITY = 0.1 # 10% packet duplication probability
DELAY_PROBABILITY = 0.1     # 10% packet delay probability
MIN_DELAY = 0.5             # Minimum delay in seconds
MAX_DELAY = 2.0             # Maximum delay in seconds

# Flags
FLAG_SYN = 0x01
FLAG_ACK = 0x02
FLAG_FIN = 0x04

class Packet:
    def __init__(self, seq, ack, flags, window, data=b""):
        self.seq = seq
        self.ack = ack
        self.flags = flags
        self.window = window
        self.data = data

    def pack(self):
        header = struct.pack(HEADER_FORMAT, self.seq, self.ack, self.flags, self.window)
        return header + self.data

    @classmethod
    def unpack(cls, buffer):
        if len(buffer) < HEADER_SIZE:
            raise ValueError("Packet too short")
        
        header_data = buffer[:HEADER_SIZE]
        seq, ack, flags, window = struct.unpack(HEADER_FORMAT, header_data)
        data = buffer[HEADER_SIZE:]
        
        return cls(seq, ack, flags, window, data)

    def __repr__(self):
        return (f"Packet(seq={self.seq}, ack={self.ack}, flags={self.flags:#04x}, "
                f"window={self.window}, len={len(self.data)})")
