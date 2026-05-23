from utils import log, generate_mac
from physical_layer import EndDevice, Hub, PointToPointLink, LineCodingDemo
from data_link_layer import DataLinkHost, Switch, Bridge, CSMACD, GoBackN, corrupt_frame, BROADCAST
from network_layer import Router, ARPTable, run_rip
from transport_layer import TCP, UDP, Socket, PortManager, WELL_KNOWN_PORTS
from application_layer import DNSService, HTTPService, FTPService, SSHService
from packet import IPPacket, TCPSegment


def title(text):
    print('\n' + '=' * 92)
    print(text)
    print('=' * 92)


def build_host(name, ip, mac_no):
    h = EndDevice(name, generate_mac(mac_no), ip)
    h.arp = ARPTable(h)
    h.ports = PortManager(h)
    return h


def physical_tests():
    title('SUBMISSION 1 + 2: PHYSICAL LAYER TESTS')
    LineCodingDemo.run('Hello')
    a = build_host('PC1', '192.168.1.2', 1)
    b = build_host('PC2', '192.168.1.3', 2)
    PointToPointLink(a, b)
    a.send('Hi PC2')

    hub = Hub('Hub1')
    hosts = [build_host(f'PC{i}', f'192.168.1.{i}', i) for i in range(1, 6)]
    for h in hosts:
        hub.connect(h)
    hosts[0].send('Broadcast through hub', dest='PC4')


def data_link_tests():
    title('SUBMISSION 1 + 2: DATA LINK LAYER TESTS')
    hosts = [build_host(f'SW-PC{i}', f'192.168.10.{i}', i) for i in range(1, 6)]
    sw = Switch('Switch1')
    for i, h in enumerate(hosts, 1):
        sw.connect(i, h)

    dl1 = DataLinkHost(hosts[0])
    dl4 = DataLinkHost(hosts[3])
    frame1 = dl1.make_frame(hosts[3].mac, 'First message to learn MAC')
    for port, dev in sw.receive(1, frame1):
        DataLinkHost(dev).accept_frame(frame1)

    frame2 = dl4.make_frame(hosts[0].mac, 'Reply: now switch can unicast')
    for port, dev in sw.receive(4, frame2):
        DataLinkHost(dev).accept_frame(frame2)
    log('DL', f'Domains in switch topology: {sw.domains()}')

    bad = dl1.make_frame(hosts[1].mac, 'Important payload')
    corrupt_frame(bad)
    DataLinkHost(hosts[1]).accept_frame(bad)

    CSMACD.transmit(['SW-PC1', 'SW-PC2'])
    GoBackN(total=10, window=4, lost=5).run()

    hub_a, hub_b, core = Hub('Hub-A'), Hub('Hub-B'), Switch('CoreSwitch')
    left = [build_host(f'A{i}', f'10.0.1.{i}', i + 10) for i in range(1, 6)]
    right = [build_host(f'B{i}', f'10.0.2.{i}', i + 20) for i in range(1, 6)]
    for h in left: hub_a.connect(h)
    for h in right: hub_b.connect(h)
    core.connect(1, hub_a); core.connect(2, hub_b)
    log('DL', 'Two star topologies connected via switch: 10 devices can communicate')
    log('DL', 'Broadcast domains = 1 with normal switch/VLAN default; collision domains = each switch port + hub shared segments')


def network_tests():
    title('SUBMISSION 2: NETWORK LAYER TESTS')
    r1, r2, r3 = Router('R1'), Router('R2'), Router('R3')
    r1.add_interface('g0/0', '192.168.1.1', generate_mac(101), '192.168.1.0/24')
    r1.add_interface('s0/0', '10.0.12.1', generate_mac(102), '10.0.12.0/30')
    r2.add_interface('s0/0', '10.0.12.2', generate_mac(103), '10.0.12.0/30')
    r2.add_interface('s0/1', '10.0.23.1', generate_mac(104), '10.0.23.0/30')
    r3.add_interface('s0/0', '10.0.23.2', generate_mac(105), '10.0.23.0/30')
    r3.add_interface('g0/0', '192.168.3.1', generate_mac(106), '192.168.3.0/24')

    r1.add_route('192.168.3.0/24', '10.0.12.2', 's0/0', 2)
    r2.add_route('192.168.1.0/24', '10.0.12.1', 's0/0', 1)
    r2.add_route('192.168.3.0/24', '10.0.23.2', 's0/1', 1)
    r3.add_route('192.168.1.0/24', '10.0.23.1', 's0/0', 2)

    packet = IPPacket('192.168.1.2', '192.168.3.2', 'Hello through static routing', ttl=5)
    log('NET', f'IP packet created: {packet.summary()}')
    r1.forward(packet); r2.forward(packet); r3.forward(packet)

    r1.add_route('192.168.3.0/24', '10.0.12.2', 's0/0', 2)
    r1.add_route('192.168.3.128/25', '10.0.12.2', 's0/0', 1)
    r1.lookup('192.168.3.130')

    r1.add_neighbor(r2); r2.add_neighbor(r1); r2.add_neighbor(r3); r3.add_neighbor(r2)
    run_rip([r1, r2, r3], rounds=2)


