# Legacy artefacts

These files configured a one-off Azure VM used to host Doccano during
the phase-2 annotation push. The VM is gone. Nothing under this folder
is referenced by the current 3-script pipeline. Kept as historical
record so the reviewer can see how the team distributed the
annotation work.

- `Caddyfile` — TLS termination for `hp-ner.swedencentral.cloudapp.azure.com`
- `deploy/bootstrap_vm.sh` — first-boot provisioning
- `deploy/deploy_annotation.sh` — push docker-compose stack to VM
- `deploy/setup_https.sh` — wire up Caddy + Let's Encrypt
- `deploy/export_annotations.sh` — pull JSONL exports off the VM
- `deploy/sync_annotations.sh` — rsync helper

For local Doccano (the only supported setup today), see [doccano/README.md](../doccano/README.md).
