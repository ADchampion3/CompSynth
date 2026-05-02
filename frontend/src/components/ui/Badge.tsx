const VARIANT_STYLES: Record<string, string> = {
  default: "bg-paper-3 text-ink-2",
  success: "bg-ok-muted text-ok",
  warning: "bg-warn-muted text-warn",
  danger: "bg-err-muted text-err",
  info: "bg-accent-muted text-accent-text",
};

export default function Badge({
  label,
  variant = "default",
}: {
  label: string;
  variant?: "default" | "success" | "warning" | "danger" | "info";
}) {
  return (
    <span
      className={`inline-block rounded-sm px-1.5 py-0.5 text-[0.6875rem] font-medium tracking-wide ${VARIANT_STYLES[variant]}`}
    >
      {label}
    </span>
  );
}
