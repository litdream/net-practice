import socket
import os
import random
import time
from shared import (
    Packet, FLAG_ACK, HEADER_SIZE, FLAG_SYN, FLAG_FIN,
    SERVER_BUFFER_SIZE, DROP_PROBABILITY, DUPLICATE_PROBABILITY,
    DELAY_PROBABILITY, MIN_DELAY, MAX_DELAY
)

SERVER_IP = "0.0.0.0"
SERVER_PORT = 9999
BUFFER_SIZE = SERVER_BUFFER_SIZE
DATA_DIR = "data"

def setup_socket(ip, port):
    """Creates, configures, and binds a UDP socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((ip, port))
    sock.setblocking(False) # Make socket non-blocking
    print(f"Server listening on {ip}:{port}")
    return sock

def send_packet(sock, pkt, addr, delayed_packets_buffer, description=""): # New helper for sending packets
    if random.random() < DELAY_PROBABILITY:
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        deliver_at = time.time() + delay
        delayed_packets_buffer.append((deliver_at, pkt, addr, description))
        print(f"[{addr}] Simulating {description} packet delay for {delay:.2f}s. Will deliver at {deliver_at:.2f}")
    else:
        sock.sendto(pkt.pack(), addr)
        print(f"[{addr}] Sent {description} packet immediately.")

def handle_syn(sock, pkt, addr, state, delayed_packets_buffer):
    """Handles a SYN packet to initiate a connection."""
    client_port = addr[1]
    output_file = f"{DATA_DIR}/{client_port}.in"
    print(f"[{addr}] New session. Writing to {output_file}")
    with open(output_file, "wb") as f:
        pass  # Truncate/Create
    
    resp_flags = FLAG_ACK | FLAG_SYN
    state["expected_seq"] = pkt.seq + 1
    state["initialized"] = True
    
    ack_pkt = Packet(seq=0, ack=state["expected_seq"], flags=resp_flags, window=1024)
    if random.random() < DROP_PROBABILITY:
        print(f"[{addr}] Simulating ACK packet drop for SYN-ACK.")
    else:
        send_packet(sock, ack_pkt, addr, delayed_packets_buffer, "SYN-ACK")
        if random.random() < DUPLICATE_PROBABILITY:
            print(f"[{addr}] Simulating ACK packet duplication for SYN-ACK.")
            send_packet(sock, ack_pkt, addr, delayed_packets_buffer, "SYN-ACK (duplicate)")

def handle_fin(sock, pkt, addr, state, client_id, client_states, delayed_packets_buffer):
    """Handles a FIN packet to terminate a connection."""
    if pkt.seq == state["expected_seq"]:
        print(f"[{addr}] Session finished.")
        resp_flags = FLAG_ACK | FLAG_FIN
        state["expected_seq"] += 1
        
        ack_pkt = Packet(seq=0, ack=state["expected_seq"], flags=resp_flags, window=1024)
        if random.random() < DROP_PROBABILITY:
            print(f"[{addr}] Simulating ACK packet drop for FIN-ACK.")
        else:
            send_packet(sock, ack_pkt, addr, delayed_packets_buffer, "FIN-ACK")
            if random.random() < DUPLICATE_PROBABILITY:
                print(f"[{addr}] Simulating ACK packet duplication for FIN-ACK.")
                send_packet(sock, ack_pkt, addr, delayed_packets_buffer, "FIN-ACK (duplicate)")
        del client_states[client_id]  # Clean up state
    else:
        # Out of order FIN, re-ack the expected sequence
        ack_pkt = Packet(seq=0, ack=state["expected_seq"], flags=FLAG_ACK, window=1024)
        if random.random() < DROP_PROBABILITY:
            print(f"[{addr}] Simulating ACK packet drop for out-of-order FIN-ACK.")
        else:
            send_packet(sock, ack_pkt, addr, delayed_packets_buffer, "FIN-ACK (out-of-order)")
            if random.random() < DUPLICATE_PROBABILITY:
                print(f"[{addr}] Simulating ACK packet duplication for out-of-order FIN-ACK.")
                send_packet(sock, ack_pkt, addr, delayed_packets_buffer, "FIN-ACK (out-of-order, duplicate)")


def handle_data(sock, pkt, addr, state, delayed_packets_buffer):
    """Handles a data packet."""
    output_file = f"{DATA_DIR}/{addr[1]}.in"
    if pkt.seq == state["expected_seq"]:
        if pkt.data:
            with open(output_file, "ab") as f:
                f.write(pkt.data)
            state["expected_seq"] += len(pkt.data)
    else:
        print(f"[{addr}] Out-of-order! Got {pkt.seq}, Expected {state['expected_seq']}")

    # Cumulative ACK (Always send what we expect next)
    ack_pkt = Packet(
        seq=0,
        ack=state["expected_seq"],
        flags=FLAG_ACK,
        window=1024
    )
    if random.random() < DROP_PROBABILITY:
        print(f"[{addr}] Simulating ACK packet drop for data ACK.")
    else:
        send_packet(sock, ack_pkt, addr, delayed_packets_buffer, "Data ACK")
        if random.random() < DUPLICATE_PROBABILITY:
            print(f"[{addr}] Simulating ACK packet duplication for data ACK.")
            send_packet(sock, ack_pkt, addr, delayed_packets_buffer, "Data ACK (duplicate)")

def process_packet(sock, data, addr, client_states, delayed_packets_buffer):
    """Processes a received packet and delegates to the appropriate handler."""
    try:
        if random.random() < DROP_PROBABILITY:
            print(f"[{addr}] Simulating packet drop for incoming packet.")
            return
        
        # Simulate incoming packet delay
        if random.random() < DELAY_PROBABILITY:
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            deliver_at = time.time() + delay
            delayed_packets_buffer.append((deliver_at, Packet.unpack(data), addr, "Incoming"))
            print(f"[{addr}] Simulating incoming packet delay for {delay:.2f}s. Will process at {deliver_at:.2f}")
            return
        pkt = Packet.unpack(data)
        client_id = f"{addr[0]}_{addr[1]}"

        if client_id not in client_states:
            client_states[client_id] = {"expected_seq": 0, "initialized": False}
        
        state = client_states[client_id]

        if pkt.flags & FLAG_SYN:
            handle_syn(sock, pkt, addr, state, delayed_packets_buffer)
            return

        if not state["initialized"]:
            # Ignore non-SYN packets if not initialized
            return

        if pkt.flags & FLAG_FIN:
            handle_fin(sock, pkt, addr, state, client_id, client_states, delayed_packets_buffer)
        else:
            handle_data(sock, pkt, addr, state, delayed_packets_buffer)

        # Simulate packet duplication
        if random.random() < DUPLICATE_PROBABILITY:
            print(f"[{addr}] Simulating packet duplication for incoming packet.")
            if pkt.flags & FLAG_FIN:
                handle_fin(sock, pkt, addr, state, client_id, client_states, delayed_packets_buffer)
            else:
                handle_data(sock, pkt, addr, state, delayed_packets_buffer)

    except Exception as e:
        print(f"Error processing packet from {addr}: {e}")

def main():
    if not os.path.exists(DATA_DIR):
         os.makedirs(DATA_DIR)

    sock = setup_socket(SERVER_IP, SERVER_PORT)
    client_states = {}
    delayed_packets_buffer = [] # Initialize delayed packet buffer

    try:
        while True:
            # Process incoming packets (non-blocking)
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                process_packet(sock, data, addr, client_states, delayed_packets_buffer)
            except socket.error as e:
                # No data available, or other socket error
                pass # Continue to process delayed packets

            # Process delayed packets
            now = time.time()
            # Create a new list for packets that are not yet due
            remaining_delayed_packets = []
            for deliver_at, pkt, addr, description in delayed_packets_buffer:
                if now >= deliver_at:
                    if "Incoming" in description: # Distinguish between incoming and outgoing delayed packets
                        # For delayed incoming packets, re-process them as if just received
                        # Note: `data` here would be pkt.pack() if we wanted to re-use process_packet's initial unpack
                        # But since we already have the unpacked pkt, we can call the handlers directly.
                        # However, to maintain the structure, we pass the original data to process_packet
                        # to ensure all checks (like drop) are done consistently.
                        # For simplicity here, we'll re-unpack, or could refactor to pass Packet object.
                        # Let's call the relevant handlers based on flags
                        client_id = f"{addr[0]}_{addr[1]}"
                        if client_id not in client_states:
                             client_states[client_id] = {"expected_seq": 0, "initialized": False}
                        state = client_states[client_id]

                        # This effectively re-processes the packet. Drop/duplication checks are already done.
                        if pkt.flags & FLAG_SYN:
                            handle_syn(sock, pkt, addr, state, delayed_packets_buffer)
                        elif pkt.flags & FLAG_FIN:
                            handle_fin(sock, pkt, addr, state, client_id, client_states, delayed_packets_buffer)
                        else:
                            handle_data(sock, pkt, addr, state, delayed_packets_buffer)
                    else: # Delayed outgoing ACK
                        sock.sendto(pkt.pack(), addr)
                        print(f"[{addr}] Delivered delayed {description} packet.")
                else:
                    remaining_delayed_packets.append((deliver_at, pkt, addr, description))
            delayed_packets_buffer = remaining_delayed_packets
    except KeyboardInterrupt:
        print("\nServer stopping...")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
