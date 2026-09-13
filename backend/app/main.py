"""Main entrypoint for running the Buy or Wait API server."""
import os
import uvicorn
from .api import app

def run():
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("backend.app.api:app", host=host, port=port, reload=True)

if __name__ == "__main__":
    run()
