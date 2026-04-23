# TeleCRM -> Odoo 19 Integration

## What this does

When a `Quotation` is moved to `APPROVED` in TeleCRM, Django automatically:

1. Authenticates to Odoo via JSON-RPC.
2. Finds or creates the customer in `res.partner`.
3. Optionally creates a `sale.order`.
4. Finds or creates a project in `project.project`.
5. Optionally creates default tasks in `project.task`.

This trigger runs from `crm_api.signals.update_lead_status_on_quotation`.

## Required Odoo setup

1. Enable developer mode in Odoo.
2. Create a dedicated API user for TeleCRM.
3. Grant that user access to:
   - Contacts (`res.partner`)
   - Sales (`sale.order`) if sales sync is enabled
   - Projects (`project.project`, `project.task`)
4. Note these credentials:
   - Odoo URL
   - Database name
   - API username
   - API password

## Environment variables

Configure in `.env`:

- `ODOO_URL`
- `ODOO_DB`
- `ODOO_USERNAME`
- `ODOO_PASSWORD`
- `ODOO_TIMEOUT` (default `20`)
- `ODOO_RETRIES` (default `3`)
- `ODOO_RETRY_DELAY` (default `1.5`)
- `ODOO_AUTO_CREATE_TASKS` (`true`/`false`)
- `ODOO_SYNC_SALE_ORDER` (`true`/`false`)

## Data mapping

- Client -> `res.partner` (`name`, `phone`, `email`, `street`)
- Approved quotation -> optional `sale.order` (`client_order_ref=TELECRM-Q-{id}`)
- Project -> `project.project` (`name`, `partner_id`, dates, description)
- Default tasks -> `project.task`

The project description includes:

- Quotation ID
- Budget
- Location
- Assigned designer
- Expected completion date

## Duplicate handling

- Partner: searched by `phone`, then `email`, then `name`.
- Project: searched by `name + partner_id`.
- Task: searched by `name + project_id`.
- Sale order: searched by `client_order_ref + partner_id`.

## Reliability and production notes

- API calls include retry with incremental backoff.
- Integration events are logged through the `crm_api` logger.
- Trigger runs on `transaction.on_commit()` so only committed approvals are synced.
- For high volume, move the sync call to Celery/Redis worker execution.
