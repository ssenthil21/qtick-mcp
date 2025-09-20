# TEST_mcp_client_stream.py
import asyncio, os
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client  # <-- underscore

async def main():
    url = os.getenv("TEST_MCP_BASE", "http://127.0.0.1:8000/mcp")  # no trailing slash
    headers = {"X-API-Key": os.getenv("QTF_API_KEY")} if os.getenv("QTF_API_KEY") else None
    async with streamablehttp_client(url, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])
            # If you added ping() in app/mcp_server.py:
            try:
                res = await s.call_tool("ping", {})
                print("PING:", res.content[0].text if res.content else res)
            except Exception as e:
                print("Ping not available:", e)

if __name__ == "__main__":
    asyncio.run(main())
