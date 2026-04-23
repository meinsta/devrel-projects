#!/usr/bin/env python3
"""Search local Qdrant Edge memory."""

import json
import sys

from memory import search

if len(sys.argv) < 2:
    print("usage: python3 search.py <query>")
    sys.exit(1)

query = " ".join(sys.argv[1:])
results = search(query)
print(json.dumps(results, indent=2))
