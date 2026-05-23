"""
Network Simulator - Protocol Implementations
1. CRC              - Error Control (Cyclic Redundancy Check)
2. CSMA/CD          - Access Control
3. StopAndWait      - Flow Control ARQ  (window = 1)
4. GoBackN          - Flow Control ARQ  (sliding window, retransmit from error)
5. SelectiveRepeat  - Flow Control ARQ  (sliding window, retransmit ONLY lost frame)
"""

import random


# ─────────────────────────────────────────────
# 1. CRC - Cyclic Redundancy Check
# ─────────────────────────────────────────────

class CRC:
    GENERATOR = "10011"

    @staticmethod
    def xor(a, b):
        result = ""
        for i in range(1, len(b)):
            result += "0" if a[i] == b[i] else "1"
        return result

    @staticmethod
    def mod2div(dividend, divisor):
        pick = len(divisor)
        tmp = dividend[:pick]
        while pick < len(dividend):
            if tmp[0] == "1":
                tmp = CRC.xor(divisor, tmp) + dividend[pick]
            else:
                tmp = CRC.xor("0" * pick, tmp) + dividend[pick]
            pick += 1
        if tmp[0] == "1":
            tmp = CRC.xor(divisor, tmp)
        else:
            tmp = CRC.xor("0" * pick, tmp)
        return tmp

    @staticmethod
    def encode(data):
        bits = "".join(format(ord(c), "08b") for c in data)
        appended = bits + "0" * (len(CRC.GENERATOR) - 1)
        remainder = CRC.mod2div(appended, CRC.GENERATOR)
        return bits + remainder, remainder

    @staticmethod
    def verify(codeword):
        remainder = CRC.mod2div(codeword, CRC.GENERATOR)
        return all(b == "0" for b in remainder), remainder

    @staticmethod
    def introduce_error(codeword):
        pos = random.randint(0, len(codeword) - 1)
        bits = list(codeword)
        bits[pos] = "1" if bits[pos] == "0" else "0"
        return "".join(bits)

    @staticmethod
    def run(data, simulate_error=False):
        codeword, remainder = CRC.encode(data)
        received = CRC.introduce_error(codeword) if simulate_error else codeword
        is_valid, check = CRC.verify(received)
        return {
            "protocol": "CRC",
            "original_data": data,
            "generator": CRC.GENERATOR,
            "codeword": codeword,
            "remainder": remainder,
            "received": received,
            "error_introduced": simulate_error,
            "is_valid": is_valid,
            "check_remainder": check,
            "status": "ACCEPTED" if is_valid else "ERROR DETECTED - Frame Discarded",
        }


# ─────────────────────────────────────────────
# 2. CSMA/CD - Access Control
# ─────────────────────────────────────────────

class CSMACD:
    MAX_ATTEMPTS = 16

    def __init__(self, device_id):
        self.device_id = device_id

    def transmit(self, frame_data, channel_busy=False):
        steps = []
        attempts = 0

        while attempts < self.MAX_ATTEMPTS:
            if channel_busy:
                steps.append({"attempt": attempts + 1, "step": "SENSE",
                               "result": "Channel BUSY - waiting", "backoff_slots": 0})
                channel_busy = random.choice([True, False])
                continue

            steps.append({"attempt": attempts + 1, "step": "TRANSMIT",
                           "result": "Channel IDLE - transmitting", "backoff_slots": 0})

            collision = random.random() < (0.3 / (attempts + 1))

            if collision:
                attempts += 1
                backoff = random.randint(0, (2 ** min(attempts, 10)) - 1)
                steps.append({"attempt": attempts, "step": "COLLISION",
                               "result": f"Collision! JAM sent. Backoff = {backoff} slots",
                               "backoff_slots": backoff})
                channel_busy = False
            else:
                steps.append({"attempt": attempts + 1, "step": "SUCCESS",
                               "result": "Frame transmitted successfully", "backoff_slots": 0})
                return {"protocol": "CSMA/CD", "device": self.device_id,
                        "success": True, "attempts": attempts + 1,
                        "steps": steps, "status": "TRANSMITTED"}

        return {"protocol": "CSMA/CD", "device": self.device_id,
                "success": False, "attempts": attempts,
                "steps": steps, "status": "FAILED - Max retries exceeded"}


# ─────────────────────────────────────────────
# 3. Stop-and-Wait ARQ
#    Window size = 1.
#    Sender transmits one frame, waits for ACK.
#    On NAK/timeout it retransmits the SAME frame.
# ─────────────────────────────────────────────

class StopAndWait:
    def __init__(self, error_rate=0.2):
        self.error_rate = error_rate

    def simulate(self, frames):
        total = len(frames)
        events = []
        transmissions = 0
        retransmissions = 0
        i = 0

        while i < total:
            is_error = random.random() < self.error_rate
            transmissions += 1

            if is_error:
                events.append({
                    "event": "SEND",
                    "seq": i,
                    "frame": frames[i],
                    "status": "ERROR - lost/corrupted",
                    "window": "[W=1]",
                })
                retransmissions += 1
                events.append({
                    "event": "NAK/TIMEOUT",
                    "seq": i,
                    "status": f"Timeout — retransmit frame {i}",
                    "window": "[W=1]",
                })
                # i stays the same → same frame retransmitted next loop
            else:
                events.append({
                    "event": "SEND",
                    "seq": i,
                    "frame": frames[i],
                    "status": "OK",
                    "window": "[W=1]",
                })
                events.append({
                    "event": "ACK",
                    "seq": i,
                    "status": f"ACK {i} received — send next frame",
                    "window": "[W=1]",
                })
                i += 1  # advance only on success

        efficiency = round((total / transmissions) * 100, 1) if transmissions > 0 else 100

        return {
            "protocol": "Stop-and-Wait ARQ",
            "window_size": 1,
            "total_frames": total,
            "transmissions": transmissions,
            "retransmissions": retransmissions,
            "efficiency": f"{efficiency}%",
            "events": events,
            "status": "ALL FRAMES DELIVERED",
        }


