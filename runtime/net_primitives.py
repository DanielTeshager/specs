"""
Network Primitives

Low-level network operations: TCP connect, ping, port scan, etc.
"""

import socket
import subprocess
import platform
import concurrent.futures
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from primitives import Block, NONE
from io_adapter import Ok, Err, IOError as IOErr


# =============================================================================
# COMMON SERVICES (port -> service name)
# =============================================================================

COMMON_SERVICES = {
    20: "ftp-data", 21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp",
    53: "dns", 80: "http", 110: "pop3", 111: "rpc", 135: "msrpc",
    139: "netbios", 143: "imap", 443: "https", 445: "smb", 993: "imaps",
    995: "pop3s", 1433: "mssql", 1521: "oracle", 3306: "mysql",
    3389: "rdp", 5432: "postgres", 5900: "vnc", 6379: "redis",
    8080: "http-alt", 8443: "https-alt", 27017: "mongodb",
}


# =============================================================================
# TCP CONNECT
# =============================================================================

def tcp_connect(host: str, port: int, timeout: float = 1.0) -> Ok | Err:
    """
    Attempt TCP connection to host:port.
    Returns connection result.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        start = _time_ms()
        result = sock.connect_ex((host, port))
        latency = _time_ms() - start

        sock.close()

        if result == 0:
            return Ok({"status": "open", "latency_ms": latency})
        else:
            return Ok({"status": "closed", "latency_ms": latency})

    except socket.timeout:
        return Ok({"status": "filtered", "latency_ms": timeout * 1000})
    except socket.gaierror as e:
        return Err(IOErr("InvalidData", message=f"DNS resolution failed: {e}"))
    except Exception as e:
        return Err(IOErr("Unknown", message=str(e)))


def _time_ms() -> float:
    import time
    return time.time() * 1000


# =============================================================================
# PING
# =============================================================================

def ping(host: str, timeout: float = 1.0) -> Ok | Err:
    """
    Send ICMP ping to host.
    """
    try:
        # Platform-specific ping command
        param = "-n" if platform.system().lower() == "windows" else "-c"
        timeout_param = "-w" if platform.system().lower() == "windows" else "-W"

        cmd = ["ping", param, "1", timeout_param, str(int(timeout)), host]

        start = _time_ms()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
        latency = _time_ms() - start

        if result.returncode == 0:
            # Try to extract actual latency from output
            import re
            match = re.search(r'time[=<](\d+\.?\d*)', result.stdout)
            if match:
                latency = float(match.group(1))
            return Ok({"reachable": True, "latency_ms": latency})
        else:
            return Ok({"reachable": False, "latency_ms": 0})

    except subprocess.TimeoutExpired:
        return Ok({"reachable": False, "latency_ms": 0})
    except Exception as e:
        return Err(IOErr("Unknown", message=str(e)))


# =============================================================================
# DNS LOOKUP
# =============================================================================

def dns_lookup(hostname: str, record_type: str = "A") -> Ok | Err:
    """
    Resolve hostname to IP addresses.
    """
    try:
        if record_type == "A":
            results = socket.gethostbyname_ex(hostname)
            return Ok(results[2])  # List of IPs
        elif record_type == "AAAA":
            results = socket.getaddrinfo(hostname, None, socket.AF_INET6)
            ips = list(set(r[4][0] for r in results))
            return Ok(ips)
        else:
            # For MX, TXT, etc. would need dnspython library
            return Err(IOErr("InvalidData", message=f"Record type {record_type} requires dnspython"))

    except socket.gaierror as e:
        return Err(IOErr("NotFound", message=f"DNS lookup failed: {e}"))
    except Exception as e:
        return Err(IOErr("Unknown", message=str(e)))


# =============================================================================
# PORT SCAN
# =============================================================================

def port_scan(host: str, ports: List[int] | str, timeout: float = 0.5,
              max_workers: int = 100) -> Ok | Err:
    """
    Scan multiple ports on a host.
    """
    try:
        # Parse port range if string
        if isinstance(ports, str):
            ports = _parse_port_range(ports)

        open_ports = []
        start = _time_ms()

        # Scan ports concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_check_port, host, port, timeout): port
                for port in ports
            }

            for future in concurrent.futures.as_completed(futures):
                port = futures[future]
                try:
                    is_open = future.result()
                    if is_open:
                        service = COMMON_SERVICES.get(port, "unknown")
                        open_ports.append({"port": port, "service": service})
                except Exception:
                    pass

        scan_time = _time_ms() - start

        # Sort by port number
        open_ports.sort(key=lambda x: x["port"])

        return Ok({
            "host": host,
            "open_ports": open_ports,
            "scanned_ports": len(ports),
            "scan_time_ms": scan_time
        })

    except Exception as e:
        return Err(IOErr("Unknown", message=str(e)))


def _check_port(host: str, port: int, timeout: float) -> bool:
    """Check if a single port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def _parse_port_range(port_str: str) -> List[int]:
    """Parse port range string like '1-1024' or '22,80,443'"""
    ports = []
    for part in port_str.split(","):
        if "-" in part:
            start, end = part.split("-")
            ports.extend(range(int(start), int(end) + 1))
        else:
            ports.append(int(part))
    return ports


