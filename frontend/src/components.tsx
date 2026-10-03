import {
  useState,
  useId,
  cloneElement,
  isValidElement,
  type ReactNode,
  type ReactElement,
} from "react";
import { Search, X, ChevronDown, Leaf, ArrowRight, Inbox } from "lucide-react";
export type Row = Record<string, any>;
export function Brand() {
  return (
    <div className="brand">
      <div className="brand-icon">
        <Leaf size={23} />
      </div>
      <div>
        <strong>
          NutriTrack<span> Ghana</span>
        </strong>
        <small>NUTRITION INTELLIGENCE</small>
      </div>
    </div>
  );
}
export function Empty({
  title = "Your workspace is ready",
  text = "Add records to begin turning nutrition data into action.",
  action,
}: {
  title?: string;
  text?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div>
        <Inbox size={30} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
export function Badge({ children }: { children: ReactNode }) {
  const value = String(children);
  return (
    <span
      className={`badge ${["Urgent", "Immediate", "High", "Overdue", "Returned", "Inactive"].includes(value) ? "red" : ["Approved", "Locked", "Completed", "Active", "Valid"].includes(value) ? "green" : "amber"}`}
    >
      {children}
    </span>
  );
}
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="field">
      <label id={id}>
        <span>{label}</span>
      </label>
      {isValidElement(children)
        ? cloneElement(children as ReactElement<Record<string, unknown>>, {
            "aria-labelledby": id,
          })
        : children}
      {hint && <small>{hint}</small>}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const id = useId();
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <h2 id={id}>{title}</h2>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <X />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
export function Combobox({
  options,
  value,
  onChange,
  placeholder = "Select an option",
  "aria-labelledby": labelledBy,
}: {
  options: Row[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  "aria-labelledby"?: string;
}) {
  const [open, setOpen] = useState(false),
    [query, setQuery] = useState(""),
    [index, setIndex] = useState(0);
  const id = useId();
  const filtered = options.filter((o) =>
    o.name.toLowerCase().includes(query.toLowerCase()),
  );
  const selected = options.find((o) => o.id === value);
  return (
    <div className="combobox">
      <button
        type="button"
        role="combobox"
        aria-labelledby={labelledBy}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => {
          setOpen(!open);
          setQuery("");
          setIndex(0);
        }}
      >
        {selected?.name || placeholder}
        <ChevronDown size={16} />
      </button>
      {open && (
        <div className="combo-menu">
          <div className="search-input">
            <Search size={15} />
            <input
              autoFocus
              aria-label="Search options"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setIndex(0);
              }}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setIndex(Math.min(index + 1, filtered.length - 1));
                }
                if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setIndex(Math.max(index - 1, 0));
                }
                if (e.key === "Escape") setOpen(false);
                if (e.key === "Enter" && filtered[index]) {
                  e.preventDefault();
                  onChange(filtered[index].id);
                  setOpen(false);
                }
              }}
            />
          </div>
          <div id={id} role="listbox">
            {filtered.map((o, i) => (
              <button
                type="button"
                role="option"
                aria-selected={o.id === value}
                className={i === index ? "highlight" : ""}
                key={o.id}
                onClick={() => {
                  onChange(o.id);
                  setOpen(false);
                }}
              >
                {o.name}
              </button>
            ))}
            {!filtered.length && <p>No matching options</p>}
          </div>
        </div>
      )}
    </div>
  );
}
export function Form({
  onSubmit,
  children,
  label = "Save record",
}: {
  onSubmit: (data: Row) => Promise<void>;
  children: ReactNode;
  label?: string;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        try {
          await onSubmit(Object.fromEntries(new FormData(e.currentTarget)));
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      {children}
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      <div className="form-actions">
        <button className="primary" disabled={busy}>
          {busy ? "Saving…" : label}
          <ArrowRight size={17} />
        </button>
      </div>
    </form>
  );
}
export function Select({
  name,
  options,
  required = true,
  value,
  defaultValue,
  onChange,
  "aria-labelledby": labelledBy,
}: {
  name: string;
  options: Row[];
  required?: boolean;
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  "aria-labelledby"?: string;
}) {
  return (
    <select
      aria-labelledby={labelledBy}
      name={name}
      required={required}
      value={value}
      defaultValue={defaultValue}
      onChange={(e) => onChange?.(e.target.value)}
    >
      <option value="">Select…</option>
      {options.map((o) => (
        <option value={o.id ?? o.code ?? o.name} key={o.id ?? o.code ?? o.name}>
          {o.name ?? o.title}
        </option>
      ))}
    </select>
  );
}
export function Table({
  rows,
  columns,
  onSelect,
}: {
  rows: Row[];
  columns: { key: string; label: string; render?: (row: Row) => ReactNode }[];
  onSelect?: (row: Row) => void;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.id ?? r.facility_id}
              onClick={() => onSelect?.(r)}
              className={onSelect ? "clickable" : ""}
            >
              {columns.map((c) => (
                <td key={c.key}>
                  {c.render ? c.render(r) : (r[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
