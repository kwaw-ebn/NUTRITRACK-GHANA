"""Initialize a separate fictional UI integration database, never production."""

import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ["DATABASE_URL"] = "sqlite:////tmp/nutritrack-ui-test.db"
os.environ["SETUP_TOKEN"] = "ui-test-onboarding-token-1234567890"
os.environ["ENVIRONMENT"] = "development"
from app.db import Base, engine
from app.models import *
from app.seed import run

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
run()
print("Fictional UI test database ready at /tmp/nutritrack-ui-test.db")
