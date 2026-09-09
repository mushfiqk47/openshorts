"""Route clusters split out of app.py. Each module exposes exactly one name:
`router` (an APIRouter). Shared state comes from `config`/`state`; shared
request helpers stay in app.py until the deps.py seam (T6b) earns its keep.
"""
