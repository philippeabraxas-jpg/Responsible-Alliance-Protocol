"""
TBP-V4.0 FastAPI Middleware
API Gateway enforcement for TBP policies
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import requests
import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TBPMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for TBP policy enforcement
    
    Intercepts all API requests and enforces F/I/W invariants
    before allowing request to proceed.
    """
    
    def __init__(
        self,
        app,
        opa_url: str = "http://localhost:8181",
        policy_path: str = "v1/data/tbp/core/v4",
        agent_id: str = "fastapi-app"
    ):
        super().__init__(app)
        self.opa_url = opa_url
        self.policy_path = policy_path
        self.agent_id = agent_id
    
    async def dispatch(self, request: Request, call_next):
        """
        Intercept request and check TBP policy
        """
        # Extract action context from request
        context = self._extract_context(request)
        
        # Check TBP policy
        try:
            decision = self._check_policy(context)
        except Exception as e:
            logger.error(f"TBP policy check failed: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Policy enforcement error",
                    "detail": str(e)
                }
            )
        
        # Block if not allowed
        if not decision["allowed"]:
            logger.warning(f"TBP blocked request: {decision['reason']}")
            return JSONResponse(
                status_code=403,
                content={
                    "error": "TBP Policy Violation",
                    "invariant": decision.get("invariant"),
                    "reason": decision["reason"],
                    "timestamp": decision["timestamp"],
                    "request_id": str(id(request))
                }
            )
        
        # Allow request to proceed
        logger.info(f"TBP allowed request: {request.method} {request.url.path}")
        response = await call_next(request)
        
        # Add TBP headers to response
        response.headers["X-TBP-Status"] = "compliant"
        response.headers["X-TBP-Timestamp"] = decision["timestamp"]
        
        return response
    
    def _extract_context(self, request: Request) -> Dict[str, Any]:
        """
        Extract TBP context from HTTP request
        """
        path = request.url.path
        method = request.method
        
        # Determine domain based on path
        if path.startswith("/api/finance") or path.startswith("/api/trading"):
            domain = "finance"
            operation = self._map_http_method_to_operation(method)
        elif path.startswith("/api/system") or path.startswith("/api/infrastructure"):
            domain = "system"
            operation = self._map_http_method_to_operation(method)
        elif path.startswith("/api/users") or path.startswith("/api/interact"):
            domain = "human_interaction"
            operation = "informational" if method == "GET" else "action"
        else:
            domain = "general"
            operation = self._map_http_method_to_operation(method)
        
        context = {
            "domain": domain,
            "operation": operation,
            "agent_id": self.agent_id,
            "http_method": method,
            "path": path,
            "tags": {}
        }
        
        # Add domain-specific context
        if domain == "finance":
            # Extract financial parameters from query params or body
            # In production, parse request body
            pass
        elif domain == "system":
            # Categorize system paths
            if "kernel" in path or "/sys/" in path:
                context["path_category"] = "kernel_config"
            elif "security" in path and "logs" in path:
                context["path_category"] = "security_logs"
            elif "config" in path:
                context["path_category"] = "config"
            else:
                context["path_category"] = "user_data"
        
        return context
    
    def _map_http_method_to_operation(self, method: str) -> str:
        """Map HTTP methods to TBP operations"""
        mapping = {
            "GET": "read",
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete"
        }
        return mapping.get(method, "unknown")
    
    def _check_policy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query OPA for policy decision
        """
        # Check if action is allowed
        allow_response = requests.post(
            f"{self.opa_url}/{self.policy_path}/allow",
            json={"input": context},
            timeout=5
        )
        allow_response.raise_for_status()
        allowed = allow_response.json().get("result", False)
        
        result = {
            "allowed": allowed,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if not allowed:
            # Get denial reason
            reason_response = requests.post(
                f"{self.opa_url}/{self.policy_path}/denial_reason",
                json={"input": context},
                timeout=5
            )
            result["reason"] = reason_response.json().get(
                "result",
                "Action blocked by TBP policy"
            )
            
            # Get triggered invariant
            inv_response = requests.post(
                f"{self.opa_url}/{self.policy_path}/triggered_invariant",
                json={"input": context},
                timeout=5
            )
            result["invariant"] = inv_response.json().get("result")
            
            # Get decision log
            log_response = requests.post(
                f"{self.opa_url}/{self.policy_path}/decision_log",
                json={"input": context},
                timeout=5
            )
            result["decision_log"] = log_response.json().get("result", {})
        
        return result


# =============================================================================
# Example FastAPI Application
# =============================================================================

app = FastAPI(title="TBP-Protected API")

# Add TBP middleware
app.add_middleware(
    TBPMiddleware,
    opa_url="http://localhost:8181",
    agent_id="fastapi-demo-001"
)


# =============================================================================
# Finance Endpoints
# =============================================================================

@app.post("/api/finance/trade")
async def execute_trade(
    symbol: str,
    amount: float,
    approved: bool = False
):
    """
    Execute a trade (TBP F-STABILITY enforced via middleware)
    """
    # Business logic here
    return {
        "status": "success",
        "trade": {
            "symbol": symbol,
            "amount": amount,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }


@app.get("/api/finance/balance")
async def get_balance(account_id: str):
    """
    Get account balance (TBP F-STABILITY enforced)
    """
    # Business logic here
    return {
        "account_id": account_id,
        "balance": 100000.00
    }


# =============================================================================
# System Endpoints
# =============================================================================

@app.get("/api/system/file")
async def read_file(path: str):
    """
    Read a system file (TBP I-INTEGRITY enforced)
    """
    # Business logic here
    return {
        "path": path,
        "content": "File contents here..."
    }


@app.post("/api/system/config")
async def update_config(key: str, value: str, approved: bool = False):
    """
    Update system configuration (TBP I-INTEGRITY enforced)
    """
    # Business logic here
    return {
        "status": "success",
        "config": {
            "key": key,
            "value": value
        }
    }


# =============================================================================
# Human Interaction Endpoints
# =============================================================================

@app.post("/api/interact/message")
async def send_message(user_id: str, message: str, message_type: str = "informational"):
    """
    Send message to user (TBP W-MONOPOLY enforced)
    """
    # Business logic here
    return {
        "status": "sent",
        "user_id": user_id,
        "message": message
    }


# =============================================================================
# Health Check (No TBP enforcement)
# =============================================================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint (bypasses TBP)
    """
    return {"status": "healthy"}


# =============================================================================
# TBP Status Endpoint
# =============================================================================

@app.get("/tbp/status")
async def tbp_status():
    """
    Check TBP enforcement status
    """
    try:
        # Query OPA health
        response = requests.get("http://localhost:8181/health", timeout=2)
        opa_healthy = response.status_code == 200
    except:
        opa_healthy = False
    
    return {
        "tbp_version": "4.0",
        "opa_connected": opa_healthy,
        "enforcement_active": opa_healthy
    }


# =============================================================================
# Usage
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Start OPA server first:
    # opa run --server --bundle tbp-policies/
    
    # Start FastAPI app
    print("Starting TBP-protected API...")
    print("OPA should be running at http://localhost:8181")
    print("API will be available at http://localhost:8000")
    print("\nEndpoints:")
    print("  POST /api/finance/trade")
    print("  GET  /api/finance/balance")
    print("  GET  /api/system/file")
    print("  POST /api/system/config")
    print("  POST /api/interact/message")
    print("  GET  /tbp/status")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
