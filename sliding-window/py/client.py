import socket
import sys
import time
import select
from shared import Packet, FLAG_SYN, FLAG_ACK, FLAG_FIN, MAX_PAYLOAD_SIZE, SERVER_BUFFER_SIZE, WINDOW_SIZE

SERVER_IP = "127.0.0.1"
SERVER_PORT = 9999
TIMEOUT = 0.5  # Seconds

def setup_socket():
    """Creates and returns a non-blocking UDP socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    return sock

def read_file_chunks(filename):
    """Reads a file and splits it into chunks."""
    try:
        chunks = []
        with open(filename, "rb") as f:
            while True:
                chunk = f.read(MAX_PAYLOAD_SIZE)
                if not chunk:
                    break
                chunks.append(chunk)
        return chunks
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return None

def perform_handshake(sock, server_addr):
    """Performs the SYN/SYN-ACK handshake."""
    seq = 100
    syn_pkt = Packet(seq=seq, ack=0, flags=FLAG_SYN, window=1024)
    print("Sending SYN...")

    start_time = time.time()
    while True:
        sock.sendto(syn_pkt.pack(), server_addr)
        
        ready = select.select([sock], [], [], TIMEOUT)
        if ready[0]:
            try:
                data, _ = sock.recvfrom(SERVER_BUFFER_SIZE)
                pkt = Packet.unpack(data)
                if pkt.flags & (FLAG_SYN | FLAG_ACK):
                    print("Connection established.")
                    # The server's ACK is our starting sequence number for data
                    return pkt.ack
            except Exception:
                pass
        else: # Timeout
            print("Timeout waiting for SYN-ACK. Retrying...")

    return None # Should not be reached in happy path


def transmit_file(sock, server_addr, chunks, initial_seq):
    """Transmits the file chunks using a sliding window."""
    base_idx = 0
    next_idx = 0
    base_seq = initial_seq
    seq_window = {}
    last_ack_time = time.time()
    total_chunks = len(chunks)

    while base_idx < total_chunks:
        # Send packets while the window is not full
        while next_idx < total_chunks and next_idx < base_idx + WINDOW_SIZE:
            current_seq = base_seq
            if next_idx > base_idx:
                prev_chunk_len = len(chunks[next_idx - 1])
                current_seq = seq_window[next_idx - 1] + prev_chunk_len
            
            seq_window[next_idx] = current_seq
            
            chunk = chunks[next_idx]
            pkt = Packet(seq=current_seq, ack=0, flags=FLAG_ACK, window=1024, data=chunk)
            sock.sendto(pkt.pack(), server_addr)
            print(f"Sent Segment {next_idx + 1}/{total_chunks} (Seq={current_seq})")
            next_idx += 1
        
        # Check for ACKs
        ready = select.select([sock], [], [], 0.1)
        if ready[0]:
            try:
                data, _ = sock.recvfrom(SERVER_BUFFER_SIZE)
                ack_pkt = Packet.unpack(data)

                # Cumulative ACK: Slide window forward
                while base_idx < next_idx:
                    chunk_len = len(chunks[base_idx])
                    if ack_pkt.ack >= base_seq + chunk_len:
                        print(f"Acked Segment {base_idx + 1} (Ack={ack_pkt.ack})")
                        base_seq += chunk_len
                        base_idx += 1
                        last_ack_time = time.time()  # Reset timer on progress
                    else:
                        break
            except Exception:
                pass
        
        # Timeout Handling (Go-Back-N)
        if time.time() - last_ack_time > TIMEOUT:
            print("Timeout! Resending window...")
            next_idx = base_idx  # Reset to re-send from the base
            last_ack_time = time.time()

    print("File transmission complete.")
    return base_seq

def perform_teardown(sock, server_addr, final_seq):
    """Performs the FIN/FIN-ACK teardown."""
    fin_pkt = Packet(seq=final_seq, ack=0, flags=FLAG_FIN, window=1024)
    for _ in range(5):  # Retry up to 5 times
        print("Sending FIN...")
        sock.sendto(fin_pkt.pack(), server_addr)
        ready = select.select([sock], [], [], 0.5)
        if ready[0]:
            try:
                data, _ = sock.recvfrom(SERVER_BUFFER_SIZE)
                pkt = Packet.unpack(data)
                if pkt.flags & FLAG_ACK:
                    print("FIN ACKed.")
                    return
            except Exception:
                pass
    print("No FIN-ACK received.")

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <filename>")
        return

    filename = sys.argv[1]
    server_addr = (SERVER_IP, SERVER_PORT)
    
    chunks = read_file_chunks(filename)
    if chunks is None:
        return

    sock = setup_socket()
    
    try:
        start_seq = perform_handshake(sock, server_addr)
        if start_seq is not None:
            final_seq = transmit_file(sock, server_addr, chunks, start_seq)
            perform_teardown(sock, server_addr, final_seq)
    finally:
        sock.close()

if __name__ == "__main__":
    main()
