# Deliberately empty: importing app.tools.<submodule> must NOT pull in the
# FastMCP registry (app/tools/registry.py), which imports app.models and loads
# every ML model. Tests import submodules directly and stay model-free.
