"""Find Music Assistant servers on the LAN via mDNS (_mass._tcp)."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

SERVICE_TYPE = "_mass._tcp.local."


@dataclass(frozen=True)
class MassServer:
    server_id: str
    name: str
    base_url: str
    version: str


def _txt(props: dict[bytes, bytes | None], key: str) -> str | None:
    value = props.get(key.encode())
    if not value:
        return None
    return value.decode("utf-8", "replace")


def parse_mass_service(
    properties: dict[bytes, bytes | None], addresses: list[str], port: int
) -> MassServer | None:
    base_url = _txt(properties, "base_url")
    if not base_url:
        if not addresses:
            return None
        host = addresses[0]
        if ipaddress.ip_address(host).version == 6:
            host = f"[{host}]"
        base_url = f"http://{host}:{port}"
    return MassServer(
        server_id=_txt(properties, "server_id") or base_url,
        name=_txt(properties, "name") or "Music Assistant",
        base_url=base_url.rstrip("/"),
        version=_txt(properties, "server_version") or "",
    )


def _dedupe(servers: list[MassServer]) -> list[MassServer]:
    seen: set[str] = set()
    out = []
    for s in servers:
        if s.server_id not in seen:
            seen.add(s.server_id)
            out.append(s)
    return out


async def discover_mass(timeout: float = 4.0) -> list[MassServer]:
    from zeroconf import ServiceStateChange
    from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

    found: list[MassServer] = []
    pending: set[asyncio.Task] = set()
    azc = AsyncZeroconf()

    async def resolve(name: str) -> None:
        info = AsyncServiceInfo(SERVICE_TYPE, name)
        if await info.async_request(azc.zeroconf, 3000):
            server = parse_mass_service(
                info.properties, info.parsed_scoped_addresses(), info.port or 8095
            )
            if server:
                found.append(server)

    def on_change(zeroconf, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            task = asyncio.ensure_future(resolve(name))
            pending.add(task)
            task.add_done_callback(pending.discard)

    browser = AsyncServiceBrowser(azc.zeroconf, SERVICE_TYPE, handlers=[on_change])
    try:
        await asyncio.sleep(timeout)
        if pending:
            await asyncio.wait(pending, timeout=3)
    finally:
        await browser.async_cancel()
        await azc.async_close()
    return _dedupe(found)
