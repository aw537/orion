# Orion services follow two patterns:
#
# 1. Module-level functions (e.g. audit_service.py, galaxy_service.py)
#    - Functions at module scope, imported as `from app.services import audit_service`
#
# 2. Class + singleton instance (e.g. graph_service.py, brain_service.py)
#    - Class with methods, module-level singleton: `graph_service = GraphService()`
#    - Imported as `from app.services.graph_service import graph_service`
#
# New services should use pattern 2 (class + singleton) for consistency
# and easier testing via dependency injection.
