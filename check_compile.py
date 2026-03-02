import py_compile
import sys

try:
    py_compile.compile(r'routes\new_subscription_routes.py', doraise=True)
    print("COMPILE_OK")
except py_compile.PyCompileError as e:
    print(f"COMPILE_ERROR: {e}")
    sys.exit(1)
