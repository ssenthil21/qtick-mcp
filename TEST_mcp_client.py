# TEST_mcp_client.py
import asyncio, os, sys

from mcp.client.session import ClientSession

# Try Streamable HTTP first
try:
    from mcp.client.streamablehttp import streamablehttp_client
    TRANSPORT = "streamablehttp"
except Exception:
    streamablehttp_client = None
    TRANSPORT = "sse"
    from mcp.client.sse import sse_client  # SSE is widely available in current MCP clients

async def main():
    # default URLs: /mcp for streamable HTTP; /sse for SSE
    url = os.getenv("TEST_MCP_BASE", "http://127.0.0.1:8000/mcp" if TRANSPORT=="streamablehttp" else "http://127.0.0.1:8000/sse")
    headers = {"X-API-Key": os.getenv("QTF_API_KEY")} if os.getenv("QTF_API_KEY") else None

    if TRANSPORT == "streamablehttp":
        async with streamablehttp_client(url, headers=headers) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = await s.list_tools()
                print("TOOLS:", [t.name for t in tools.tools])
    else:
        async with sse_client(url, headers=headers) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = await s.list_tools()
                print("TOOLS:", [t.name for t in tools.tools])

if __name__ == "__main__":
    asyncio.run(main())
