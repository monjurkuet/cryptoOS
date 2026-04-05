"""Shared pytest test-environment defaults."""

import os


# Keep test imports resilient when local .env uses non-boolean DEBUG values.
os.environ["DEBUG"] = "false"

# Integration tests require this to build Settings/MongoConfig.
os.environ.setdefault("MONGO__URL", "mongodb://localhost:27017")
