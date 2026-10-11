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

## Video Link
https://www.loom.com/share/583896f4d60f49cb845f36ca6e19b23b

## Postman Screenshots
<img width="1920" height="1021" alt="Workspaces SS8" src="https://github.com/user-attachments/assets/77b0590a-9e95-45f6-ba00-41cff3da01a3" />
<img width="1919" height="1020" alt="Workspaces SS7" src="https://github.com/user-attachments/assets/0e92e2fd-b202-4ab5-8afe-cc9a0f7dafd2" />
<img width="1918" height="1023" alt="Workspaces SS6" src="https://github.com/user-attachments/assets/b1abbd89-d21b-4223-930a-4f47742e3b3b" />
<img width="1919" height="1023" alt="Workspaces SS5" src="https://github.com/user-attachments/assets/c8a98fb1-c5a1-42f6-b6cb-897dfa8c1e9e" />
<img width="1920" height="1020" alt="Workspaces SS4" src="https://github.com/user-attachments/assets/a693998c-123b-4b2c-92c1-0063b0dc6c9d" />
<img width="1920" height="1023" alt="Workspaces SS3" src="https://github.com/user-attachments/assets/6eef2550-fe44-47bb-97ea-1b9c9e3ce57a" />
<img width="1920" height="1024" alt="Workspaces SS2" src="https://github.com/user-attachments/assets/88bfdbc5-27c5-41aa-8f0a-d7d16525b944" />
<img width="1920" height="1020" alt="Workspaces SS1" src="https://github.com/user-attachments/assets/5407f86d-f9ce-4d8b-8260-f04eea42c1a7" />
<img width="1920" height="1022" alt="Users SS5" src="https://github.com/user-attachments/assets/d5d62ecf-cde9-49f3-a8aa-361659a45db3" />
<img width="1919" height="1021" alt="Users SS4" src="https://github.com/user-attachments/assets/5ad164de-8970-4025-b8ff-c6f21ae5a825" />
<img width="1917" height="1022" alt="Users SS3" src="https://github.com/user-attachments/assets/60e39a4e-1cc6-4dbc-b6e5-443b6dc80e97" />
<img width="1919" height="1019" alt="Users SS2" src="https://github.com/user-attachments/assets/738dc862-f046-4fb4-9345-ad94c4ef476f" />
<img width="1920" height="1017" alt="Users SS1" src="https://github.com/user-attachments/assets/d8edaa49-c032-4b15-9e1c-c15d206cbdd4" />
<img width="1920" height="1024" alt="Tags SS6" src="https://github.com/user-attachments/assets/c944a001-a628-4e25-be24-a68ee7d7bd37" />
<img width="1920" height="1020" alt="Tags SS5" src="https://github.com/user-attachments/assets/299018b0-58ea-48ba-8721-6b3fa5712591" />
<img width="1919" height="1022" alt="Tags SS4" src="https://github.com/user-attachments/assets/869cb2c7-c0a7-4dc4-ac12-6b8f99046d69" />
<img width="1920" height="1019" alt="Tags SS3" src="https://github.com/user-attachments/assets/4f6f27ca-62d3-43a4-8555-9d8fd2248fa5" />
<img width="1920" height="1023" alt="Tags SS2" src="https://github.com/user-attachments/assets/d51e29fa-8d31-4bd3-935e-2a81366921ee" />
<img width="1920" height="1020" alt="Tags SS1" src="https://github.com/user-attachments/assets/967dc1cf-bf3c-4691-a6b8-1014059c997d" />
<img width="1920" height="1023" alt="Documents SS8" src="https://github.com/user-attachments/assets/cab816c2-d460-4947-9658-ae5fa359783c" />
<img width="1919" height="1019" alt="Documents SS7" src="https://github.com/user-attachments/assets/7e6a1d68-f16d-43a9-93a8-9aabfce1364f" />
<img width="1920" height="1018" alt="Documents SS6" src="https://github.com/user-attachments/assets/553898ff-5f0b-4529-bc6e-9e99c21d87d5" />
<img width="1918" height="1021" alt="Documents SS5" src="https://github.com/user-attachments/assets/e42de37d-4cc8-415f-ba12-b7e507b742a4" />
<img width="1920" height="1021" alt="Documents SS4" src="https://github.com/user-attachments/assets/a3523d95-48b4-4000-bb6d-05b926ee99cf" />
<img width="1920" height="1022" alt="Documents SS3" src="https://github.com/user-attachments/assets/fa364f4c-4e8e-40df-a8e7-9f6c7db8180e" />
<img width="1920" height="1020" alt="Documents SS2" src="https://github.com/user-attachments/assets/cd3ba01a-e87f-4fdb-b2bd-044e9b54650c" />
<img width="1919" height="1022" alt="Documents SS1" src="https://github.com/user-attachments/assets/745dd7fa-30e4-44e4-a623-ba922170d965" />
<img width="1919" height="1018" alt="Comments SS3" src="https://github.com/user-attachments/assets/765abfef-e30d-458e-bdaa-de2a479621ec" />
<img width="1920" height="1023" alt="Comments SS2" src="https://github.com/user-attachments/assets/bc942995-f712-484f-92a4-0ccffc8f5ff6" />
<img width="1920" height="1023" alt="Comments SS1" src="https://github.com/user-attachments/assets/8f21eb73-16c1-4770-8c21-65a1534ade0d" />
<img width="1920" height="1021" alt="AuditLogs SS2" src="https://github.com/user-attachments/assets/4f29ecc7-a8f2-4f00-ac5d-20f5ce356ff9" />
<img width="1920" height="1020" alt="AuditLogs SS1" src="https://github.com/user-attachments/assets/afa48721-fda9-4963-8ac8-f78b7595c02e" />

