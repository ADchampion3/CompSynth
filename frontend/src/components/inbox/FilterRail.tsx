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
    <div className="space-y-4">
      {/* Search */}
      <div>
        <label className="text-xs font-medium text-gray-500">Search</label>
        <input
          type="text"
          value={query ?? ""}
          onChange={(e) => onFilterChange("query", e.target.value || undefined)}
          placeholder="Search articles..."
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </div>

      {/* Source filter */}
      <div>
        <label className="text-xs font-medium text-gray-500">Source</label>
        <select
          value={source ?? ""}
          onChange={(e) => onFilterChange("source", e.target.value || undefined)}
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
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
        <label className="text-xs font-medium text-gray-500">Tag</label>
        <select
          value={tag ?? ""}
          onChange={(e) => onFilterChange("tag", e.target.value || undefined)}
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
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
        <label className="text-xs font-medium text-gray-500">State</label>
        <div className="mt-1 space-y-1">
          {READ_STATES.map((s) => (
            <label key={s.value} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="readState"
                checked={readState === s.value || (!readState && s.value === "")}
                onChange={() =>
                  onFilterChange("readState", s.value || undefined)
                }
                className="text-xs"
              />
              {s.label}
            </label>
          ))}
        </div>
      </div>

      {/* Liked */}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={liked ?? false}
          onChange={(e) =>
            onFilterChange("liked", e.target.checked ? "true" : undefined)
          }
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
        className="text-xs text-gray-500 hover:text-gray-700"
      >
        Clear filters
      </button>
    </div>
  );
}
