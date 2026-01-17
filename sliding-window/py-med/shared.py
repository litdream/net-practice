import struct

# Protocol Constants
# Header format: SrcPort (2), DstPort (2), Sequence Number (4), Ack Number (4), Flags (2), Window Size (2)
# Total Header Size: 16 bytes
HEADER_FORMAT = "!HHIIHH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# Constraints
SERVER_BUFFER_SIZE = 1024
MAX_PAYLOAD_SIZE = SERVER_BUFFER_SIZE - HEADER_SIZE # 1008 bytes
WINDOW_SIZE = 5

# Flags
FLAG_SYN = 0x01
FLAG_ACK = 0x02
FLAG_FIN = 0x04

class Packet:
    def __init__(self, src_port, dst_port, seq, ack, flags, window, data=b""):
        self.src_port = src_port
        self.dst_port = dst_port
        self.seq = seq
        self.ack = ack
        self.flags = flags
        self.window = window
        self.data = data

    def pack(self):
        header = struct.pack(HEADER_FORMAT, self.src_port, self.dst_port, self.seq, self.ack, self.flags, self.window)
        return header + self.data

    @classmethod
    def unpack(cls, buffer):
        if len(buffer) < HEADER_SIZE:
            raise ValueError("Packet too short")
        
        header_data = buffer[:HEADER_SIZE]
        src_port, dst_port, seq, ack, flags, window = struct.unpack(HEADER_FORMAT, header_data)
        data = buffer[HEADER_SIZE:]
        
        return cls(src_port, dst_port, seq, ack, flags, window, data)

    def __repr__(self):
        return (f"Packet(src={self.src_port}, dst={self.dst_port}, seq={self.seq}, ack={self.ack}, "
                f"flags={self.flags:#04x}, window={self.window}, len={len(self.data)})")
