#!/usr/bin/env python3
"""
Illustrative MCP server skeleton — driving an undocumented enterprise BPM
form system as AI-Agent-callable tools.

================================ READ ME ================================
This is an ILLUSTRATIVE SKELETON, not the production tool.

It demonstrates the *architecture* of how I wrapped a closed, undocumented
enterprise form system into a Model Context Protocol (MCP) toolchain so an
AI agent can drive it. To stay within responsible-disclosure limits:

  * The vendor / product is intentionally unnamed.
  * The client-side authentication is intentionally a STUB (see `_auth_header`).
    The real scheme was reverse-engineered; its algorithm is NOT published.
  * The backend is a MOCK (in-memory dict). No real hosts, IDs, or data.

What is faithful here is the *shape*: the tool definitions, the request
envelope, and how a legacy system gets exposed as a stable, agent-callable
interface. That shape is the transferable part.
========================================================================
"""

import json
import os
import sys
import uuid

# Placeholder — real deployments inject this via env, never hard-coded.
BASE_URL = os.environ.get("FORM_SYSTEM_BASE_URL", "http://<form-system-host>/")


# --------------------------------------------------------------------------
# Backend client — wraps the legacy form system's API behind clean methods.
# --------------------------------------------------------------------------
class FormSystemClient:
    """Thin client over the (undocumented) BPM form system's HTTP API.

    In production each verb maps to a reverse-engineered endpoint. Here the
    backend is an in-memory mock so the skeleton runs without a live system.
    """

    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self._mock_store = {}  # uid -> form definition (mock backend)

    def _auth_header(self, body: str) -> dict:
        """Compute the per-request auth header the server expects.

        STUB. The production system uses a custom client-side scheme that I
        reverse-engineered to call its API programmatically. The actual
        algorithm is deliberately omitted (responsible disclosure).

        A real implementation returns something like:
            {"Authorization": <token derived from body + nonce>}
        """
        return {"Authorization": "<computed-client-side-token>"}

    def _call(self, endpoint: str, payload: dict) -> dict:
        """Single choke point for every API call: serialize, sign, send.

        Centralizing auth + transport here is what made the whole surface
        automatable — every tool below is just a thin wrapper over `_call`.
        """
        body = json.dumps(payload, ensure_ascii=False)
        headers = {"Content-Type": "application/json", **self._auth_header(body)}
        # Production: POST f"{self.base_url}{endpoint}" with `body` + `headers`.
        # Mock: dispatch against the in-memory store instead of the network.
        return self._mock_dispatch(endpoint, payload)

    # --- form lifecycle (the 6 core tools map onto these) -----------------

    def list_forms(self) -> list:
        return self._call("form/list", {})

    def read_form(self, uid: str) -> dict:
        return self._call("form/read", {"uid": uid})

    def create_form(self, name: str, fields: list) -> dict:
        uid = str(uuid.uuid4())
        return self._call("form/create", {"uid": uid, "name": name, "fields": fields})

    def update_form(self, uid: str, fields: list) -> dict:
        return self._call("form/update", {"uid": uid, "fields": fields})

    def deploy_form(self, uid: str) -> dict:
        return self._call("form/deploy", {"uid": uid})

    def clone_form(self, src_uid: str, name: str) -> dict:
        dst_uid = str(uuid.uuid4())
        return self._call("form/clone", {"src": src_uid, "dst": dst_uid, "name": name})

    # The same pattern extends to the data-source subsystem (list/read/create);
    # omitted here to keep the skeleton focused on the form lifecycle.

    # --- mock backend (replace with real HTTP in production) --------------

    def _mock_dispatch(self, endpoint: str, p: dict) -> dict:
        if endpoint == "form/list":
            return [{"uid": u, "name": f["name"]} for u, f in self._mock_store.items()]
        if endpoint == "form/read":
            return self._mock_store.get(p["uid"], {"error": "not found"})
        if endpoint in ("form/create", "form/update"):
            uid = p["uid"]
            self._mock_store[uid] = {"name": p.get("name", self._mock_store.get(uid, {}).get("name", "")),
                                     "fields": p["fields"], "deployed": False}
            return {"uid": uid, "ok": True}
        if endpoint == "form/deploy":
            self._mock_store.setdefault(p["uid"], {}).update(deployed=True)
            return {"uid": p["uid"], "deployed": True}
        if endpoint == "form/clone":
            src = self._mock_store.get(p["src"], {})
            self._mock_store[p["dst"]] = {"name": p["name"], "fields": src.get("fields", []), "deployed": False}
            return {"uid": p["dst"], "ok": True}
        return {"error": f"unknown endpoint {endpoint}"}


# --------------------------------------------------------------------------
# MCP tool definitions — what the AI agent sees.
# --------------------------------------------------------------------------
TOOLS = [
    {"name": "form_list", "description": "List all forms in the system.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "form_read", "description": "Read one form's full schema by uid.",
     "inputSchema": {"type": "object", "properties": {"uid": {"type": "string"}}, "required": ["uid"]}},
    {"name": "form_create", "description": "Create a form from a name + field list.",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string"},
         "fields": {"type": "array", "items": {"type": "object"}}}, "required": ["name", "fields"]}},
    {"name": "form_update", "description": "Update an existing form's fields.",
     "inputSchema": {"type": "object", "properties": {
         "uid": {"type": "string"},
         "fields": {"type": "array", "items": {"type": "object"}}}, "required": ["uid", "fields"]}},
    {"name": "form_deploy", "description": "Deploy (publish) a form so it goes live.",
     "inputSchema": {"type": "object", "properties": {"uid": {"type": "string"}}, "required": ["uid"]}},
    {"name": "form_clone", "description": "Clone an existing form as a template under a new name.",
     "inputSchema": {"type": "object", "properties": {
         "src_uid": {"type": "string"}, "name": {"type": "string"}}, "required": ["src_uid", "name"]}},
]

_client = FormSystemClient()

_DISPATCH = {
    "form_list":   lambda a: _client.list_forms(),
    "form_read":   lambda a: _client.read_form(a["uid"]),
    "form_create": lambda a: _client.create_form(a["name"], a["fields"]),
    "form_update": lambda a: _client.update_form(a["uid"], a["fields"]),
    "form_deploy": lambda a: _client.deploy_form(a["uid"]),
    "form_clone":  lambda a: _client.clone_form(a["src_uid"], a["name"]),
}


def call_tool(name: str, args: dict):
    if name not in _DISPATCH:
        raise ValueError(f"unknown tool: {name}")
    return _DISPATCH[name](args)


# --------------------------------------------------------------------------
# Minimal MCP stdio loop (JSON-RPC over stdin/stdout).
# --------------------------------------------------------------------------
def handle(req: dict) -> dict:
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05",
                  "serverInfo": {"name": "eip-form-mcp", "version": "0.1.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = req.get("params", {})
        out = call_tool(params["name"], params.get("arguments", {}))
        result = {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}]}
    else:
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        resp = handle(json.loads(line))
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
