#!/usr/bin/env python3
"""Store a text snippet in local Qdrant Edge memory."""

import json
import sys

from memory import store

if len(sys.argv) < 2:
    print("usage: python3 store.py <text>")
    sys.exit(1)

text = " ".join(sys.argv[1:])
point_id = store(text)
print(json.dumps({"stored": True, "id": point_id, "text": text}))
