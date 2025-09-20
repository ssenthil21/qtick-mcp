# diag_mcp.py
import sys, importlib.util, importlib.metadata

print("Python:", sys.version)
print("Executable:", sys.executable)

def has(spec):
    return importlib.util.find_spec(spec) is not None

# Safely get package version via metadata (works even if module lacks __version__)
def pkg_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "NOT INSTALLED"

print("mcp package version:", pkg_version("mcp"))

print("Has mcp.client.session?        ", has("mcp.client.session"))
print("Has mcp.client.streamablehttp? ", has("mcp.client.streamablehttp"))
print("Has mcp.client.sse?            ", has("mcp.client.sse"))
