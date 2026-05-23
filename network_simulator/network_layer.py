from ipaddress import ip_network, ip_address
from utils import log
from packet import IPPacket

class Interface:
    def __init__(self, name, ip, mac, network):
        self.name = name
        self.ip = ip
        self.mac = mac
        self.network = ip_network(network, strict=False)

class Router:
    def __init__(self, name):
        self.name = name
        self.interfaces = {}
        self.routing_table = []
        self.neighbors = []

    def add_interface(self, ifname, ip, mac, network):
        self.interfaces[ifname] = Interface(ifname, ip, mac, network)
        self.add_route(str(ip_network(network, strict=False)), None, ifname, 0)
        log('NET', f'{self.name}: interface {ifname} IP {ip} network {network}')

    def add_route(self, network, next_hop, interface, metric=1):
        net = ip_network(network, strict=False)
        existing = [r for r in self.routing_table if r['network'] == net]
        if existing:
            if metric < existing[0]['metric']:
                existing[0].update(next_hop=next_hop, interface=interface, metric=metric)
        else:
            self.routing_table.append({'network': net, 'next_hop': next_hop, 'interface': interface, 'metric': metric})
        log('NET', f'{self.name}: route added {net} via {next_hop or "direct"} dev {interface} metric {metric}')

    def add_neighbor(self, router):
        if router not in self.neighbors:
            self.neighbors.append(router)
            log('NET', f'{self.name}: RIP neighbor {router.name} added')

    def lookup(self, dest_ip):
        dest = ip_address(dest_ip)
        matches = [r for r in self.routing_table if dest in r['network']]
        if not matches:
            log('NET', f'{self.name}: no route for {dest_ip}')
            return None
        best = max(matches, key=lambda r: r['network'].prefixlen)
        log('NET', f'{self.name}: Longest prefix match for {dest_ip} -> {best["network"]} via {best["next_hop"] or "direct"}')
        return best

    def forward(self, packet: IPPacket):
        packet.ttl -= 1
        log('NET', f'{self.name}: TTL decremented to {packet.ttl}')
        if packet.ttl <= 0:
            log('NET', f'{self.name}: TTL = 0, packet dropped')
            return None
        route = self.lookup(packet.dest_ip)
        if route:
            log('NET', f'{self.name}: forwarding {packet.src_ip} -> {packet.dest_ip} out {route["interface"]}')
        return route

    def rip_send_update(self):
        update = [{'network': r['network'], 'metric': min(r['metric'] + 1, 16), 'from': self.name} for r in self.routing_table]
        for n in self.neighbors:
            n.rip_receive_update(self, update)

    def rip_receive_update(self, sender, update):
        log('NET', f'{self.name}: RIP update received from {sender.name}')
        for item in update:
            if item['metric'] >= 16:
                continue
            if any(item['network'] == iface.network for iface in self.interfaces.values()):
                continue
            self.add_route(str(item['network']), sender.name, f'to-{sender.name}', item['metric'])

    def print_table(self):
        log('NET', f'Routing table of {self.name}')
        for r in sorted(self.routing_table, key=lambda x: str(x['network'])):
            log('NET', f'  {r["network"]} | mask {r["network"].netmask} | next-hop {r["next_hop"] or "direct"} | iface {r["interface"]} | metric {r["metric"]}')

class ARPTable:
    def __init__(self, owner):
        self.owner = owner
        self.cache = {}

    def resolve(self, ip, known_hosts):
        if ip in self.cache:
            log('NET', f'ARP cache hit: {ip} is at {self.cache[ip]}')
            return self.cache[ip]
        log('NET', f'ARP Request: Who has {ip}? Tell {self.owner.ip}')
        host = known_hosts.get(ip)
        if not host:
            log('NET', f'ARP failed: {ip} unknown')
            return None
        log('NET', f'ARP Reply: {ip} is at {host.mac}')
        self.cache[ip] = host.mac
        return host.mac

def run_rip(routers, rounds=3):
    for i in range(1, rounds + 1):
        log('NET', f'RIP convergence round {i}')
        for r in routers:
            r.rip_send_update()
        for r in routers:
            r.print_table()
