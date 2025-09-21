# TEST_mcp_client_sse.py (point to /sse/messages/)
import os
import asyncio
import logging

from mcp.client.sse import sse_client
try:
    from mcp.client.session import ClientSession  # NEW
except ImportError:
    from mcp.shared.session import ClientSession  # OLD

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s", force=True)
for name in ["mcp", "mcp.client", "mcp.shared", "httpx", "anyio"]:
    logging.getLogger(name).setLevel(logging.DEBUG)

# IMPORTANT: point to /sse/messages/
BASE = os.getenv("TEST_MCP_SSE", "http://127.0.0.1:8000/sse/messages/")
HEADERS = {}

async def main():
    print("TEST_MCP_SSE =", BASE)
    async with sse_client(BASE, headers=HEADERS) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])

            res = await s.call_tool("ping", {"message": "hello"})
            print("PING RESULT:", res)

if __name__ == "__main__":
    asyncio.run(main())
