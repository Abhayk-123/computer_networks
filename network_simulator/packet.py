from dataclasses import dataclass
from typing import Any
from utils import crc16

@dataclass
class Frame:
    dest_mac: str
    src_mac: str
    eth_type: str
    payload: Any
    fcs: str = ''
    corrupted: bool = False

    def __post_init__(self):
        if not self.fcs:
            self.fcs = crc16(self.serialized_without_fcs())

    def serialized_without_fcs(self) -> str:
        return f'{self.dest_mac}|{self.src_mac}|{self.eth_type}|{self.payload}'

    def summary(self) -> str:
        return f'[DST:{self.dest_mac} | SRC:{self.src_mac} | TYPE:{self.eth_type} | FCS:{self.fcs} | Data:{self.payload}]'

@dataclass
class IPPacket:
    src_ip: str
    dest_ip: str
    payload: Any
    ttl: int = 8
    protocol: str = 'TCP'
    version: int = 4
    ihl: int = 5

    def summary(self) -> str:
        return f'[IPv{self.version} IHL:{self.ihl} TTL:{self.ttl} PROTO:{self.protocol} SRC:{self.src_ip} DST:{self.dest_ip} DATA:{self.payload}]'

@dataclass
class UDPSegment:
    src_port: int
    dest_port: int
    data: str
    checksum: str = ''

    def __post_init__(self):
        if not self.checksum:
            self.checksum = crc16(f'{self.src_port}|{self.dest_port}|{self.data}')

    @property
    def length(self):
        return 8 + len(self.data)

    def summary(self):
        return f'[UDP SrcPort:{self.src_port} DstPort:{self.dest_port} Len:{self.length} Checksum:{self.checksum} Data:{self.data}]'

@dataclass
class TCPSegment:
    src_port: int
    dest_port: int
    seq: int
    ack: int
    flags: str
    window: int
    data: str = ''

    def summary(self):
        return f'[TCP SrcPort:{self.src_port} DstPort:{self.dest_port} Seq:{self.seq} Ack:{self.ack} Flags:{self.flags} Win:{self.window} Data:{self.data}]'
