#!/usr/bin/env python3
"""
Illustrative "agent session": a natural-language intent becomes a sequence of
tool calls that builds and deploys a form.

Runs against the skeleton's in-memory mock backend — no live system required:

    python examples/demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcp_server_skeleton as eip  # noqa: E402


def step(desc, tool, args):
    print(f"\n>> {desc}")
    print(f"   call: {tool}({args})")
    out = eip.call_tool(tool, args)
    print(f"   <-   {out}")
    return out


print('User intent: "Clone our standard approval template into a Leave Request '
      'form, add a reason and days field, then deploy it."')
print("\n--- the agent translates that into tool calls ---")

template = step("Create a standard approval template (so there is something to clone)",
                "form_create",
                {"name": "Standard Approval Template",
                 "fields": [{"id": "applicant", "label": "Applicant"}]})

clone = step("Clone the template as 'Leave Request'",
             "form_clone", {"src_uid": template["uid"], "name": "Leave Request"})

step("Add the leave-specific fields",
     "form_update",
     {"uid": clone["uid"],
      "fields": [{"id": "applicant", "label": "Applicant"},
                 {"id": "reason", "label": "Reason"},
                 {"id": "days", "label": "Days"}]})

step("Deploy the form so it goes live", "form_deploy", {"uid": clone["uid"]})

forms = step("List forms to confirm", "form_list", {})

print(f"\nResult: one natural-language instruction -> {len(forms)} form(s) "
      "created and deployed, without ever touching the back-office UI.")
