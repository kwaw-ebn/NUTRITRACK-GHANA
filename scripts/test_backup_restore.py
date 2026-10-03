"""Recovery exercise against the disposable PostgreSQL CI service, never a live user database."""

import os, time, tempfile, secrets, base64
from pathlib import Path
import psycopg
from backup_database import encrypt_database
from restore_database import restore_database

url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
with psycopg.connect(url, autocommit=True) as db:
    db.execute("CREATE DATABASE nutritrack_recovery_ci")
# The fixed test target exists only inside the ephemeral workflow container.
from urllib.parse import urlsplit, urlunsplit
parts = urlsplit(url)
target = urlunsplit(parts._replace(path="/nutritrack_recovery_ci"))
started = time.monotonic()
with tempfile.TemporaryDirectory() as directory:
    path = str(Path(directory) / "backup.enc")
    encrypt_database(url, key, path)
    restore_database(path, key, target, True)
    with psycopg.connect(target) as recovered:
        regions = recovered.execute("SELECT count(*) FROM regions").fetchone()[0]
        migration = recovered.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        assert regions == 16 and migration == "0004"
    tampered = Path(directory) / "tampered.enc"
    data = bytearray(Path(path).read_bytes())
    data[30] ^= 1
    tampered.write_bytes(data)
    try:
        restore_database(str(tampered), key, target, True)
    except Exception as e:
        from cryptography.exceptions import InvalidTag

        assert isinstance(e, InvalidTag)
    else:
        raise AssertionError("Tampered backup was accepted")
print(
    f"Ephemeral PostgreSQL recovery verified: 16 regions, migration 0004; elapsed {time.monotonic()-started:.2f}s. This does not verify live backup protection."
)
