# TEST_mcp_client_stream.py (works across MCP versions)
import os
import asyncio
import logging

# Transport
from mcp.client.streamable_http import streamablehttp_client

# ClientSession moved in newer MCP; try new path, then fallback
try:
    from mcp.client.session import ClientSession  # NEWER VERSIONS
except ImportError:
    from mcp.shared.session import ClientSession  # OLDER VERSIONS

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    force=True,
)
for name in ["mcp", "mcp.client", "mcp.shared", "httpx", "anyio"]:
    logging.getLogger(name).setLevel(logging.DEBUG)

BASE = os.getenv("TEST_MCP_BASE", "http://127.0.0.1:8000/mcp")
HEADERS = {}

async def main():
    print("TEST_MCP_BASE =", BASE)
    async with streamablehttp_client(BASE, headers=HEADERS) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            names = [t.name for t in tools.tools]
            print("TOOLS:", names)

            res = await s.call_tool("ping", {"message": "hello"})
            print("PING RESULT:", res)

if __name__ == "__main__":
    asyncio.run(main())
