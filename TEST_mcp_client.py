
# TEST_mcp_client.py
import asyncio, os
from mcp.client.session import ClientSession
from mcp.client.streamablehttp import streamablehttp_client

async def main():
    base = os.getenv("TEST_MCP_BASE", "http://127.0.0.1:8000/mcp")
    async with streamablehttp_client(base) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])

if __name__ == "__main__":
    asyncio.run(main())
