# ssm-server

The Simple Secrets Manager API server. A lightweight Flask + flask-restx
REST API that stores secrets in MongoDB and organizes them by **project
and config** with inheritance, secret references, scoped tokens,
workspace RBAC, and a full audit trail. It also serves the React Admin
Console in the unified Docker image.

## Run it

The easiest path is the unified image via the root compose stack:

```bash
git clone https://github.com/bearlike/Simple-Secrets-Manager.git
cd Simple-Secrets-Manager
./scripts/deploy_stack.sh
```

- Admin Console: `http://localhost:8080`
- API through the proxy: `http://localhost:8080/api`
- API direct: `http://localhost:5000/api`

From source (needs a reachable MongoDB):

```bash
uv sync --all-extras
CONNECTION_STRING="mongodb://user:pass@localhost:27017" \
  uv run python -m ssm_server.main
```

## Layout

| Package | Concern |
| --- | --- |
| `api/` | Flask app factory, flask-restx namespaces, serialization, the `{"message": ...}` error envelope |
| `api/resources/` | Thin HTTP resource adapters, one namespace per concern |
| `engines/` | Business logic — one engine per concern, each wrapping a Mongo collection |
| `access/` | Authentication, token scopes, and workspace RBAC |
| `connection.py` / `main.py` | Mongo wiring and the process entry point |

## Documentation

- Deploying and updating: [`docs/SERVER_INSTALLATION.md`](../docs/SERVER_INSTALLATION.md)
- First admin, tokens, RBAC: [`docs/FIRST_TIME_SETUP.md`](../docs/FIRST_TIME_SETUP.md)
- Image tags and runtime reference: [`docs/README_dockerhub.md`](../docs/README_dockerhub.md)
- Contributing and quality gates: [`docs/CONTRIBUTING.md`](../docs/CONTRIBUTING.md)
