from app.config.settings import config

_db_cfg = config["database"]
DATABASE_NAME = _db_cfg["name"]
PAYMENTS_COLLECTION = _db_cfg["collections"]["payments"]
EVIDENCE_COLLECTION = _db_cfg["collections"]["evidence"]

ALLOWED_MIME_TYPES = set(config["storage"]["allowed_mime_types"])
