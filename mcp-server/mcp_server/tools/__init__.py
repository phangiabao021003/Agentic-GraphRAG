# Deliberately empty: importing mcp_server.tools.<submodule> must NOT pull in the
# FastMCP registry (mcp_server/tools/registry.py), which imports mcp_server.models and loads
# every ML model. Tests import submodules directly and stay model-free.
