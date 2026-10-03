"""Stream a native PostgreSQL dump into authenticated encryption; secrets stay out of arguments."""

import argparse, base64, os, subprocess, sys
from pathlib import Path
from urllib.parse import urlparse, unquote
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"NUTRIBK1"


def connection_env(url):
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1))
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("PostgreSQL DATABASE_URL required")
    env = os.environ.copy()
    env.update(
        PGHOST=parsed.hostname or "",
        PGPORT=str(parsed.port or 5432),
        PGUSER=unquote(parsed.username or ""),
        PGPASSWORD=unquote(parsed.password or ""),
        PGDATABASE=parsed.path.lstrip("/"),
    )
    from urllib.parse import parse_qs

    options = parse_qs(parsed.query)
    env["PGSSLMODE"] = options.get("sslmode", ["require"])[0]
    return env


def encrypt_database(url, key, path):
    nonce = os.urandom(12)
    cipher = Cipher(algorithms.AES(base64.urlsafe_b64decode(key)), modes.GCM(nonce)).encryptor()
    cipher.authenticate_additional_data(MAGIC)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(MAGIC + nonce)
            # pg_dump may report operational errors to stderr, but connection credentials are never arguments.
            proc = subprocess.Popen(
                ["pg_dump", "--format=custom", "--no-owner", "--no-privileges"],
                env=connection_env(url),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                output.write(cipher.update(chunk))
            if proc.wait() != 0:
                raise RuntimeError(
                    "Database backup failed; check connectivity, client version and service logs"
                )
            output.write(cipher.finalize())
            output.write(cipher.tag)
        return path
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    encrypt_database(os.environ["DATABASE_URL"], os.environ["BACKUP_ENCRYPTION_KEY"], args.output)
    print("Encrypted PostgreSQL backup completed.")
