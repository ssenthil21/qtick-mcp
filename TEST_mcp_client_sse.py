# TEST_mcp_client_sse.py
import asyncio, os
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

async def main():
    url = os.getenv("TEST_MCP_SSE", "http://127.0.0.1:8000/sse")
    headers = {"X-API-Key": os.getenv("QTF_API_KEY")} if os.getenv("QTF_API_KEY") else None
    async with sse_client(url, headers=headers) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])
            res = await s.call_tool("ping", {})
            print("PING:", res.content[0].text if res.content else res)

if __name__ == "__main__":
    asyncio.run(main())
