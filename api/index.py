"""Deployment entrypoint forwarding to the existing Tiger Data FastAPI app."""
from backend.main import app as backend_app


class ApiEntrypoint:
    """Accept both Vercel /api/... rewrites and direct ASGI route paths."""
    async def __call__(self, scope, receive, send):
        if scope['type'] in ('http', 'websocket') and (scope['path']=='/api' or scope['path'].startswith('/api/')):
            scope=dict(scope)
            scope['path']=scope['path'][4:] or '/'
            scope['root_path']=scope.get('root_path','').rstrip('/')+'/api'
            if scope.get('raw_path',b'').startswith(b'/api'):
                scope['raw_path']=scope['raw_path'][4:] or b'/'
        await backend_app(scope,receive,send)


app=ApiEntrypoint()
