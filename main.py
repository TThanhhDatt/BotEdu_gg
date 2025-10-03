import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from core.graph.build_graph import create_main_graph

from api.v1.routes import router as api_router_v1
from api.v2.routes import router as api_router_v2
from api.v3.routes import router as api_router_v3

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup
#     graph = create_main_graph()
#     app.state.graph = graph
    
#     # Start cleanup task
#     graph.cleanup_manager.start_cleanup_task()
    
#     yield
    
#     # Shutdown
#     graph.cleanup_manager.stop_cleanup_task()

# Create a FastAPI app instance
app = FastAPI(
    title="Chatbot customer service project", 
    # lifespan=lifespan
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Include the API router with a prefix
app.include_router(api_router_v1, prefix="/api/v1")
app.include_router(api_router_v2, prefix="/api/v2")
app.include_router(api_router_v3, prefix="/api/v3")

# Define a root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to selling bot"}

@app.get("/health")
async def health():
    """
    Endpoint kiểm tra tình trạng dịch vụ.

    Returns:
        dict: Trạng thái "healthy" nếu ứng dụng sẵn sàng.
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    # This will only run if you execute the file directly
    # Not when using langgraph dev
    uvicorn.run(app, host="127.0.0.1", port=2024)
