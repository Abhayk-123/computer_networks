from utils import log, nrz_encode, manchester_encode

class EndDevice:
    def __init__(self, name, mac=None, ip=None):
        self.name = name
        self.mac = mac
        self.ip = ip
        self.port = None
        self.arp_cache = {}
        self.process_ports = {}

    def connect(self, device):
        self.port = device
        if hasattr(device, 'connect'):
            device.connect(self)
        log('PHY', f'{self.name} connected to {device.name}')

    def send(self, data, dest=None):
        bits = nrz_encode(data)
        log('PHY', f'{self.name}: Signal sent using NRZ bits: {bits[:120]}')
        if self.port:
            self.port.receive_signal(self, data, dest)

    def receive_signal(self, sender, data):
        bits = nrz_encode(data)
        log('PHY', f'{self.name}: Signal received from {sender.name}; bits decoded: {bits[:120]}')
        return data

class Hub:
    def __init__(self, name):
        self.name = name
        self.devices = []

    def connect(self, device):
        if device not in self.devices:
            self.devices.append(device)
            device.port = self
            self.show_topology()

    def receive_signal(self, sender, data, dest=None):
        log('PHY', f'{self.name}: Hub broadcasting signal from {sender.name} to all ports')
        accepted = []
        for d in self.devices:
            if d is not sender:
                d.receive_signal(sender, data)
                if dest is None or getattr(d, 'name', None) == dest:
                    accepted.append(d.name)
        if dest:
            log('PHY', f'Only destination {dest} accepts. Others discard at upper layer.')
        return accepted

    def show_topology(self):
        names = '  '.join(d.name for d in self.devices)
        log('PHY', f'Star Topology: {names}\n          \\  |  /\n            [{self.name}]')

class PointToPointLink:
    def __init__(self, a, b, name='P2P-Link'):
        self.name = name
        self.a = a
        self.b = b
        a.port = self
        b.port = self
        log('PHY', f'{a.name} <---- {self.name} ----> {b.name}')

    def receive_signal(self, sender, data, dest=None):
        receiver = self.b if sender is self.a else self.a
        log('PHY', f'{self.name}: carrying signal {sender.name} -> {receiver.name}')
        return receiver.receive_signal(sender, data)

class LineCodingDemo:
    @staticmethod
    def run(data='Hello'):
        log('PHY', f'Input data: {data}')
        log('PHY', f'NRZ       : {nrz_encode(data)}')
        log('PHY', f'Manchester: {manchester_encode(data)[:140]}')
