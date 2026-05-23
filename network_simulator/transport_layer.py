from utils import log, random_ephemeral_port
from packet import TCPSegment, UDPSegment

WELL_KNOWN_PORTS = {'HTTP': 80, 'FTP': 21, 'SSH': 22, 'DNS': 53, 'TELNET': 23}

class Process:
    def __init__(self, name, port=None):
        self.name = name
        self.port = port or random_ephemeral_port()

class Socket:
    def __init__(self, src_ip, src_port, dest_ip, dest_port):
        self.src_ip = src_ip
        self.src_port = src_port
        self.dest_ip = dest_ip
        self.dest_port = dest_port

    def __str__(self):
        return f'({self.src_ip}:{self.src_port}) -> ({self.dest_ip}:{self.dest_port})'

class TCP:
    def __init__(self, window=4):
        self.window = window
        self.seq = 0

    def handshake(self, socket):
        syn = TCPSegment(socket.src_port, socket.dest_port, 0, 0, 'SYN', self.window)
        synack = TCPSegment(socket.dest_port, socket.src_port, 100, 1, 'SYN-ACK', self.window)
        ack = TCPSegment(socket.src_port, socket.dest_port, 1, 101, 'ACK', self.window)
        log('TCP', f'3-way handshake on socket {socket}')
        log('TCP', f'SYN sent: {syn.summary()}')
        log('TCP', f'SYN-ACK received: {synack.summary()}')
        log('TCP', f'ACK sent: {ack.summary()}')
        return [syn, synack, ack]

    def send_data_sliding_window(self, socket, messages, lost_index=5):
        base = 1
        n = len(messages)
        while base <= n:
            end = min(base + self.window - 1, n)
            log('TCP', f'Sliding window [{base}-{end}] sending TCP segments')
            lost = False
            for i in range(base, end + 1):
                seg = TCPSegment(socket.src_port, socket.dest_port, i, 0, 'PSH-ACK', self.window, messages[i-1])
                log('TCP', f'Sent {seg.summary()}')
                if i == lost_index:
                    log('TCP', f'Segment {i} lost. No ACK received.')
                    lost = True
                    break
                log('TCP', f'ACK {i+1} received')
            if lost:
                log('TCP', f'Timeout. Go-Back-N retransmission starts from segment {i}')
                lost_index = -1
                base = i
            else:
                base = end + 1

    def teardown(self, socket):
        log('TCP', f'Connection teardown for {socket}: FIN -> FIN-ACK -> ACK')

class UDP:
    def send(self, socket, data):
        seg = UDPSegment(socket.src_port, socket.dest_port, data)
        log('UDP', f'UDP datagram sent without handshake/retransmission: {seg.summary()}')
        return seg

class PortManager:
    def __init__(self, host):
        self.host = host
        self.processes = {}

    def bind(self, process_name, port=None):
        if port is None:
            port = random_ephemeral_port()
        if port in self.processes:
            raise ValueError(f'Port {port} already used on {self.host.name}')
        self.processes[port] = process_name
        log('TCP', f'{self.host.name}: Process {process_name} bound to port {port}')
        return port

    def deliver(self, port, data):
        proc = self.processes.get(port)
        log('TCP', f'{self.host.name}: Multiplexing delivered data to process {proc} on port {port}: {data}')