# =============================================================================
# SERVICE DETECTION
# =============================================================================

def service_detect(host: str, port: int, timeout: float = 2.0) -> Ok | Err:
    """
    Detect service running on a port by grabbing banner.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))

        # Try to receive banner
        banner = None
        try:
            # Some services send banner immediately
            sock.setblocking(False)
            import select
            ready = select.select([sock], [], [], 1.0)
            if ready[0]:
                banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
        except:
            pass

        # If no banner, try sending probe
        if not banner:
            try:
                sock.setblocking(True)
                sock.settimeout(1.0)
                # HTTP probe
                if port in (80, 8080, 8000, 8888):
                    sock.send(b"HEAD / HTTP/1.0\r\n\r\n")
                else:
                    sock.send(b"\r\n")
                banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
            except:
                pass

        sock.close()

        # Parse banner to identify service
        service = COMMON_SERVICES.get(port, "unknown")
        version = None

        if banner:
            banner_lower = banner.lower()
            if "ssh" in banner_lower:
                service = "ssh"
                if "openssh" in banner_lower:
                    import re
                    match = re.search(r'openssh[_\s]*([\d.]+)', banner_lower)
                    if match:
                        version = f"OpenSSH {match.group(1)}"
            elif "http" in banner_lower:
                service = "http"
                if "nginx" in banner_lower:
                    version = "nginx"
                elif "apache" in banner_lower:
                    version = "apache"
            elif "ftp" in banner_lower:
                service = "ftp"
            elif "smtp" in banner_lower:
                service = "smtp"

        return Ok({
            "service": service,
            "version": version,
            "banner": banner[:200] if banner else None
        })

    except socket.timeout:
        return Ok({"service": COMMON_SERVICES.get(port, "unknown"), "version": None, "banner": None})
    except ConnectionRefusedError:
        return Err(IOErr("ConnectionFailed", message="Connection refused"))
    except Exception as e:
        return Err(IOErr("Unknown", message=str(e)))


# =============================================================================
# HOST DISCOVERY
# =============================================================================

def host_discover(ip_range: str, method: str = "ping", timeout: float = 0.5,
                  max_workers: int = 50) -> Ok | Err:
    """
    Discover live hosts on a network range.
    """
    try:
        # Parse CIDR
        ips = _parse_cidr(ip_range)

        if len(ips) > 1024:
            return Err(IOErr("InvalidData", message="Range too large (max 1024 hosts)"))

        live_hosts = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            if method == "ping":
                futures = {
                    executor.submit(_ping_host, ip, timeout): ip
                    for ip in ips
                }
            else:  # tcp - check common ports
                futures = {
                    executor.submit(_tcp_probe, ip, timeout): ip
                    for ip in ips
                }

            for future in concurrent.futures.as_completed(futures):
                ip = futures[future]
                try:
                    result = future.result()
                    if result:
                        live_hosts.append(result)
                except Exception:
                    pass

        # Sort by IP
        live_hosts.sort(key=lambda x: _ip_to_int(x["ip"]))

        return Ok(live_hosts)

    except Exception as e:
        return Err(IOErr("Unknown", message=str(e)))


def _parse_cidr(cidr: str) -> List[str]:
    """Parse CIDR notation to list of IPs"""
    import ipaddress
    try:
        network = ipaddress.ip_network(cidr, strict=False)
        return [str(ip) for ip in network.hosts()]
    except ValueError as e:
        raise ValueError(f"Invalid CIDR: {e}")


def _ip_to_int(ip: str) -> int:
    """Convert IP to integer for sorting"""
    parts = ip.split(".")
    return sum(int(p) << (24 - 8*i) for i, p in enumerate(parts))


def _ping_host(ip: str, timeout: float) -> Optional[Dict]:
    """Ping a single host"""
    result = ping(ip, timeout)
    if isinstance(result, Ok) and result.value.get("reachable"):
        hostname = _reverse_dns(ip)
        return {
            "ip": ip,
            "hostname": hostname,
            "latency_ms": result.value.get("latency_ms", 0)
        }
    return None


def _tcp_probe(ip: str, timeout: float) -> Optional[Dict]:
    """TCP probe on common ports"""
    for port in [80, 443, 22, 445]:
        result = tcp_connect(ip, port, timeout)
        if isinstance(result, Ok) and result.value.get("status") == "open":
            hostname = _reverse_dns(ip)
            return {
                "ip": ip,
                "hostname": hostname,
                "latency_ms": result.value.get("latency_ms", 0)
            }
    return None


def _reverse_dns(ip: str) -> Optional[str]:
    """Attempt reverse DNS lookup"""
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        return hostname
    except:
        return None


# =============================================================================
# BLOCK WRAPPERS (for primitives system)
# =============================================================================

class Net:
    """Factory for network primitive blocks"""

    @staticmethod
    def tcp_connect(host: str = None, port: int = None, timeout: float = 1.0) -> Block:
        def connect_fn(input_):
            h = host or (input_.get("host") if isinstance(input_, dict) else input_)
            p = port or (input_.get("port") if isinstance(input_, dict) else 80)
            return tcp_connect(h, p, timeout)
        return Block(f"net.tcp_connect({host}:{port})", connect_fn)

    @staticmethod
    def ping(host: str = None, timeout: float = 1.0) -> Block:
        def ping_fn(input_):
            h = host or input_
            return ping(h, timeout)
        return Block(f"net.ping({host})", ping_fn)

    @staticmethod
    def dns_lookup(hostname: str = None, record_type: str = "A") -> Block:
        def dns_fn(input_):
            h = hostname or input_
            return dns_lookup(h, record_type)
        return Block(f"net.dns({hostname})", dns_fn)

    @staticmethod
    def port_scan(host: str = None, ports: str = "1-1024", timeout: float = 0.5) -> Block:
        def scan_fn(input_):
            h = host or input_
            return port_scan(h, ports, timeout)
        return Block(f"net.port_scan({host})", scan_fn)

    @staticmethod
    def service_detect(host: str = None, port: int = None) -> Block:
        def detect_fn(input_):
            h = host or (input_.get("host") if isinstance(input_, dict) else None)
            p = port or (input_.get("port") if isinstance(input_, dict) else None)
            return service_detect(h, p)
        return Block(f"net.service_detect({host}:{port})", detect_fn)

    @staticmethod
    def host_discover(ip_range: str = None, method: str = "ping") -> Block:
        def discover_fn(input_):
            r = ip_range or input_
            return host_discover(r, method)
        return Block(f"net.host_discover({ip_range})", discover_fn)


# Convenience exports
tcp = Net.tcp_connect
ping_host = Net.ping
dns = Net.dns_lookup
scan_ports = Net.port_scan
detect_service = Net.service_detect
discover_hosts = Net.host_discover
