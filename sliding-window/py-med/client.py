import socket
import argparse
import time
import select
import sys
import random
from shared import Packet, HEADER_SIZE, SERVER_BUFFER_SIZE, MAX_PAYLOAD_SIZE, FLAG_SYN, FLAG_ACK, FLAG_FIN, WINDOW_SIZE

TIMEOUT = 0.5

class Client:
    def __init__(self, filename, net_host, net_port, server_port):
        self.filename = filename
        self.net_addr = (net_host, net_port)
        self.server_port = server_port
        
        # Pick a random source port (or let OS pick, but we need it for header)
        # We can't easily ask OS for ephemeral port unless we bind 0. 
        # But we also need to keep it consistent.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", 0)) # Bind to ephemeral
        self.port = self.sock.getsockname()[1] 
        self.sock.setblocking(False)
        
        print(f"Client started on port {self.port}")

    def send_to_net(self, pkt):
        self.sock.sendto(pkt.pack(), self.net_addr)

    def wait_for_packet(self, timeout=TIMEOUT):
        ready = select.select([self.sock], [], [], timeout)
        if ready[0]:
            try:
                data, _ = self.sock.recvfrom(SERVER_BUFFER_SIZE)
                return Packet.unpack(data)
            except Exception:
                pass
        return None

    def perform_handshake(self):
        print("Sending SYN...")
        seq = 100
        syn_pkt = Packet(src_port=self.port, dst_port=self.server_port, seq=seq, ack=0, 
                         flags=FLAG_SYN, window=1024)
        
        start_time = time.time()
        while time.time() - start_time < 10: # 10s total handshake timeout
            self.send_to_net(syn_pkt)
            
            resp = self.wait_for_packet(TIMEOUT)
            if resp and (resp.flags & (FLAG_SYN | FLAG_ACK)) and resp.ack == seq + 1:
                print("Connection established.")
                return resp.ack
            
            print("Timeout waiting for SYN-ACK. Retrying...")
        
        raise TimeoutError("Handshake failed")

    def perform_teardown(self, final_seq):
        print("Sending FIN...")
        fin_pkt = Packet(src_port=self.port, dst_port=self.server_port, seq=final_seq, ack=0, 
                         flags=FLAG_FIN, window=1024)
        
        for _ in range(5):
            self.send_to_net(fin_pkt)
            resp = self.wait_for_packet(TIMEOUT)
            if resp and (resp.flags & FLAG_ACK) and resp.ack == final_seq + 1:
                print("FIN ACKed.")
                return
        print("No FIN-ACK received.")

    def read_file_chunks(self):
        chunks = []
        try:
            with open(self.filename, "rb") as f:
                while True:
                    chunk = f.read(MAX_PAYLOAD_SIZE)
                    if not chunk:
                        break
                    chunks.append(chunk)
            return chunks
        except FileNotFoundError:
            print(f"Error: File {self.filename} not found")
            return None

    def transmit_file(self, start_seq):
        chunks = self.read_file_chunks()
        if chunks is None: return

        base_idx = 0
        next_idx = 0
        base_seq = start_seq
        seq_window = {} # map index -> seq
        total_chunks = len(chunks)
        last_ack_time = time.time()

        # Pre-calculate sequences to avoid complexity
        current_seq = start_seq
        for i in range(total_chunks):
            seq_window[i] = current_seq
            current_seq += len(chunks[i])

        while base_idx < total_chunks:
            # Send
            while next_idx < total_chunks and next_idx < base_idx + WINDOW_SIZE:
                chunk = chunks[next_idx]
                seq = seq_window[next_idx]
                pkt = Packet(src_port=self.port, dst_port=self.server_port, seq=seq, ack=0,
                             flags=FLAG_ACK, window=1024, data=chunk)
                self.send_to_net(pkt)
                print(f"Sent Segment {next_idx + 1}/{total_chunks} (Seq={seq})")
                next_idx += 1

            # recv
            resp = self.wait_for_packet(0.05) # fast poll
            if resp and (resp.flags & FLAG_ACK):
                # Check if this ACK moves base forward
                # valid if ack > base_seq
                if resp.ack > base_seq:
                     print(f"Acked up to {resp.ack}")
                     # Move base_idx forward
                     while base_idx < len(chunks):
                         chunk_end_seq = seq_window[base_idx] + len(chunks[base_idx])
                         if resp.ack >= chunk_end_seq:
                             base_idx += 1
                             base_seq = chunk_end_seq
                             last_ack_time = time.time()
                         else:
                             break
            
            # Timeout
            if time.time() - last_ack_time > TIMEOUT:
                print("Timeout! Resending window...")
                next_idx = base_idx # Go-back-N
                last_ack_time = time.time()

        print("File transmission complete.")
        return base_seq

    def run(self):
        try:
            start_seq = self.perform_handshake()
            final_seq = self.transmit_file(start_seq)
            self.perform_teardown(final_seq)
        finally:
            self.sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Client (py-med)")
    parser.add_argument("filename", help="File to transfer")
    parser.add_argument("--net-host", type=str, default="127.0.0.1", help="Net Daemon Host")
    parser.add_argument("--net-port", type=int, default=8000, help="Net Daemon Port")
    parser.add_argument("--server-port", type=int, default=9999, help="Server Port")
    args = parser.parse_args()

    client = Client(args.filename, args.net_host, args.net_port, args.server_port)
    client.run()
