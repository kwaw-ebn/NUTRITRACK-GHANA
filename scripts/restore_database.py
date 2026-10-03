"""Verify the backup before restoring into a separately authorized empty recovery database."""

import argparse, base64, os, subprocess, tempfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from backup_database import MAGIC, connection_env


def restore_database(path, key, url, allow_restore=False):
    if not allow_restore:
        raise ValueError(
            "Explicit --allow-restore is required for the selected empty recovery database"
        )
    with open(path, "rb") as source:
        header = source.read(20)
        if header[:8] != MAGIC:
            raise ValueError("Unknown backup format")
        source.seek(-16, 2)
        tag = source.read(16)
        length = source.tell() - 36
        decryptor = Cipher(
            algorithms.AES(base64.urlsafe_b64decode(key)), modes.GCM(header[8:], tag)
        ).decryptor()
        decryptor.authenticate_additional_data(MAGIC)
        with tempfile.TemporaryDirectory(prefix="nutri-recovery-") as directory:
            plain = Path(directory) / "verified.dump"
            descriptor = os.open(plain, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                source.seek(20)
                remaining = length
                while remaining:
                    data = source.read(min(65536, remaining))
                    if not data:
                        raise ValueError("Truncated encrypted backup")
                    remaining -= len(data)
                    output.write(decryptor.update(data))
                output.write(decryptor.finalize())
            # An isolated empty target is required; this never runs DROP or --clean.
            result = subprocess.run(
                [
                    "pg_restore",
                    "--no-owner",
                    "--no-privileges",
                    "--exit-on-error",
                    "--dbname",
                    connection_env(url)["PGDATABASE"],
                    str(plain),
                ],
                env=connection_env(url),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode:
                raise RuntimeError(
                    "Restore failed; confirm an empty authorized target and compatible PostgreSQL client"
                )
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--allow-restore", action="store_true")
    args = parser.parse_args()
    restore_database(
        args.input,
        os.environ["BACKUP_ENCRYPTION_KEY"],
        os.environ["RESTORE_DATABASE_URL"],
        args.allow_restore,
    )
    print("PostgreSQL backup authentication and restore completed.")
