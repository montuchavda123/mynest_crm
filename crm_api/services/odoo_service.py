import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any
from urllib import request
from urllib.error import URLError

from django.utils import timezone

from crm_api.models import Project
from quotation.models import Quotation

logger = logging.getLogger(__name__)


class OdooIntegrationError(Exception):
    """Raised when Odoo integration cannot proceed."""


@dataclass
class OdooConfig:
    url: str
    database: str
    username: str
    password: str
    timeout: int
    retries: int
    retry_delay: float
    create_sales_order: bool
    auto_create_tasks: bool

    @classmethod
    def from_env(cls) -> "OdooConfig":
        return cls(
            url=os.getenv("ODOO_URL", "").rstrip("/"),
            database=os.getenv("ODOO_DB", ""),
            username=os.getenv("ODOO_USERNAME", ""),
            password=os.getenv("ODOO_PASSWORD", ""),
            timeout=int(os.getenv("ODOO_TIMEOUT", "20")),
            retries=int(os.getenv("ODOO_RETRIES", "3")),
            retry_delay=float(os.getenv("ODOO_RETRY_DELAY", "1.5")),
            create_sales_order=os.getenv("ODOO_SYNC_SALE_ORDER", "false").lower() == "true",
            auto_create_tasks=os.getenv("ODOO_AUTO_CREATE_TASKS", "true").lower() == "true",
        )

    def validate(self) -> None:
        if not all([self.url, self.database, self.username, self.password]):
            raise OdooIntegrationError(
                "Missing Odoo credentials. Set ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD."
            )


