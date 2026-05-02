import { useSources, useTags } from "../../api/hooks";

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
  onClear,
}: {
  source?: string;
  tag?: string;
  liked?: boolean;
  query?: string;
  readState?: string;
  onFilterChange: (key: string, value: string | undefined) => void;
  onClear: () => void;
}) {
  const { data: sources } = useSources();
  const { data: tagsData } = useTags();
  const tags = tagsData?.tags ?? [];

  return (
    <div className="space-y-5">
      {/* Search */}
      <div>
        <label htmlFor="filter-search" className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1.5">
          Search
        </label>
        <input
          id="filter-search"
          type="text"
          value={query ?? ""}
          onChange={(e) => onFilterChange("query", e.target.value || undefined)}
          placeholder="Search articles…"
          className="w-full rounded-md border border-rule bg-paper px-2.5 py-2 text-sm text-ink placeholder:text-ink-4 focus:border-accent focus:outline-none transition-colors"
        />
      </div>

      {/* Source filter */}
      <div>
        <label htmlFor="filter-source" className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1.5">
          Source
        </label>
        <select
          id="filter-source"
          value={source ?? ""}
          onChange={(e) => onFilterChange("source", e.target.value || undefined)}
          className="w-full rounded-md border border-rule bg-paper px-2.5 py-2 text-sm text-ink focus:border-accent focus:outline-none transition-colors"
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
        <label htmlFor="filter-tag" className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1.5">
          Tag
        </label>
        <select
          id="filter-tag"
          value={tag ?? ""}
          onChange={(e) => onFilterChange("tag", e.target.value || undefined)}
          className="w-full rounded-md border border-rule bg-paper px-2.5 py-2 text-sm text-ink focus:border-accent focus:outline-none transition-colors"
        >
          <option value="">All tags</option>
          {tags.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {/* Read state */}
      <div>
        <span className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 block mb-1.5">
          State
        </span>
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Read state filter">
          {READ_STATES.map((s) => {
            const active = readState === s.value || (!readState && s.value === "");
            return (
              <button
                key={s.value}
                role="radio"
                aria-checked={active}
                onClick={() => onFilterChange("readState", s.value || undefined)}
                className={`rounded-md px-3 py-2 text-xs font-medium transition-colors min-h-[36px] ${
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
      <label className="flex items-center gap-2 text-sm text-ink-2 cursor-pointer py-1">
        <input
          id="filter-liked"
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
        onClick={onClear}
        className="text-xs text-ink-4 hover:text-ink transition-colors py-2"
      >
        Clear filters
      </button>
    </div>
  );
}
