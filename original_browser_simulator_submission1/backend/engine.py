"""
Network Simulator - Simulation Engine
Manages topology, runs simulations, tracks events.

FIXES:
  - connect(): when a Switch is involved, register_mac() is called for the
    connected EndDevice so the MAC table is pre-populated (bidirectional
    awareness → unidirectional forwarding on first frame).
  - test_hub_broadcast(): hub.broadcast() returns ALL targets except sender;
    engine now iterates that list and calls receive() on every host so data
    truly reaches ALL remaining PCs.
  - All three ARQ protocols (Stop-and-Wait, Go-Back-N, Selective Repeat)
    are run and included in every simulation result.
"""

from devices import EndDevice, Hub, Switch, Bridge, Frame
from protocols import CRC, CSMACD, StopAndWait, GoBackN, SelectiveRepeat
import random
import time


class SimulationEngine:
    def __init__(self):
        self.devices = {}
        self.links = []
        self.events = []
        self.link_counter = 0

    def _log(self, event_type: str, message: str, data: dict = None):
        self.events.append({
            "timestamp": round(time.time() * 1000),
            "type": event_type,
            "message": message,
            "data": data or {},
        })

    # ── Device Management ──────────────────────────────

    def add_device(self, device_id: str, device_type: str, name: str = None) -> dict:
        name = name or device_id
        if device_type == "host":
            device = EndDevice(device_id, name)
        elif device_type == "hub":
            device = Hub(device_id, name)
        elif device_type == "switch":
            device = Switch(device_id, name)
        elif device_type == "bridge":
            device = Bridge(device_id, name)
        else:
            return {"error": f"Unknown device type: {device_type}"}

        self.devices[device_id] = device
        self._log("DEVICE_ADDED", f"{device_type.upper()} '{name}' added", device.to_dict())
        return device.to_dict()

    def connect(self, source_id: str, target_id: str, bandwidth: int = 100) -> dict:
        if source_id not in self.devices or target_id not in self.devices:
            return {"error": "One or both devices not found"}

        self.link_counter += 1
        link_id = f"link_{self.link_counter}"
        link = {"id": link_id, "source": source_id, "target": target_id, "bandwidth": bandwidth}
        self.links.append(link)

        src = self.devices[source_id]
        tgt = self.devices[target_id]
        src.connections.append(target_id)
        tgt.connections.append(source_id)

        # ── FIX: pre-register MACs so switch can unicast immediately ──
        # If either side is a Switch and the other is an EndDevice,
        # register the EndDevice's MAC into the switch's MAC table now.
        if isinstance(src, Switch) and isinstance(tgt, EndDevice):
            src.register_mac(tgt.mac_address, tgt.device_id)
        if isinstance(tgt, Switch) and isinstance(src, EndDevice):
            tgt.register_mac(src.mac_address, src.device_id)

        self._log("LINK_CREATED", f"Link: {source_id} ↔ {target_id} ({bandwidth} Mbps)", link)
        return link

    def get_topology(self) -> dict:
        nodes = [d.to_dict() for d in self.devices.values()]
        return {"nodes": nodes, "links": self.links, "summary": self._get_summary()}

    def _get_summary(self) -> dict:
        hosts    = [d for d in self.devices.values() if d.device_type == "host"]
        hubs     = [d for d in self.devices.values() if d.device_type == "hub"]
        switches = [d for d in self.devices.values() if d.device_type == "switch"]
        bridges  = [d for d in self.devices.values() if d.device_type == "bridge"]

        collision_domains = len(hubs)
        for sw in switches:
            collision_domains += len(sw.connections)

        broadcast_domains = max(1, len([d for d in self.devices.values()
                                        if d.device_type == "router"]) + 1)
        return {
            "total_devices": len(self.devices),
            "hosts": len(hosts),
            "hubs": len(hubs),
            "switches": len(switches),
            "bridges": len(bridges),
            "collision_domains": collision_domains,
            "broadcast_domains": broadcast_domains,
        }

    # ── Helper: run all three ARQ protocols ───────────

    def _run_all_arq(self, num_frames: int = 6, window_size: int = 4,
                     error_rate: float = 0.2) -> dict:
        frame_list = [f"frame_{i}" for i in range(num_frames)]
        return {
            "stop_and_wait":    StopAndWait(error_rate).simulate(frame_list),
            "go_back_n":        GoBackN(window_size, error_rate).simulate(frame_list),
            "selective_repeat": SelectiveRepeat(window_size, error_rate).simulate(frame_list),
        }

    # ── Test Case 1: P2P between two hosts ────────────

    def test_p2p(self, host1_id: str, host2_id: str, message: str) -> dict:
        h1 = self.devices.get(host1_id)
        h2 = self.devices.get(host2_id)
        if not h1 or not h2:
            return {"error": "Hosts not found"}

        self._log("TEST_START", f"P2P test: {host1_id} → {host2_id}")
        packet, frame = h1.send(h2.mac_address, message)
        crc_result = CRC.run(message)
        frame.checksum = crc_result["remainder"]
        received = h2.receive(frame)

        self._log("TRANSMISSION", f"Frame sent {host1_id} → {host2_id}", frame.to_dict())
        self._log("RECEIVED", f"{host2_id} received frame", {"success": received})

        return {
            "test": "P2P Transmission",
            "from": host1_id,
            "to": host2_id,
            "message": message,
            "bits": packet.bits[:40] + "...",
            "frame": frame.to_dict(),
            "crc": crc_result,
            "delivered": received,
            "flow_control": self._run_all_arq(),
        }

    # ── Test Case 2: Star topology via Hub ────────────

    def test_hub_broadcast(self, sender_id: str, hub_id: str, message: str) -> dict:
        """
        Hub Broadcast — Physical layer.

        FIX: hub.broadcast() returns ALL connected device IDs.
        We now iterate every target and call receive() on it so the data truly
        reaches ALL PCs.
        """
        sender = self.devices.get(sender_id)
        hub    = self.devices.get(hub_id)
        if not sender or not hub:
            return {"error": "Device not found"}

        self._log("TEST_START", f"Hub broadcast from {sender_id}")

        csmacd = CSMACD(sender_id)
        access_result = csmacd.transmit(message, channel_busy=random.choice([True, False]))

        # Build broadcast frame (dest = broadcast MAC)
        frame = Frame(
            source_mac=sender.mac_address,
            dest_mac="FF:FF:FF:FF:FF:FF",
            data=message
        )
        crc_result = CRC.run(message)
        frame.checksum = crc_result["remainder"]

        # ── FIX: get ALL targets from hub, deliver to EACH one ──
        targets = hub.broadcast(frame, sender_id)

        delivery = {}
        for target_id in targets:
            target = self.devices.get(target_id)
            if target and target.device_type == "host":
                ok = target.receive(frame)           # broadcast frame accepted
                delivery[target_id] = ok
                self._log("DELIVERED", f"Hub → {target_id}", {"delivered": ok})
            else:
                # Non-host devices on the hub (rare) just log
                delivery[target_id] = "forwarded"

        self._log("HUB_BROADCAST_DONE",
                  f"Hub delivered to {len(delivery)} devices",
                  {"targets": targets, "delivery": delivery})

        return {
            "test": "Hub Broadcast (Star Topology)",
            "sender": sender_id,
            "hub": hub_id,
            "message": message,
            "broadcast_dest_mac": "FF:FF:FF:FF:FF:FF",
            "csmacd": access_result,
            "crc": crc_result,
            "frame": frame.to_dict(),
            "broadcast_targets": targets,
            "delivery": delivery,
            "all_delivered": all(v is True for v in delivery.values()),
            "collision_domain": "ALL devices share 1 collision domain (hub)",
            "flow_control": self._run_all_arq(),
        }

    # ── Test Case 3: Switch with MAC learning ─────────

    def test_switch_unicast(self, sender_id: str, receiver_id: str,
                             switch_id: str, message: str) -> dict:
        sender   = self.devices.get(sender_id)
        receiver = self.devices.get(receiver_id)
        switch   = self.devices.get(switch_id)
        if not sender or not receiver or not switch:
            return {"error": "Device not found"}

        self._log("TEST_START", f"Switch unicast: {sender_id} → {receiver_id}")

        frame = Frame(
            source_mac=sender.mac_address,
            dest_mac=receiver.mac_address,
            data=message
        )
        crc_result = CRC.run(message)
        frame.checksum = crc_result["remainder"]

        csmacd = CSMACD(sender_id)
        access_result = csmacd.transmit(message, channel_busy=False)

        targets, forward_type = switch.forward_frame(frame, sender_id)
        delivered = False
        if receiver_id in targets:
            delivered = receiver.receive(frame)

        self._log("SWITCH_FORWARD",
                  f"Switch forwarded ({forward_type}) to {targets}",
                  {"mac_table": switch.mac_table, "forward_type": forward_type})

        return {
            "test": "Switch Unicast + MAC Learning",
            "sender": sender_id,
            "receiver": receiver_id,
            "switch": switch_id,
            "message": message,
            "frame": frame.to_dict(),
            "crc": crc_result,
            "csmacd": access_result,
            "forward_type": forward_type,
            "mac_table": switch.mac_table,
            "delivered": delivered,
            "collision_domains": switch.get_collision_domains(),
            "broadcast_domains": 1,
            "flow_control": self._run_all_arq(),
        }

    # ── Test Case 4: Dual star (2 hubs + 1 switch) ────

    def test_dual_star(self, sender_id: str, receiver_id: str,
                        hub1_id: str, hub2_id: str, switch_id: str,
                        message: str) -> dict:
        sender   = self.devices.get(sender_id)
        receiver = self.devices.get(receiver_id)
        hub1     = self.devices.get(hub1_id)
        hub2     = self.devices.get(hub2_id)
        switch   = self.devices.get(switch_id)

        if not all([sender, receiver, hub1, hub2, switch]):
            return {"error": "One or more devices not found"}

        self._log("TEST_START", f"Dual star: {sender_id} → {receiver_id}")

        frame = Frame(
            source_mac=sender.mac_address,
            dest_mac=receiver.mac_address,
            data=message
        )
        crc_result = CRC.run(message)
        frame.checksum = crc_result["remainder"]

        csmacd = CSMACD(sender_id)
        access_result = csmacd.transmit(message, channel_busy=False)

        # Path: sender → hub1 → switch → hub2 → receiver
        _                      = hub1.broadcast(frame, sender_id)
        _, fwd_type            = switch.forward_frame(frame, hub1_id)
        hub2_targets           = hub2.broadcast(frame, switch_id)

        delivered = False
        if receiver_id in hub2_targets:
            delivered = receiver.receive(frame)

        return {
            "test": "Dual Star Topology",
            "path": f"{sender_id} → {hub1_id} → {switch_id} → {hub2_id} → {receiver_id}",
            "message": message,
            "frame": frame.to_dict(),
            "crc": crc_result,
            "csmacd": access_result,
            "switch_forward_type": fwd_type,
            "mac_table": switch.mac_table,
            "delivered": delivered,
            "collision_domains": 2,
            "broadcast_domains": 1,
            "note": "2 collision domains (one per hub), 1 broadcast domain",
            "flow_control": self._run_all_arq(),
        }

    def get_events(self) -> list:
        return self.events

    def clear(self):
        self.devices = {}
        self.links = []
        self.events = []
        self.link_counter = 0
