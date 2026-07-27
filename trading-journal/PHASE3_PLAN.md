#Phase 3 Plan

Phase 2 is complete: signed ingestion, outbox delivery, and idempotency are working.

##Goal

Evolve the SaaS from a single-organization pipeline to a multi-tenant trading platform with clearer operations and separation.

##Core pieces

- Multi-organization model
- Per-organization API keys
- Per-node MT5 registrations
- Role-based access for admin and operator workflows
- Ingestion scoping by organization
- Audit trail for deliveries and failures
- Minimal UI for org and node management

##Recommended implementation order

1. Organization API
   - Create orgs
   - List orgs
   - Activate/deactivate orgs

2. API key management
   - Create API keys for each org
   - Store only hashed keys
   - Rotate keys safely

3. Node registration
   - Register MT5 nodes per org
   - Track last heartbeat and status

4. Ingestion scoping
   - Require org and key context per request
   - Write data only to the matching org

5. Admin UI
   - View orgs
   - View nodes
   - View ingestion events
   - View delivery status

6. Operational hardening
   - Add metrics by org
   - Add health dashboards
   - Improve retry visibility

##Notes

- Keep the current HMAC model for transport security.
- Add per-organization keys on top of it, not instead of it.
- Keep the outbox agent local-first; avoid moving MT5 logic into the cloud.

##Immediate next step

Build the smallest useful slice first:

- `POST /api/v1/orgs`
- `POST /api/v1/orgs/{org_id}/keys`
- `POST /api/v1/nodes`
