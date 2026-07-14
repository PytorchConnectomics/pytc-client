# demo.seg.bio Health Check Runbook

Run this when updating the public demo build or service stack.

## What this checks

`scripts/check_demo_health.py` verifies:

- Root app returns HTTP 200
- Canonical workflow endpoint `GET /api/workflows/current` returns HTTP 200
- Compatibility endpoint `GET /api/api/workflows/current` returns HTTP 200
- Files root `GET /api/files?parent=root` returns HTTP 200 and JSON list
- Project suggestions `GET /api/files/project-suggestions` returns HTTP 200 and JSON list
- App log event ingest `POST /api/app/log-event`
- Neuroglancer viewer health when either:
  - a viewer URL is derivable from the current workflow, or
  - `--neuroglancer-url` is passed

## Deployment components currently involved

- `nginx` fronts `https://demo.seg.bio`
- Frontend static bundle is deployed to `/var/www/demo.seg.bio`
- API process runs on port `4342` (service: `pytc-demo@pytc-client-demo2.service`)
- PyTC worker (behind the API) is configured separately and must be reachable by API
- Neuroglancer backend is on port `4244`
- Public tunnel service is `cloudflared-demo-seg-bio.service`

## Run the health check

```bash
cd /home/weidf/deploy/pytc-client-demo2
python3 scripts/check_demo_health.py
```

Optional viewer override:

```bash
python3 scripts/check_demo_health.py --neuroglancer-url https://demo.seg.bio/neuroglancer/v/<token>/
```

The script exits with a non-zero status if any required check fails.
