# CollabDocs - Collaborative Document Platform (API only)

Django + Django REST Framework + PostgreSQL backend: workspaces, role-based members, versioned documents,
threaded comments, tags and an automatic audit log. Postman is the client.

**Demo video:** <PASTE YOUR LOOM / GOOGLE DRIVE LINK HERE>

## Tech stack
Django 6.1, Django REST Framework 3.18, PostgreSQL 16 (Docker), python-dotenv, psycopg2-binary.

## Setup

```bash
# 1. clone and enter the project
git clone <your-repo-url>
cd collabdocs

# 2. virtual environment + dependencies
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt

# 3. environment variables
copy .env.example .env         # Mac/Linux: cp .env.example .env

# 4. start PostgreSQL (Docker)
docker compose up -d

# 5. apply migrations
python manage.py migrate

# 6. run the server
python manage.py runserver
```

API base URL: `http://127.0.0.1:8000/api/`

The database runs on **host port 5434** (set by `POSTGRES_PORT` in `.env`) so it does not clash with a local
PostgreSQL on 5432. Credentials are read from `.env` only; nothing is hard-coded.

## Postman
Import `collabdocs.postman_collection.json` (repo root). Folders: Users, Workspaces, Documents, Comments, Tags,
Audit Logs. Run them top to bottom - test scripts store the generated ids in collection variables.

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/users/` | Create user (email/phone validated) |
| GET | `/api/users/` , `/api/users/{id}/` | List / retrieve users |
| POST | `/api/workspaces/` | Create workspace; owner becomes `admin` member (one transaction) |
| GET | `/api/workspaces/` , `/api/workspaces/{id}/` | List / retrieve (with `member_count`) |
| GET / POST | `/api/workspaces/{id}/members/` | List members / add member (409 if already a member) |
| GET | `/api/workspaces/{id}/summary/` | Aggregation: documents, members, comments |
| POST | `/api/documents/` | Create document + version 1 (+ optional `tag_ids`) atomically |
| GET | `/api/documents/` | List with filters: `workspace`, `status` (csv), `tag`, `search` (title OR content), `updated_from`, `updated_to` |
| GET | `/api/documents/{id}/` | Retrieve document |
| PUT | `/api/documents/{id}/` | Update; creates a new version atomically |
| GET | `/api/documents/{id}/versions/` | Version history |
| GET | `/api/documents/{id}/stats/` | Aggregation: version, comment and contributor counts |
| GET / POST | `/api/documents/{id}/tags/` | List tags / attach tags |
| POST | `/api/comments/` | Create comment or reply (`parent`) |
| GET | `/api/comments/?document={id}` | Threaded comments (top-level + nested replies) |
| POST / GET | `/api/tags/` | Create tag (409 on duplicate) / list tags |
| GET | `/api/audit-logs/` | Filters: `actor`, `date_from`, `date_to`, `model_name`, `action`, `object_id` |

## Design decisions
- **UUID primary keys** on all 8 models; enums use `TextChoices` (`Role`, `Status`, `Action`).
- **Transactions:** workspace + owner membership + audit log, and document + version + tags, each run inside a
  single `transaction.atomic()`. If any step fails (e.g. unknown `tag_id`), nothing is saved.
- **Signal:** `post_save` on `Document` (in `signals.py`, connected in `ApiConfig.ready()`) writes the AuditLog.
  `instance._state.adding` is already `False` inside `post_save`, so a `pre_save` receiver records it first.
- **Versioning:** `version_number = document.versions.count() + 1`, inside the atomic block.
- **Errors:** 400 validation, 404 `DoesNotExist`, 409 `IntegrityError` (duplicate member / duplicate tag).
- **Queries:** `select_related`/`prefetch_related` on nested data, `Q` for OR search, `values_list` for the
  tag filter, `Count(..., distinct=True)` aggregations in summary, stats and workspace queries.
- **Middleware:** `api.middleware.RequestLoggingMiddleware` prints `[REQUEST] METHOD path -> status (ms)`.

## Assumptions
- No authentication (not part of the brief); `User` is a plain model, not Django's auth user.
- No DELETE endpoints are exposed; only the methods listed above.
