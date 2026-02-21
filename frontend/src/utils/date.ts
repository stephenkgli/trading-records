export function normalizeDateValue(value?: string | null): Date | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const withT = trimmed.includes("T") ? trimmed : trimmed.replace(" ", "T");
  return new Date(withT);
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const d = new Date(value);
  if (isNaN(d.getTime())) return value;
  return d.toLocaleString();
}
