"""
Main-actor analyzer for network captures (.pcap / .pcapng)

Requires: pip install scapy --break-system-packages
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import TypedDict, cast

from scapy.layers.inet import ICMP, IP
from scapy.layers.inet6 import ICMPv6EchoReply, ICMPv6EchoRequest, IPv6
from scapy.layers.l2 import ARP, Ether
from scapy.utils import rdpcap


class ActorAnalysis(TypedDict):
    total_packets: int
    top_macs: list[tuple[str, int]]
    top_ips: list[tuple[str, int]]
    top_conversations: list[tuple[tuple[str, str], int]]
    protocols: list[tuple[str, int]]
    ip_mac_relations: dict[str, list[str]]


async def analyze_actors(pcap_path: str, top_n: int = 10, verbose: bool = True) -> ActorAnalysis:
    """
    Analyzes a pcap/pcapng file and extracts the main actors:
    - Most active MAC and IP addresses
    - IP-MAC relationships (who claims to be whom, useful for detecting ARP spoofing)
    - Most frequent conversations (source -> destination pairs)
    - Summary of protocols present

    Returns a dictionary with the results, and if verbose=True
    also prints a human-readable summary to the screen.
    """
    packets = rdpcap(pcap_path)

    mac_counter: Counter[str] = Counter()
    ip_counter: Counter[str] = Counter()
    conversations: Counter[tuple[str, str]] = Counter()
    protocols: Counter[str] = Counter()
    mac_to_ip: defaultdict[str, set[str]] = defaultdict(set)  # IPs each MAC announces (via ARP)
    ip_to_mac: defaultdict[str, set[str]] = defaultdict(set)  # MACs associated with each IP

    for pkt in packets:
        # --- Ethernet layer: MACs ---
        if pkt.haslayer(Ether):
            eth = cast(Ether, pkt.getlayer(Ether))
            mac_counter[eth.src] += 1
            mac_counter[eth.dst] += 1

        # --- ARP: who claims to be whom ---
        if pkt.haslayer(ARP):
            arp = cast(ARP, pkt.getlayer(ARP))
            protocols["ARP"] += 1
            if arp.op == 2:  # is-at (reply)
                mac_to_ip[arp.hwsrc].add(arp.psrc)
                ip_to_mac[arp.psrc].add(arp.hwsrc)
            ip_counter[arp.psrc] += 1
            if arp.pdst != "0.0.0.0":
                ip_counter[arp.pdst] += 1

        # --- IPv4 ---
        elif pkt.haslayer(IP):
            ip = cast(IP, pkt.getlayer(IP))
            ip_counter[ip.src] += 1
            ip_counter[ip.dst] += 1
            conversations[(ip.src, ip.dst)] += 1
            if pkt.haslayer(ICMP):
                protocols["ICMPv4"] += 1
            else:
                protocols["IPv4 (other)"] += 1

        # --- IPv6 ---
        elif pkt.haslayer(IPv6):
            ip6 = cast(IPv6, pkt.getlayer(IPv6))
            ip_counter[ip6.src] += 1
            ip_counter[ip6.dst] += 1
            conversations[(ip6.src, ip6.dst)] += 1
            if pkt.haslayer(ICMPv6EchoRequest) or pkt.haslayer(ICMPv6EchoReply):
                protocols["ICMPv6 (echo)"] += 1
            elif "ICMPv6" in pkt.summary():
                protocols["ICMPv6 (other)"] += 1
            else:
                protocols["IPv6 (other)"] += 1

    result: ActorAnalysis = {
        "total_packets": len(packets),
        "top_macs": mac_counter.most_common(top_n),
        "top_ips": ip_counter.most_common(top_n),
        "top_conversations": conversations.most_common(top_n),
        "protocols": protocols.most_common(),
        "ip_mac_relations": {ip: sorted(macs) for ip, macs in ip_to_mac.items()},
    }

    if verbose:
        print(f"📦 Total packets: {result['total_packets']}\n")

        print("🔌 Protocols detected:")
        for proto, n in result["protocols"]:
            print(f"   {proto}: {n}")

        print("\n🖥️  Most active MACs:")
        for mac, n in result["top_macs"]:
            print(f"   {mac}: {n} packets")

        print("\n🌐 Most active IPs:")
        for ip_addr, n in result["top_ips"]:
            print(f"   {ip_addr}: {n} packets")

        print("\n💬 Most frequent conversations (source -> destination):")
        for (src, dst), n in result["top_conversations"]:
            print(f"   {src} -> {dst}: {n} packets")

        if result["ip_mac_relations"]:
            print("\n🔗 IP <-> MAC relationship (from ARP):")
            for ip_addr, macs in result["ip_mac_relations"].items():
                flag = " ⚠️ multiple MACs (possible spoofing)" if len(macs) > 1 else ""
                print(f"   {ip_addr} -> {', '.join(macs)}{flag}")

    return result