class OdooService:
    def __init__(self) -> None:
        self.config = OdooConfig.from_env()
        self.config.validate()
        self.uid = self._authenticate()
        self._model_fields_cache: dict[str, set[str]] = {}

    def sync_approved_quotation(self, quotation_id: int) -> dict[str, Any]:
        try:
            quotation = (
                Quotation.objects.select_related("lead", "lead__assigned_to")
                .prefetch_related("items", "sections__items", "payment_plans", "civil_work_items")
                .get(pk=quotation_id)
            )
            if quotation.status != "APPROVED":
                raise OdooIntegrationError(
                    f"Quotation {quotation_id} is not approved. Current status: {quotation.status}"
                )

            logger.info("Starting sync for approved quotation %s (lead=%s)", quotation_id, quotation.lead.name)
            
            partner_id = self.find_or_create_partner(quotation)
            logger.info("Partner created/found: %s", partner_id)
            
            sale_order_id = self.find_or_create_sale_order(quotation, partner_id)
            logger.info("Sale order created/found: %s", sale_order_id)
            
            project_id = self.find_or_create_project(quotation, partner_id)
            logger.info("Project created/found: %s", project_id)
            
            task_ids = self.find_or_create_default_tasks(project_id) if self.config.auto_create_tasks else []
            logger.info("Tasks created: %s", len(task_ids))

            logger.info(
                "✓ Synced quotation %s to Odoo (partner=%s, sale_order=%s, project=%s, tasks=%s)",
                quotation_id,
                partner_id,
                sale_order_id,
                project_id,
                len(task_ids),
            )
            return {
                "partner_id": partner_id,
                "sale_order_id": sale_order_id,
                "project_id": project_id,
                "task_ids": task_ids,
            }
        except OdooIntegrationError as e:
            logger.error("✗ Odoo integration error for quotation %s: %s", quotation_id, str(e))
            raise
        except Exception as e:
            logger.exception("✗ Unexpected error syncing quotation %s: %s", quotation_id, str(e))
            raise OdooIntegrationError(f"Failed to sync quotation {quotation_id}: {str(e)}")

    def _authenticate(self) -> int:
        uid = self._rpc(
            "/jsonrpc",
            "call",
            {
                "service": "common",
                "method": "authenticate",
                "args": [
                    self.config.database,
                    self.config.username,
                    self.config.password,
                    {},
                ],
            },
        )
        if not uid:
            raise OdooIntegrationError("Odoo authentication failed for provided API user.")
        return uid

    def _execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        payload = {
            "service": "object",
            "method": "execute_kw",
            "args": [
                self.config.database,
                self.uid,
                self.config.password,
                model,
                method,
                args,
                kwargs or {},
            ],
        }
        return self._rpc("/jsonrpc", "call", payload)

    def _rpc(self, route: str, method: str, params: dict[str, Any]) -> Any:
        endpoint = f"{self.config.url}{route}"
        request_body = json.dumps(
            {"jsonrpc": "2.0", "method": method, "params": params, "id": int(time.time() * 1000)}
        ).encode("utf-8")

        for attempt in range(1, self.config.retries + 1):
            try:
                req = request.Request(
                    endpoint,
                    data=request_body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with request.urlopen(req, timeout=self.config.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                if data.get("error"):
                    raise OdooIntegrationError(self._format_rpc_error(data["error"]))
                return data.get("result")
            except (URLError, TimeoutError, OdooIntegrationError) as exc:
                if attempt >= self.config.retries:
                    logger.exception("Odoo API call failed after %s retries: %s", attempt, exc)
                    raise
                sleep_seconds = self.config.retry_delay * attempt
                logger.warning(
                    "Odoo API attempt %s/%s failed (%s). Retrying in %.1fs...",
                    attempt,
                    self.config.retries,
                    exc,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
        raise OdooIntegrationError("Unexpected Odoo API execution failure.")

    @staticmethod
    def _format_rpc_error(error: dict[str, Any]) -> str:
        data = error.get("data") if isinstance(error, dict) else None
        message = ""
        if isinstance(data, dict):
            message = data.get("message") or ""
            debug = data.get("debug") or ""
            if debug:
                debug_line = next((line.strip() for line in debug.splitlines() if line.strip()), "")
                if debug_line and debug_line not in message:
                    message = f"{message} | {debug_line}" if message else debug_line
        if not message:
            message = error.get("message") if isinstance(error, dict) else str(error)
        return f"Odoo RPC error: {message}"

    def _get_model_fields(self, model: str) -> set[str]:
        if model in self._model_fields_cache:
            return self._model_fields_cache[model]
        try:
            fields_data = self._execute_kw(model, "fields_get", [], {"attributes": ["type"]})
            field_names = set(fields_data.keys()) if isinstance(fields_data, dict) else set()
        except Exception as e:
            logger.warning("Unable to introspect fields for model '%s': %s", model, str(e))
            field_names = set()
        self._model_fields_cache[model] = field_names
        return field_names

    def find_or_create_partner(self, quotation: Quotation) -> int:
        lead = quotation.lead
        external_ref = f"TELECRM-LEAD-{lead.id}"

        try:
            # First, prefer a deterministic mapping between TeleCRM lead and Odoo partner.
            partner_ids = self._execute_kw(
                "res.partner",
                "search",
                [[["ref", "=", external_ref]]],
                {"limit": 1},
            )
            if partner_ids:
                logger.info("Found existing partner by ref: %s (ID:%s)", external_ref, partner_ids[0])
                return partner_ids[0]
        except Exception as e:
            logger.warning("Error searching partner by ref %s: %s", external_ref, str(e))

        # Backward compatibility for existing partners created before ref mapping.
        domain: list[list[str]] = []
        if lead.phone:
            domain = [["phone", "=", lead.phone]]
        elif lead.email:
            domain = [["email", "=", lead.email]]
        else:
            domain = [["name", "=", lead.name]]

        try:
            partner_ids = self._execute_kw("res.partner", "search", [domain], {"limit": 1})
            if partner_ids:
                partner_id = partner_ids[0]
                logger.info("Found existing partner by backward compat search (domain:%s), updating ref to %s", domain, external_ref)
                try:
                    self._execute_kw("res.partner", "write", [[partner_id], {"ref": external_ref}])
                except Exception as e:
                    logger.warning("Failed to update partner ref: %s", str(e))
                return partner_id
        except Exception as e:
            logger.warning("Error searching partner by backward compat domain %s: %s", domain, str(e))

        values = {
            "name": lead.name,
            "phone": lead.phone or "",
            "email": lead.email or "",
            "street": lead.location or "",
            "customer_rank": 1,
            "ref": external_ref,
            "active": True,
        }
        try:
            partner_id = self._execute_kw("res.partner", "create", [values])
            logger.info("✓ Created new partner: name=%s, phone=%s, email=%s, partner_id=%s, ref=%s", 
                       lead.name, lead.phone, lead.email, partner_id, external_ref)
            return partner_id
        except Exception as e:
            logger.error("✗ Failed to create partner in Odoo: %s. Values: %s", str(e), values)
            raise OdooIntegrationError(f"Failed to create partner for lead '{lead.name}': {str(e)}")


    def find_or_create_sale_order(self, quotation: Quotation, partner_id: int) -> int | None:
        if not self.config.create_sales_order:
            logger.debug("Sales order creation disabled in config, skipping sale.order creation")
            return None

        order_name = f"TELECRM-Q-{quotation.quotation_number}"
        try:
            order_ids = self._execute_kw(
                "sale.order",
                "search",
                [[["client_order_ref", "=", order_name], ["partner_id", "=", partner_id]]],
                {"limit": 1},
            )
            if order_ids:
                logger.info("Found existing sale order: ref=%s (ID:%s)", order_name, order_ids[0])
                return order_ids[0]
        except Exception as e:
            logger.warning("Error searching for existing sale order: %s", str(e))

        order_note = quotation.notes or quotation.scope_of_work or quotation.payment_terms or ""
        order_vals = {
            "partner_id": partner_id,
            "client_order_ref": order_name,
            "note": order_note,
            "date_order": timezone.now().isoformat(),
        }
        try:
            order_id = self._execute_kw("sale.order", "create", [order_vals])
            logger.info("✓ Created new sale order: ref=%s, partner_id=%s, order_id=%s", order_name, partner_id, order_id)
            return order_id
        except Exception as e:
            logger.error("✗ Failed to create sale order in Odoo: %s. Values: %s", str(e), order_vals)
            raise OdooIntegrationError(f"Failed to create sale order '{order_name}': {str(e)}")


    def find_or_create_project(self, quotation: Quotation, partner_id: int) -> int:
        lead = quotation.lead
        project_location = quotation.project_location or lead.location or "Site"
        project_kind = quotation.project_type or "Interior"
        project_name = f"{quotation.client_name} - {project_location} - {project_kind}"
        quotation_ref = str(quotation.quotation_number)
        lead_ref = str(lead.id)
        customer_ref = quotation.client_name
        domain = [["partner_id", "=", partner_id]]
        project_ids: list[int] = []

        try:
            project_fields = self._get_model_fields("project.project")
            if "telecrm_quotation_id" in project_fields:
                project_ids = self._execute_kw(
                    "project.project",
                    "search",
                    [[["telecrm_quotation_id", "=", quotation_ref]]],
                    {"limit": 1},
                )
            elif "telecrm_quotation_ref" in project_fields:
                project_ids = self._execute_kw(
                    "project.project",
                    "search",
                    [[["telecrm_quotation_ref", "=", quotation_ref]]],
                    {"limit": 1},
                )
            else:
                project_ids = self._execute_kw(
                    "project.project",
                    "search",
                    [[["name", "=", project_name], *domain]],
                    {"limit": 1},
                )
            if project_ids:
                logger.info("Found existing project: %s (ID:%s)", project_name, project_ids[0])
                return project_ids[0]
        except Exception as e:
            logger.warning("Error searching for existing project: %s", str(e))

        local_project = (
            Project.objects.filter(lead=lead).order_by("-created_at").only("start_date", "end_date", "project_name").first()
        )
        start_date = quotation.quotation_date or (local_project.start_date if local_project and local_project.start_date else timezone.now().date())
        end_date = quotation.expected_completion_date or (local_project.end_date if local_project and local_project.end_date else start_date + timedelta(days=90))
        assigned_designer = quotation.designer_name or (lead.assigned_to.get_full_name() if lead.assigned_to else "")

        budget_amount = quotation.base_amount + quotation.package_amount
        description_parts = [
            quotation.scope_of_work or "",
            quotation.notes or "",
            f"TeleCRM Quote ID: {quotation.quotation_number}",
            f"Budget: {self._to_float(budget_amount)}",
            f"Project Type: {quotation.project_type or 'Interior Design'}",
            f"Location: {quotation.project_location or lead.location or ''}",
            f"Assigned Designer: {assigned_designer}",
            f"Expected Completion Date: {end_date.isoformat()}",
        ]

        values = {
            "name": project_name,
            "partner_id": partner_id,
            "description": "\n".join([value for value in description_parts if value]),
            "active": True,
        }

        project_fields = self._get_model_fields("project.project")
        if "telecrm_quotation_id" in project_fields:
            values["telecrm_quotation_id"] = quotation_ref
        elif "telecrm_quotation_ref" in project_fields:
            values["telecrm_quotation_ref"] = quotation_ref
        if "telecrm_lead_id" in project_fields:
            values["telecrm_lead_id"] = lead_ref
        elif "telecrm_lead_ref" in project_fields:
            values["telecrm_lead_ref"] = lead_ref
        if "telecrm_customer_id" in project_fields:
            values["telecrm_customer_id"] = customer_ref
        elif "telecrm_customer_ref" in project_fields:
            values["telecrm_customer_ref"] = customer_ref
        if "site_address" in project_fields:
            values["site_address"] = project_location
        if "project_type" in project_fields and quotation.project_type:
            lowered = (quotation.project_type or "").strip().lower()
            mapped_type = "home"
            if "office" in lowered:
                mapped_type = "office"
            elif "kitchen" in lowered:
                mapped_type = "kitchen"
            elif "reno" in lowered:
                mapped_type = "renovation"
            elif "commercial" in lowered:
                mapped_type = "commercial"
            values["project_type"] = mapped_type
        supervisor_id = self._find_supervisor_user_id(quotation)
        if supervisor_id and "execution_supervisor_id" in project_fields:
            values["execution_supervisor_id"] = supervisor_id
        elif supervisor_id and "project_manager_id" in project_fields:
            values["project_manager_id"] = supervisor_id
        if "auto_execution_setup" in project_fields:
            values["auto_execution_setup"] = True
        if "date_start" in project_fields:
            values["date_start"] = start_date.isoformat()
        elif "start_date" in project_fields:
            values["start_date"] = start_date.isoformat()

        if "date_deadline" in project_fields:
            values["date_deadline"] = end_date.isoformat()
        elif "expected_completion_date" in project_fields:
            values["expected_completion_date"] = end_date.isoformat()
        elif "date" in project_fields:
            values["date"] = end_date.isoformat()
        
        try:
            project_id = self._execute_kw("project.project", "create", [values])
            logger.info(
                "✓ Created new Odoo project: name=%s, partner_id=%s, project_id=%s, start=%s, deadline=%s",
                project_name,
                partner_id,
                project_id,
                start_date,
                end_date,
            )
            return project_id
        except Exception as e:
            logger.error("✗ Failed to create project in Odoo: %s. Values: %s", str(e), values)
            raise OdooIntegrationError(f"Failed to create project '{project_name}': {str(e)}")

    def _find_supervisor_user_id(self, quotation: Quotation) -> int | None:
        lead = quotation.lead
        if not lead.assigned_to:
            return None
        email = (lead.assigned_to.email or "").strip().lower()
        name = (lead.assigned_to.get_full_name() or lead.assigned_to.username or "").strip()
        if not email and not name:
            return None
        try:
            users_fields = self._get_model_fields("res.users")
            if email:
                by_login = self._execute_kw("res.users", "search", [[["login", "=", email]]], {"limit": 1})
                if by_login:
                    return by_login[0]
                if "email" in users_fields:
                    by_email = self._execute_kw("res.users", "search", [[["email", "=", email]]], {"limit": 1})
                    if by_email:
                        return by_email[0]
            if name:
                by_name = self._execute_kw("res.users", "search", [[["name", "=", name]]], {"limit": 1})
                if by_name:
                    return by_name[0]
        except Exception as e:
            logger.warning("Unable to resolve supervisor user in Odoo: %s", str(e))
        return None

    def find_or_create_default_tasks(self, project_id: int) -> list[int]:
        try:
            project_fields = self._get_model_fields("project.project")
            if "execution_phase_ids" in project_fields:
                project_data = self._execute_kw(
                    "project.project",
                    "read",
                    [[project_id], ["execution_phase_ids"]],
                )
                if project_data and project_data[0].get("execution_phase_ids"):
                    logger.info(
                        "Structured execution phases already exist for project %s; skipping legacy task seeding",
                        project_id,
                    )
                    return []
        except Exception as e:
            logger.debug("Unable to check structured execution setup for project %s: %s", project_id, str(e))

        task_names = [
            "Site Measurement",
            "Design Planning",
            "Material Procurement",
            "Interior Execution",
            "Final Handover",
        ]
        created_or_existing = []
        for task_name in task_names:
            try:
                existing_ids = self._execute_kw(
                    "project.task",
                    "search",
                    [[["name", "=", task_name], ["project_id", "=", project_id]]],
                    {"limit": 1},
                )
                if existing_ids:
                    logger.debug("Task '%s' already exists for project %s (task_id:%s)", task_name, project_id, existing_ids[0])
                    created_or_existing.append(existing_ids[0])
                    continue
            except Exception as e:
                logger.warning("Error searching for task '%s': %s, attempting creation anyway", task_name, str(e))

            try:
                task_id = self._execute_kw(
                    "project.task",
                    "create",
                    [
                        {
                            "name": task_name,
                            "project_id": project_id,
                            "active": True,
                        }
                    ],
                )
                logger.debug("Created task '%s' in project %s (task_id:%s)", task_name, project_id, task_id)
                created_or_existing.append(task_id)
            except Exception as e:
                logger.error("✗ Failed to create task '%s' in project %s: %s", task_name, project_id, str(e))
                # Don't raise here to allow partial task creation; log and continue
                continue
        
        logger.info("✓ Created/found %d default tasks for project %s", len(created_or_existing), project_id)
        return created_or_existing

    @staticmethod
    def _to_float(amount: Decimal) -> float:
        return float(amount.quantize(Decimal("0.01")))

