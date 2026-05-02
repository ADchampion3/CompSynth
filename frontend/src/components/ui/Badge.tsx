const VARIANT_STYLES: Record<string, string> = {
  default: "bg-gray-100 text-gray-700",
  success: "bg-green-100 text-green-700",
  warning: "bg-yellow-100 text-yellow-700",
  danger: "bg-red-100 text-red-700",
  info: "bg-blue-100 text-blue-700",
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
      className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${VARIANT_STYLES[variant]}`}
    >
      {label}
    </span>
  );
}
