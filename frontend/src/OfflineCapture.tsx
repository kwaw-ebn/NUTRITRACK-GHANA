import { useState, useEffect, useImperativeHandle, forwardRef } from "react";
import { api } from "./api";
import { Field, type Row } from "./components";
type Vault = {
  salt: string;
  entries: { id: string; iv: number[]; cipher: number[] }[];
};
export type OfflineHandle = { queue: (data: Row) => Promise<void> };
const openDB = () =>
  new Promise<IDBDatabase>((resolve, reject) => {
    const req = indexedDB.open("nutritrack-encrypted-capture", 1);
    req.onupgradeneeded = () => req.result.createObjectStore("vaults");
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
async function readVault(id: string): Promise<Vault | null> {
  const db = await openDB();
  try {
    return await new Promise((resolve, reject) => {
      const req = db.transaction("vaults").objectStore("vaults").get(id);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
  } finally {
    db.close();
  }
}
async function writeVault(id: string, value: Vault) {
  const db = await openDB();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction("vaults", "readwrite");
      tx.objectStore("vaults").put(value, id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}
export default forwardRef<
  OfflineHandle,
  { userId: string; organizationId: string; onSynced: () => void }
>(function OfflineCapture({ userId, organizationId, onSynced }, ref) {
  const vaultId = `${userId}:${organizationId}`;
  const [key, setKey] = useState<CryptoKey | null>(null),
    [vault, setVault] = useState<Vault | null>(null),
    [phrase, setPhrase] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [open, setOpen] = useState(false);
  useEffect(() => {
    setKey(null);
    setVault(null);
    readVault(vaultId)
      .then(setVault)
      .catch(() =>
        setError("This browser cannot store encrypted deferred entries."),
      );
  }, [vaultId]);
  useImperativeHandle(
    ref,
    () => ({
      queue: async (data) => {
        if (!key || !vault)
          throw Error(
            "Unlock encrypted deferred capture before recording during a connection interruption.",
          );
        if (vault.entries.length >= 100)
          throw Error(
            "Sync pending entries before adding more; the device limit is 100.",
          );
        const iv = crypto.getRandomValues(new Uint8Array(12));
        const id = crypto.randomUUID();
        const cipher = await crypto.subtle.encrypt(
          { name: "AES-GCM", iv },
          key,
          new TextEncoder().encode(
            JSON.stringify({
              operation_id: id,
              encounter: data,
              user_id: userId,
              organization_id: organizationId,
            }),
          ),
        );
        const next = {
          ...vault,
          entries: [
            ...vault.entries,
            {
              id,
              iv: Array.from(iv),
              cipher: Array.from(new Uint8Array(cipher)),
            },
          ],
        };
        await writeVault(vaultId, next);
        setVault(next);
      },
    }),
    [key, vault, userId, organizationId],
  );
  const unlock = async () => {
    setError("");
    try {
      if (phrase.length < 12)
        throw Error("Choose a device passphrase of at least 12 characters.");
      const value = vault || {
        salt: Array.from(crypto.getRandomValues(new Uint8Array(16))).join(","),
        entries: [],
      };
      const material = await crypto.subtle.importKey(
        "raw",
        new TextEncoder().encode(phrase),
        "PBKDF2",
        false,
        ["deriveKey"],
      );
      const derived = await crypto.subtle.deriveKey(
        {
          name: "PBKDF2",
          salt: new Uint8Array(value.salt.split(",").map(Number)),
          iterations: 250000,
          hash: "SHA-256",
        },
        material,
        { name: "AES-GCM", length: 256 },
        false,
        ["encrypt", "decrypt"],
      );
      if (value.entries.length)
        await crypto.subtle.decrypt(
          { name: "AES-GCM", iv: new Uint8Array(value.entries[0].iv) },
          derived,
          new Uint8Array(value.entries[0].cipher),
        );
      await writeVault(vaultId, value);
      setKey(derived);
      setVault(value);
      setPhrase("");
    } catch {
      setError(
        "Could not unlock. Check your passphrase and browser storage support.",
      );
    }
  };
  const sync = async () => {
    if (!vault || !key) return;
    setBusy(true);
    setError("");
    let remaining = [...vault.entries];
    try {
      for (const item of vault.entries) {
        const decoded = JSON.parse(
          new TextDecoder().decode(
            await crypto.subtle.decrypt(
              { name: "AES-GCM", iv: new Uint8Array(item.iv) },
              key,
              new Uint8Array(item.cipher),
            ),
          ),
        );
        if (
          decoded.user_id !== userId ||
          decoded.organization_id !== organizationId
        )
          throw Error("Entry belongs to another signed-in scope.");
        await api("/api/sync/encounters", {
          method: "POST",
          body: JSON.stringify({
            operation_id: decoded.operation_id,
            encounter: decoded.encounter,
          }),
        });
        remaining = remaining.filter((v) => v.id !== item.id);
        const next = { ...vault, entries: remaining };
        await writeVault(vaultId, next);
        setVault(next);
      }
      onSynced();
    } catch (e) {
      setError(
        `Sync stopped: ${(e as Error).message}. Pending encrypted entries are retained for review; no records are silently overwritten.`,
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel offline-capture">
      <button className="secondary" onClick={() => setOpen(!open)}>
        Encrypted deferred capture · {vault?.entries.length || 0} pending
      </button>
      {open && (
        <>
          <p>
            For an interrupted connection during an already signed-in session.
            Entries are encrypted on this device and can only sync after online
            authentication and server validation.
          </p>
          {!key ? (
            <>
              <Field label="Device vault passphrase">
                <input
                  type="password"
                  value={phrase}
                  onChange={(e) => setPhrase(e.target.value)}
                  autoComplete="off"
                  minLength={12}
                />
              </Field>
              <button className="secondary" onClick={unlock}>
                Unlock / enable capture vault
              </button>
              <p className="muted">
                Use your own trusted device. Keep the passphrase: it is not sent
                to the server and cannot be recovered.
              </p>
            </>
          ) : (
            <div className="admin-tabs">
              <button
                className="primary"
                disabled={busy || !navigator.onLine || !vault?.entries.length}
                onClick={sync}
              >
                {busy ? "Synchronizing…" : "Sync pending entries"}
              </button>
              <button className="secondary" onClick={() => setKey(null)}>
                Lock device vault
              </button>
            </div>
          )}
          {error && <p role="alert">{error}</p>}
        </>
      )}
    </section>
  );
});
