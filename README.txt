ITL351 Computer Networks Lab - Complete Protocol Stack Simulator
===============================================================

This package contains a complete Python network simulator for Submission 2 and Submission 3.
It implements Physical, Data Link, Network, Transport, and Application layers and runs them together.

Run:
  cd network_simulator
  python main.py

Files:
  main.py              - runs all tests end-to-end
  physical_layer.py    - EndDevice, Hub, line coding, topology
  data_link_layer.py   - MAC, Bridge, Switch, CRC, CSMA/CD, Go-Back-N
  network_layer.py     - Router, CIDR/VLSM, ARP, static routing, RIP, LPM, TTL
  transport_layer.py   - ports, sockets, TCP, UDP, multiplexing
  application_layer.py - HTTP, FTP, DNS, SSH demos
  packet.py            - frame/packet/segment data structures
  utils.py             - CRC, encoding, logging helpers

No extra packages are required.
