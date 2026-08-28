# Forensic Database Access Inventory in Service Layer

Total Direct Database Operations Found: **2**

| Service | File | Line | Entity / Table | Operation | Cross-domain? | Historical Impact? | Code Snippet |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `exam_service` | `app\services\exam\exam_service.py` | 15 | `Unknown` | `db.query` | No | No | `Repository boundary: Service Layer NEVER calls db.query() or select() directly.` |
| `exam_service` | `app\services\exam\exam_service.py` | 15 | `Unknown` | `select` | No | No | `Repository boundary: Service Layer NEVER calls db.query() or select() directly.` |