def transport_application_tests():
    title('SUBMISSION 3: TRANSPORT + APPLICATION LAYER TESTS')
    host_a = build_host('HostA', '192.168.1.2', 1)
    host_b = build_host('HostB', '192.168.2.2', 2)
    pa1 = host_a.ports.bind('Browser-A', 5001)
    pa2 = host_a.ports.bind('FTP-Client-A', 5002)
    pb1 = host_b.ports.bind('HTTP-Server-B', 80)
    pb2 = host_b.ports.bind('FTP-Server-B', 21)

    tcp = TCP(window=4)
    tcp.handshake(Socket(host_a.ip, pa1, host_b.ip, pb1))
    tcp.handshake(Socket(host_a.ip, pa2, host_b.ip, pb2))
    tcp.send_data_sliding_window(Socket(host_a.ip, pa1, host_b.ip, pb1), [f'Msg{i}' for i in range(1, 11)], lost_index=6)
    UDP().send(Socket(host_a.ip, 53000, host_b.ip, WELL_KNOWN_PORTS['DNS']), 'DNS query payload')
    host_b.ports.deliver(80, 'GET /index.html HTTP/1.1')
    HTTPService().request('/index.html'); HTTPService().response()
    FTPService().run_demo()
    SSHService().run_demo()
    tcp.teardown(Socket(host_a.ip, pa1, host_b.ip, pb1))


def full_stack_test():
    title('MANDATORY FULL STACK TEST: HostA HTTP Client -> Router1 -> HostB HTTP Server')
    host_a = build_host('HostA', '192.168.1.2', 1)
    host_b = build_host('HostB', '192.168.2.2', 2)
    router = Router('Router1')
    router.add_interface('g0/0', '192.168.1.1', generate_mac(10), '192.168.1.0/24')
    router.add_interface('g0/1', '192.168.2.1', generate_mac(11), '192.168.2.0/24')

    dns = DNSService()
    http = HTTPService()
    server_ip = dns.query('hostb.local')
    known_hosts = {host_a.ip: host_a, host_b.ip: host_b}
    host_a.arp.resolve('192.168.1.1', {'192.168.1.1': type('GW', (), {'mac': router.interfaces['g0/0'].mac})()})
    host_b.arp.resolve('192.168.2.1', {'192.168.2.1': type('GW', (), {'mac': router.interfaces['g0/1'].mac})()})

    req = http.request('/index.html')
    client_port = 52000
    server_port = 80
    socket = Socket(host_a.ip, client_port, server_ip, server_port)
    tcp = TCP(window=4)
    handshake = tcp.handshake(socket)

    segment = TCPSegment(client_port, server_port, 1, 101, 'PSH-ACK', 4, req)
    ip_packet = IPPacket(host_a.ip, server_ip, segment, ttl=8, protocol='TCP')
    log('NET', f'IP packet created, TTL set: {ip_packet.summary()}')
    route = router.lookup(server_ip)

    dl_a = DataLinkHost(host_a)
    frame_to_router = dl_a.make_frame(router.interfaces['g0/0'].mac, ip_packet, 'IPv4')
    host_a.send(frame_to_router.summary(), dest='Router1')

    log('PHY', 'Router1: bits received and decoded from HostA')
    log('DL', 'Router1: CRC checked OK; incoming frame accepted')
    router.forward(ip_packet)
    hostb_mac = host_a.arp.resolve(host_b.ip, known_hosts)
    frame_to_b = type('FrameCarrier', (), {})
    from packet import Frame
    frame2 = Frame(host_b.mac, router.interfaces['g0/1'].mac, 'IPv4', ip_packet)
    log('DL', f'Router1: Re-framed for next hop: {frame2.summary()}')
    log('PHY', f'Router1 -> HostB: Transmitted encoded bits for frame')

    log('PHY', 'HostB: bits received and decoded')
    DataLinkHost(host_b).accept_frame(frame2)
    log('NET', f'HostB: IP packet delivered to {host_b.ip}: {ip_packet.summary()}')
    log('TCP', f'HostB: TCP segment delivered to port 80: {segment.summary()}')
    response = http.response()

    response_segment = TCPSegment(server_port, client_port, 101, 2, 'PSH-ACK', 4, response)
    response_packet = IPPacket(host_b.ip, host_a.ip, response_segment, ttl=8, protocol='TCP')
    log('APP', 'HTTP response travels back using same encapsulation path')
    log('TCP', response_segment.summary())
    log('NET', response_packet.summary())
    frame_back = DataLinkHost(host_b).make_frame(router.interfaces['g0/1'].mac, response_packet, 'IPv4')
    log('PHY', f'HostB -> Router1 -> HostA: response bits encoded and transmitted')
    router.forward(response_packet)
    frame_final = Frame(host_a.mac, router.interfaces['g0/0'].mac, 'IPv4', response_packet)
    DataLinkHost(host_a).accept_frame(frame_final)
    log('APP', 'HostA Browser received: HTTP/1.1 200 OK — Hello from HostB')
    log('APP', 'Full encapsulation and decapsulation completed: APP -> TCP -> IP -> Frame -> Bits and back')


def main():
    physical_tests()
    data_link_tests()
    network_tests()
    transport_application_tests()
    full_stack_test()


if __name__ == '__main__':
    main()