# ─────────────────────────────────────────────
# 4. Go-Back-N ARQ - Sliding Window
#    On error: go back and retransmit ALL frames
#    starting from the errored frame.
# ─────────────────────────────────────────────

class GoBackN:
    def __init__(self, window_size=4, error_rate=0.2):
        self.window_size = window_size
        self.error_rate = error_rate

    def simulate(self, frames):
        total = len(frames)
        send_base = 0
        next_seq = 0
        events = []
        transmissions = 0
        retransmissions = 0

        while send_base < total:
            # Fill window
            while next_seq < total and next_seq < send_base + self.window_size:
                is_error = random.random() < self.error_rate
                win = f"[{send_base} to {min(send_base + self.window_size - 1, total - 1)}]"
                events.append({
                    "event": "SEND",
                    "seq": next_seq,
                    "frame": frames[next_seq],
                    "status": "ERROR" if is_error else "OK",
                    "window": win,
                })
                transmissions += 1
                next_seq += 1

            ack_seq = send_base
            gone_back = False

            while ack_seq < next_seq and not gone_back:
                is_error = random.random() < self.error_rate
                win = f"[{send_base} to {min(send_base + self.window_size - 1, total - 1)}]"
                if is_error:
                    events.append({
                        "event": "NAK/TIMEOUT",
                        "seq": ack_seq,
                        "status": f"GO-BACK — Retransmit from frame {ack_seq}",
                        "window": win,
                    })
                    retransmissions += next_seq - ack_seq
                    transmissions += next_seq - ack_seq
                    next_seq = ack_seq
                    gone_back = True
                else:
                    events.append({
                        "event": "ACK",
                        "seq": ack_seq,
                        "status": f"ACK {ack_seq} received — window slides",
                        "window": win,
                    })
                    send_base += 1
                    ack_seq += 1

        efficiency = round((total / transmissions) * 100, 1) if transmissions > 0 else 100

        return {
            "protocol": "Go-Back-N ARQ",
            "window_size": self.window_size,
            "total_frames": total,
            "transmissions": transmissions,
            "retransmissions": retransmissions,
            "efficiency": f"{efficiency}%",
            "events": events,
            "status": "ALL FRAMES DELIVERED",
        }


# ─────────────────────────────────────────────
# 5. Selective Repeat ARQ - Sliding Window
#    On error: retransmit ONLY the lost frame.
#    Receiver buffers out-of-order frames.
# ─────────────────────────────────────────────

class SelectiveRepeat:
    def __init__(self, window_size=4, error_rate=0.2):
        self.window_size = window_size
        self.error_rate = error_rate

    def simulate(self, frames):
        total = len(frames)
        events = []
        transmissions = 0
        retransmissions = 0

        acked = [False] * total
        send_base = 0
        next_seq = 0

        while send_base < total:
            # Fill the window
            while next_seq < total and next_seq < send_base + self.window_size:
                is_error = random.random() < self.error_rate
                win = f"[{send_base} to {min(send_base + self.window_size - 1, total - 1)}]"
                events.append({
                    "event": "SEND",
                    "seq": next_seq,
                    "frame": frames[next_seq],
                    "status": "ERROR" if is_error else "OK",
                    "window": win,
                })
                transmissions += 1
                if not is_error:
                    acked[next_seq] = True
                next_seq += 1

            # Process ACKs / selective retransmits
            for seq in range(send_base, min(send_base + self.window_size, total)):
                win = f"[{send_base} to {min(send_base + self.window_size - 1, total - 1)}]"
                if not acked[seq]:
                    events.append({
                        "event": "NAK/TIMEOUT",
                        "seq": seq,
                        "status": f"SELECTIVE retransmit frame {seq} only",
                        "window": win,
                    })
                    retransmissions += 1
                    transmissions += 1
                    acked[seq] = True   # retransmit assumed successful
                    events.append({
                        "event": "ACK",
                        "seq": seq,
                        "status": f"ACK {seq} received after selective retransmit",
                        "window": win,
                    })
                else:
                    events.append({
                        "event": "ACK",
                        "seq": seq,
                        "status": f"ACK {seq} received — window slides",
                        "window": win,
                    })

            # Slide window
            while send_base < total and acked[send_base]:
                send_base += 1
            if next_seq < send_base:
                next_seq = send_base

        efficiency = round((total / transmissions) * 100, 1) if transmissions > 0 else 100

        return {
            "protocol": "Selective Repeat ARQ",
            "window_size": self.window_size,
            "total_frames": total,
            "transmissions": transmissions,
            "retransmissions": retransmissions,
            "efficiency": f"{efficiency}%",
            "events": events,
            "status": "ALL FRAMES DELIVERED",
        }
