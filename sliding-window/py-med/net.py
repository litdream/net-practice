import socket
import sys
import time
import random
import argparse
import select
from shared import Packet, HEADER_SIZE, SERVER_BUFFER_SIZE

# Simulation Parameters
DROP_PROBABILITY = 0.1
DUPLICATE_PROBABILITY = 0.1
DELAY_PROBABILITY = 0.1
MIN_DELAY = 0.5
MAX_DELAY = 2.0

class NetDaemon:
    def __init__(self, port):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", port))
        self.sock.setblocking(False)
        self.mapping = {} # Virtual Port -> (IP, Physical Port)
        self.delayed_packets = [] # List of (delivery_time, data, address)

    def log(self, msg):
        print(f"[Net] {msg}")

    def register(self, virtual_port, addr):
        if virtual_port not in self.mapping or self.mapping[virtual_port] != addr:
            self.mapping[virtual_port] = addr
            self.log(f"Registered Virtual Port {virtual_port} -> {addr}")

    def run(self):
        self.log(f"Listening on port {self.port}...")
        
        while True:
            # 1. Check for delayed packets to send
            now = time.time()
            remaining_delayed = []
            for delivery_time, data, addr in self.delayed_packets:
                if now >= delivery_time:
                    try:
                        self.sock.sendto(data, addr)
                        # self.log(f"Sent delayed packet to {addr}")
                    except Exception as e:
                        self.log(f"Error sending delayed packet: {e}")
                else:
                    remaining_delayed.append((delivery_time, data, addr))
            self.delayed_packets = remaining_delayed

            # 2. Check for incoming packets
            # Wait a short time to avoid busy loop, but check often for delayed packets
            try:
                ready = select.select([self.sock], [], [], 0.05)
                if ready[0]:
                    data, addr = self.sock.recvfrom(SERVER_BUFFER_SIZE)
                    self.process_packet(data, addr)
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.log(f"Error in main loop: {e}")

    def process_packet(self, data, addr):
        try:
            pkt = Packet.unpack(data)
        except ValueError:
            self.log(f"Ignored invalid packet from {addr}")
            return

        # Implicit Registration
        self.register(pkt.src_port, addr)

        # Forwarding Logic
        if pkt.dst_port in self.mapping:
            target_addr = self.mapping[pkt.dst_port]
            self.handle_simulation_and_forward(data, target_addr)
        else:
            self.log(f"dropped packet for unknown destination {pkt.dst_port} (from {pkt.src_port})")

    def handle_simulation_and_forward(self, data, target_addr):
        # 1. Packet Drop
        if random.random() < DROP_PROBABILITY:
            self.log("SIMULATION: Dropped packet")
            return

        # 2. Packet Duplication
        if random.random() < DUPLICATE_PROBABILITY:
            self.log("SIMULATION: Duplicated packet")
            self.send_packet(data, target_addr)
            # Send the duplicate as well (recurse or just send?)
            # Just send it immediately to avoid infinite recursion of duplication checks
            # But usually duplication means 2 packets arrive. We can just send again.
            # To avoid "duplicate checking" the duplicate, we just call raw send.
            self.send_packet(data, target_addr)
            return

        # 3. Packet Delay
        if random.random() < DELAY_PROBABILITY:
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            delivery_time = time.time() + delay
            self.log(f"SIMULATION: Delayed packet by {delay:.2f}s")
            self.delayed_packets.append((delivery_time, data, target_addr))
            return

        # Normal Forwarding
        self.send_packet(data, target_addr)

    def send_packet(self, data, target_addr):
        try:
            self.sock.sendto(data, target_addr)
        except Exception as e:
            self.log(f"Error forwarding to {target_addr}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Mediator (Net Daemon)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()

    net = NetDaemon(args.port)
    net.run()
