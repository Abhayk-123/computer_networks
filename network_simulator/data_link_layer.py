from utils import log, crc16, verify_crc
from packet import Frame

BROADCAST = 'FF:FF:FF:FF:FF:FF'

class DataLinkHost:
    def __init__(self, device):
        self.device = device

    def make_frame(self, dest_mac, payload, eth_type='IPv4'):
        frame = Frame(dest_mac, self.device.mac, eth_type, payload)
        log('DL', f'{self.device.name}: Frame created {frame.summary()}')
        return frame

    def accept_frame(self, frame):
        if frame.corrupted or not verify_crc(frame.serialized_without_fcs(), frame.fcs):
            log('DL', f'{self.device.name}: CRC ERROR. Frame dropped. {frame.summary()}')
            return False
        if frame.dest_mac in (self.device.mac, BROADCAST):
            log('DL', f'{self.device.name}: Frame accepted after CRC check: {frame.summary()}')
            return True
        log('DL', f'{self.device.name}: Frame not for this MAC. Discarded.')
        return False

class Bridge:
    def __init__(self, name):
        self.name = name
        self.table = {}
        self.ports = {}

    def connect(self, port_name, device):
        self.ports[port_name] = device
        log('DL', f'{self.name}: connected {device.name} on {port_name}')

    def forward(self, in_port, frame):
        self.table[frame.src_mac] = in_port
        out_port = self.table.get(frame.dest_mac)
        if out_port and out_port != in_port:
            log('DL', f'{self.name}: Bridge filtered/forwarded frame only to {out_port}')
            return [self.ports[out_port]]
        log('DL', f'{self.name}: Unknown destination; bridge floods other segment')
        return [d for p, d in self.ports.items() if p != in_port]

class Switch:
    def __init__(self, name):
        self.name = name
        self.ports = {}
        self.cam_table = {}

    def connect(self, port_no, device):
        self.ports[port_no] = device
        log('DL', f'{self.name}: {device.name} connected on port {port_no}')

    def receive(self, in_port, frame):
        self.cam_table[frame.src_mac] = in_port
        log('DL', f'{self.name}: Learned MAC {frame.src_mac} on port {in_port}')
        out = self.cam_table.get(frame.dest_mac)
        if frame.dest_mac == BROADCAST or out is None:
            targets = [p for p in self.ports if p != in_port]
            log('DL', f'{self.name}: Unknown/broadcast destination; flooding to ports {targets}')
        elif out == in_port:
            targets = []
            log('DL', f'{self.name}: Source and destination on same port. Frame filtered.')
        else:
            targets = [out]
            log('DL', f'{self.name}: Unicast forwarding to port {out}')
        self.print_cam()
        return [(p, self.ports[p]) for p in targets]

    def print_cam(self):
        log('DL', f'{self.name} CAM Table: {self.cam_table}')

    def domains(self):
        return {'broadcast_domains': 1, 'collision_domains': len(self.ports)}

class CSMACD:
    @staticmethod
    def transmit(stations):
        log('DL', 'CSMA/CD: Carrier sensing started')
        if len(stations) > 1:
            log('DL', f'Collision detected between {stations}. Sending jam signal, backing off, retransmitting.')
            log('DL', f'{stations[0]} retransmits successfully after random backoff')
        else:
            log('DL', f'{stations[0]} transmits. Channel was idle.')

class GoBackN:
    def __init__(self, total=10, window=4, lost=5):
        self.total = total
        self.window = window
        self.lost = lost

    def run(self):
        base = 1
        while base <= self.total:
            end = min(base + self.window - 1, self.total)
            log('DL', f'Go-Back-N Window [{base}-{end}] sending frames {list(range(base, end+1))}')
            timeout = False
            for seq in range(base, end + 1):
                if seq == self.lost:
                    log('DL', f'Frame {seq} lost/corrupted. ACK not received.')
                    timeout = True
                    break
                log('DL', f'ACK {seq} received; window can slide')
            if timeout:
                log('DL', f'Timeout at frame {seq}. Retransmitting from {seq} onward.')
                self.lost = -1
                base = seq
            else:
                base = end + 1
        log('DL', 'Go-Back-N completed successfully')

def corrupt_frame(frame):
    frame.corrupted = True
    frame.payload = str(frame.payload) + ' [CORRUPTED]'
    return frame
