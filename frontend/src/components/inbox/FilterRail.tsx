import { useSources } from "../../api/hooks";

const ALL_TAGS = ["技术博客", "比赛信息", "就业招聘", "技术发布", "其他"];
const READ_STATES = [
  { value: "", label: "All" },
  { value: "unread", label: "Unread" },
  { value: "read", label: "Read" },
  { value: "later", label: "Later" },
  { value: "ignored", label: "Ignored" },
];

export default function FilterRail({
  source,
  tag,
  liked,
  query,
  readState,
  onFilterChange,
}: {
  source?: string;
  tag?: string;
  liked?: boolean;
  query?: string;
  readState?: string;
  onFilterChange: (key: string, value: string | undefined) => void;
}) {
  const { data: sources } = useSources();

  return (
    <div className="space-y-5">
      {/* Search */}
      <div>
        <label className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1.5">
          Search
        </label>
        <input
          type="text"
          value={query ?? ""}
          onChange={(e) => onFilterChange("query", e.target.value || undefined)}
          placeholder="Search articles…"
          className="w-full rounded-md border border-rule bg-paper px-2.5 py-1.5 text-sm text-ink placeholder:text-ink-4 focus:border-accent focus:outline-none transition-colors"
        />
      </div>

      {/* Source filter */}
      <div>
        <label className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1.5">
          Source
        </label>
        <select
          value={source ?? ""}
          onChange={(e) => onFilterChange("source", e.target.value || undefined)}
          className="w-full rounded-md border border-rule bg-paper px-2.5 py-1.5 text-sm text-ink focus:border-accent focus:outline-none transition-colors"
        >
          <option value="">All sources</option>
          {sources?.map((s) => (
            <option key={s.source_key} value={s.source_key}>
              {s.name ?? s.source_key}
            </option>
          ))}
        </select>
      </div>

      {/* Tag filter */}
      <div>
        <label className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1.5">
          Tag
        </label>
        <select
          value={tag ?? ""}
          onChange={(e) => onFilterChange("tag", e.target.value || undefined)}
          className="w-full rounded-md border border-rule bg-paper px-2.5 py-1.5 text-sm text-ink focus:border-accent focus:outline-none transition-colors"
        >
          <option value="">All tags</option>
          {ALL_TAGS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {/* Read state */}
      <div>
        <label className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1.5">
          State
        </label>
        <div className="flex flex-wrap gap-1.5">
          {READ_STATES.map((s) => {
            const active = readState === s.value || (!readState && s.value === "");
            return (
              <button
                key={s.value}
                onClick={() => onFilterChange("readState", s.value || undefined)}
                className={`rounded-sm px-2 py-0.5 text-xs font-medium transition-colors ${
                  active
                    ? "bg-accent text-paper"
                    : "bg-paper-3 text-ink-3 hover:bg-paper-2 hover:text-ink"
                }`}
              >
                {s.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Liked */}
      <label className="flex items-center gap-2 text-sm text-ink-2 cursor-pointer">
        <input
          type="checkbox"
          checked={liked ?? false}
          onChange={(e) =>
            onFilterChange("liked", e.target.checked ? "true" : undefined)
          }
          className="accent-accent rounded-sm"
        />
        Liked only
      </label>

      {/* Clear */}
      <button
        onClick={() => {
          onFilterChange("source", undefined);
          onFilterChange("tag", undefined);
          onFilterChange("liked", undefined);
          onFilterChange("query", undefined);
          onFilterChange("readState", undefined);
        }}
        className="text-xs text-ink-4 hover:text-ink transition-colors"
      >
        Clear filters
      </button>
    </div>
  );
}
