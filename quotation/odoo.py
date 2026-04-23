import json
import os
import base64
from urllib import request


def _rpc(url: str, payload: dict):
    body = json.dumps({"jsonrpc": "2.0", "method": "call", "params": payload, "id": 1}).encode("utf-8")
    req = request.Request(f"{url}/jsonrpc", data=body, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=20) as res:
        data = json.loads(res.read().decode("utf-8"))
        if data.get("error"):
            raise RuntimeError(data["error"])
        return data["result"]


def create_odoo_project_from_quotation(quotation):
    url = os.getenv("ODOO_URL", "").rstrip("/")
    db = os.getenv("ODOO_DB", "")
    username = os.getenv("ODOO_USERNAME", "")
    password = os.getenv("ODOO_PASSWORD", "")
    if not all([url, db, username, password]):
        return

    uid = _rpc(
        url,
        {
            "service": "common",
            "method": "authenticate",
            "args": [db, username, password, {}],
        },
    )
    if not uid:
        return

    def execute_kw(model, method, args, kwargs=None):
        return _rpc(
            url,
            {
                "service": "object",
                "method": "execute_kw",
                "args": [db, uid, password, model, method, args, kwargs or {}],
            },
        )

    project_id = execute_kw(
        "project.project",
        "create",
        [
            {
                "name": f"{quotation.client_name} - {quotation.quotation_number}",
                "description": f"TeleCRM Quotation {quotation.quotation_number}",
                "date": quotation.expected_completion_date.isoformat() if quotation.expected_completion_date else False,
            }
        ],
    )

    for task in ["Design Phase", "Material Procurement", "Execution", "Final Handover"]:
        execute_kw("project.task", "create", [{"name": task, "project_id": project_id}])

    # Attach PDF if exists
    if quotation.pdf_file and os.path.exists(quotation.pdf_file.path):
        with open(quotation.pdf_file.path, 'rb') as f:
            pdf_data = base64.b64encode(f.read()).decode('utf-8')
        execute_kw(
            "ir.attachment",
            "create",
            [
                {
                    "name": f"{quotation.quotation_number}.pdf",
                    "datas": pdf_data,
                    "res_model": "project.project",
                    "res_id": project_id,
                    "type": "binary",
                }
            ],
        )
