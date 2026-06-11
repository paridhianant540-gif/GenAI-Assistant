import sys
from fastapi import APIRouter, Request

router = APIRouter(tags=["Health"])

@router.get("/health")
def health_check(request: Request):
    """Provides standard API health checking capability and diagnostics."""
    # Collect registered routes
    app_routes = []
    try:
        from starlette.routing import Route, Mount, WebSocketRoute
        for r in request.app.routes:
            if isinstance(r, Route):
                app_routes.append(f"HTTP {r.path} {list(r.methods or [])}")
            elif isinstance(r, WebSocketRoute):
                app_routes.append(f"WS {r.path}")
            elif isinstance(r, Mount):
                app_routes.append(f"MOUNT {r.path}")
            else:
                app_routes.append(f"UNKNOWN {r.path}")
    except Exception as e:
        app_routes = [f"Error listing routes: {str(e)}"]

    # Check imported / importable websocket libraries
    ws_imports = {}
    for lib in ["websockets", "wsproto", "uvicorn"]:
        try:
            __import__(lib)
            ws_imports[lib] = "available"
        except ImportError as e:
            ws_imports[lib] = f"missing: {str(e)}"

    # Get installed packages list using pkg_resources or importlib.metadata
    installed_packages = []
    try:
        import importlib.metadata
        installed_packages = [f"{dist.metadata['Name']}=={dist.version}" for dist in importlib.metadata.distributions()]
    except Exception as e:
        try:
            import pkg_resources
            installed_packages = [f"{d.project_name}=={d.version}" for d in pkg_resources.working_set]
        except Exception as e2:
            installed_packages = [f"Error listing packages: {str(e2)}"]

    return {
        "status": "healthy",
        "python_version": sys.version,
        "ws_libraries": ws_imports,
        "routes": app_routes,
        "installed_packages": sorted(installed_packages)
    }

