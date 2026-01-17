import socket
import argparse
import os
from shared import Packet, HEADER_SIZE, SERVER_BUFFER_SIZE, FLAG_SYN, FLAG_ACK, FLAG_FIN

class Server:
    def __init__(self, port, net_host, net_port):
        self.port = port
        self.net_addr = (net_host, net_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", port))
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        # Client state: client_addr_str -> {state...}
        self.clients = {} 

    def register_with_net(self):
        print(f"Registering with Net Daemon at {self.net_addr}...")
        # Send a dummy packet to register our presence
        # Payload doesn't matter, just need SrcPort in header
        pkt = Packet(src_port=self.port, dst_port=0, seq=0, ack=0, flags=0, window=1024)
        self.sock.sendto(pkt.pack(), self.net_addr)

    def run(self):
        self.register_with_net()
        print(f"Server listening on port {self.port}...")
        
        while True:
            try:
                data, addr = self.sock.recvfrom(SERVER_BUFFER_SIZE)
                # Note: addr will be the Net Daemon's address, not the client's.
                # We identify clients by the SrcPort in the packet header.
                self.process_packet(data)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error processing packet: {e}")

    def process_packet(self, data):
        try:
            pkt = Packet.unpack(data)
        except ValueError:
            return

        client_id = pkt.src_port
        
        if pkt.flags & FLAG_SYN:
            self.handle_syn(client_id, pkt)
        elif pkt.flags & FLAG_FIN:
            self.handle_fin(client_id, pkt)
        else:
            self.handle_data(client_id, pkt)

    def handle_syn(self, client_id, pkt):
        print(f"Recv SYN from Client {client_id}")
        # Initialize client state
        self.clients[client_id] = {
            "expected_seq": pkt.seq + 1, # SYN consumes 1 sequence number? 
            # In our simple protocol, SYN seq is start sequence. 
            # Let's say SYN is 100, then first data byte is 101? 
            # Or is SYN just setup? 
            # Original readme said: "The server's ACK is our starting sequence number for data"
            # Let's match typical TCP: SYN consumes 1 seq.
            "current_file": None
        }
        
        # Send SYN-ACK
        ack_num = pkt.seq + 1
        syn_ack = Packet(src_port=self.port, dst_port=client_id, seq=0, ack=ack_num, 
                         flags=FLAG_SYN | FLAG_ACK, window=1024)
        self.send_to_net(syn_ack)
        
        # Open file for writing
        filename = f"data/{client_id}.in"
        self.clients[client_id]["current_file"] = open(filename, "wb")
        print(f"New connection from {client_id}, saving to {filename}")

    def handle_data(self, client_id, pkt):
        if client_id not in self.clients:
            return # Ignore data from unknown clients (maybe send RST?)

        state = self.clients[client_id]
        expected_seq = state["expected_seq"]

        if pkt.seq == expected_seq:
            # Valid in-order packet
            data_len = len(pkt.data)
            if data_len > 0:
                print(f"Recv Data {data_len} bytes (Seq={pkt.seq}) from {client_id}")
                state["current_file"].write(pkt.data)
                state["current_file"].flush() # Ensure it's written
                
                state["expected_seq"] += data_len
                
                # Send ACK
                ack_pkt = Packet(src_port=self.port, dst_port=client_id, seq=0, 
                                 ack=state["expected_seq"], flags=FLAG_ACK, window=1024)
                self.send_to_net(ack_pkt)
        elif pkt.seq < expected_seq:
             # Duplicate/Retransmit of already received data
             # Send ACK for current expected_seq (Cumulative ACK)
             print(f"Recv Old Data (Seq={pkt.seq}) from {client_id}, re-sending ACK {expected_seq}")
             ack_pkt = Packet(src_port=self.port, dst_port=client_id, seq=0, 
                              ack=state["expected_seq"], flags=FLAG_ACK, window=1024)
             self.send_to_net(ack_pkt)
        else:
            # Out of order packet
            # Simple Go-Back-N receiver: Discard out-of-order packets but re-send ACK for expected
            # (Or buffer them if we wanted SACK/Optimize, but spec says simple)
            print(f"Recv Out-of-Order (Seq={pkt.seq}, Expected={expected_seq}) from {client_id}, ignored")
            # Usually we send duplicate ACK here to trigger fast retransmit
            ack_pkt = Packet(src_port=self.port, dst_port=client_id, seq=0, 
                             ack=state["expected_seq"], flags=FLAG_ACK, window=1024)
            self.send_to_net(ack_pkt)

    def handle_fin(self, client_id, pkt):
        if client_id in self.clients:
            print(f"Recv FIN from {client_id}")
            state = self.clients[client_id]
            if state["current_file"]:
                state["current_file"].close()
            
            # Send FIN-ACK
            fin_ack = Packet(src_port=self.port, dst_port=client_id, seq=0, 
                             ack=pkt.seq + 1, flags=FLAG_ACK, window=1024)
            self.send_to_net(fin_ack)
            
            del self.clients[client_id]

    def send_to_net(self, pkt):
        self.sock.sendto(pkt.pack(), self.net_addr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Server (py-med)")
    parser.add_argument("--port", type=int, default=9999, help="Server Port")
    parser.add_argument("--net-host", type=str, default="127.0.0.1", help="Net Daemon Host")
    parser.add_argument("--net-port", type=int, default=8000, help="Net Daemon Port")
    args = parser.parse_args()

    server = Server(args.port, args.net_host, args.net_port)
    server.run()
