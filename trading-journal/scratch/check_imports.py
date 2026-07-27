import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

def scoped_import(service_name, module_path, obj_name):
    # Clear "app" modules from cache
    for key in list(sys.modules.keys()):
        if key == "app" or key.startswith("app."):
            del sys.modules[key]
            
    path = os.path.join(BASE_DIR, "backend", "bloomberg", service_name)
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        mod = __import__(module_path, fromlist=[obj_name])
        return getattr(mod, obj_name)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None
    finally:
        if path in sys.path:
            sys.path.remove(path)

print("Importing SystemicUniverseAdapter...")
adapter = scoped_import("collector-service", "app.fetchers", "SystemicUniverseAdapter")
print("Adapter:", adapter)

print("Importing TopologyEngine...")
topology = scoped_import("../Correlaciones", "TopologyEngine", "TopologyEngine")
print("Topology:", topology)

print("Importing run_swarm...")
swarm = scoped_import("mirofish", "app.main", "run_swarm")
print("Swarm:", swarm)
