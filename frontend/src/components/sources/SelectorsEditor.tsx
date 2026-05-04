import { Fragment, useState } from "react";
import type { SourceResponse } from "../../api/types";
import { useUpdateSource, useUpdateLlmSelectors, useReextractSelectors } from "../../api/hooks";

const SELECTOR_FIELDS = [
  { key: "item_container", label: "Container" },
  { key: "url", label: "URL" },
  { key: "title", label: "Title" },
  { key: "summary", label: "Summary" },
  { key: "time", label: "Time" },
] as const;

type SelectorGroup = Record<string, string>;

function toGroups(selectors: Record<string, string>[] | null | undefined): SelectorGroup[] {
  if (!selectors || selectors.length === 0) return [{}];
  return selectors.map((g) => ({ ...g }));
}

function SelectorGroupView({ group }: { group: Record<string, string> }) {
  return (
    <div className="rounded border border-rule bg-paper-2 px-2.5 py-1.5">
      <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-xs">
        {SELECTOR_FIELDS.map(({ key, label }) =>
          group[key] ? (
            <Fragment key={key}>
              <span className="text-ink-4 font-medium">{label}</span>
              <span className="font-mono text-[0.6875rem] text-ink-2">{group[key]}</span>
            </Fragment>
          ) : null,
        )}
      </div>
    </div>
  );
}

function SelectorGroupEdit({
  group,
  index,
  total,
  onUpdate,
  onRemove,
}: {
  group: SelectorGroup;
  index: number;
  total: number;
  onUpdate: (key: string, value: string) => void;
  onRemove: () => void;
}) {
  return (
    <div className="rounded border border-rule bg-paper-2 px-2.5 py-2 space-y-1.5">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4">
          Group {index + 1}
        </span>
        {total > 1 && (
          <button
            onClick={onRemove}
            className="text-[0.6875rem] text-ink-4 hover:text-err transition-colors"
          >
            Remove
          </button>
        )}
      </div>
      {SELECTOR_FIELDS.map(({ key, label }) => (
        <div key={key} className="grid grid-cols-[5rem_1fr] gap-1 items-center">
          <label className="text-[0.6875rem] font-medium text-ink-4">{label}</label>
          <input
            type="text"
            value={group[key] ?? ""}
            onChange={(e) => onUpdate(key, e.target.value)}
            placeholder={key === "item_container" ? "article.post-item" : ""}
            className="w-full rounded border border-rule bg-paper px-2 py-1 text-xs font-mono text-ink placeholder:text-ink-4/50 focus:border-accent focus:outline-none"
          />
        </div>
      ))}
    </div>
  );
}

function SelectorSection({
  label,
  tag,
  tagColor,
  selectors,
  isEditing,
  onEdit,
  onSave,
  onCancel,
  groups,
  updateField,
  addGroup,
  removeGroup,
  isPending,
  reextractPending,
  onReextract,
}: {
  label: string;
  tag: string;
  tagColor: string;
  selectors: Record<string, string>[] | null;
  isEditing: boolean;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  groups: SelectorGroup[];
  updateField: (gi: number, key: string, value: string) => void;
  addGroup: () => void;
  removeGroup: (gi: number) => void;
  isPending: boolean;
  reextractPending?: boolean;
  onReextract?: () => void;
}) {
  const hasSelectors = selectors && selectors.length > 0;

  return (
    <div className="rounded border border-rule bg-paper-2 px-3 py-2">
      <div className="flex items-center gap-2 mb-2">
        <span className={`rounded-sm px-1.5 py-0.5 text-[0.625rem] font-semibold uppercase tracking-wider ${tagColor}`}>
          {tag}
        </span>
        <span className="text-[0.6875rem] font-medium text-ink-3">{label}</span>
      </div>

      {!isEditing ? (
        <div className="space-y-2">
          {!hasSelectors ? (
            <p className="text-xs text-ink-4 italic">None</p>
          ) : (
            <div className="space-y-1.5">
              {selectors!.map((group, gi) => (
                <SelectorGroupView key={gi} group={group} />
              ))}
            </div>
          )}
          <div className="flex items-center gap-3">
            <button
              onClick={onEdit}
              className="text-xs text-ink-4 hover:text-ink transition-colors"
            >
              Edit selectors
            </button>
            {onReextract && (
              <button
                onClick={onReextract}
                disabled={reextractPending}
                className="text-xs text-ink-4 hover:text-accent transition-colors disabled:text-ink-4/50 disabled:cursor-wait"
              >
                {reextractPending ? "Extracting…" : "Re-extract"}
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map((group, gi) => (
            <SelectorGroupEdit
              key={gi}
              group={group}
              index={gi}
              total={groups.length}
              onUpdate={(key, value) => updateField(gi, key, value)}
              onRemove={() => removeGroup(gi)}
            />
          ))}
          <button
            onClick={addGroup}
            className="text-xs text-ink-4 hover:text-ink transition-colors"
          >
            + Add group
          </button>
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={onSave}
              disabled={isPending}
              className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-paper hover:bg-accent-hover disabled:opacity-50 transition-colors"
            >
              {isPending ? "Saving..." : "Save"}
            </button>
            <button
              onClick={onCancel}
              className="rounded-md border border-rule px-3 py-1.5 text-xs font-medium text-ink-3 hover:bg-paper-2 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SelectorsEditor({ source }: { source: SourceResponse }) {
  const updateSource = useUpdateSource();
  const updateLlm = useUpdateLlmSelectors();
  const reextract = useReextractSelectors();
  const canReextract = source.source_type === "web" || source.source_type === "javascript";

  const [userEditing, setUserEditing] = useState(false);
  const [llmEditing, setLlmEditing] = useState(false);
  const [userGroups, setUserGroups] = useState<SelectorGroup[]>(() => toGroups(source.selectors));
  const [llmGroups, setLlmGroups] = useState<SelectorGroup[]>(() => toGroups(source.llm_selectors));

  const updateUserField = (gi: number, key: string, value: string) => {
    setUserGroups((prev) => prev.map((g, i) => (i === gi ? { ...g, [key]: value } : g)));
  };
  const updateLlmField = (gi: number, key: string, value: string) => {
    setLlmGroups((prev) => prev.map((g, i) => (i === gi ? { ...g, [key]: value } : g)));
  };

  const saveUser = () => {
    const cleaned = userGroups.filter((g) => Object.keys(g).length > 0);
    updateSource.mutate(
      { key: source.source_key, selectors: cleaned.length > 0 ? cleaned : null },
      { onSuccess: () => setUserEditing(false) },
    );
  };
  const cancelUser = () => {
    setUserGroups(toGroups(source.selectors));
    setUserEditing(false);
  };

  const saveLlm = () => {
    const cleaned = llmGroups.filter((g) => Object.keys(g).length > 0);
    if (cleaned.length === 0) return;
    updateLlm.mutate(
      { key: source.source_key, selectors: cleaned },
      { onSuccess: () => setLlmEditing(false) },
    );
  };
  const cancelLlm = () => {
    setLlmGroups(toGroups(source.llm_selectors));
    setLlmEditing(false);
  };

  return (
    <div className="space-y-3">
      <SelectorSection
        label="User Defined"
        tag="User"
        tagColor="bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
        selectors={source.selectors}
        isEditing={userEditing}
        onEdit={() => setUserEditing(true)}
        onSave={saveUser}
        onCancel={cancelUser}
        groups={userGroups}
        updateField={updateUserField}
        addGroup={() => setUserGroups((prev) => [...prev, {}])}
        removeGroup={(gi) => setUserGroups((prev) => prev.filter((_, i) => i !== gi))}
        isPending={updateSource.isPending}
      />
      <SelectorSection
        label="LLM Auto-detected"
        tag="LLM"
        tagColor="bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300"
        selectors={source.llm_selectors}
        isEditing={llmEditing}
        onEdit={() => setLlmEditing(true)}
        onSave={saveLlm}
        onCancel={cancelLlm}
        groups={llmGroups}
        updateField={updateLlmField}
        addGroup={() => setLlmGroups((prev) => [...prev, {}])}
        removeGroup={(gi) => setLlmGroups((prev) => prev.filter((_, i) => i !== gi))}
        isPending={updateLlm.isPending}
        reextractPending={reextract.isPending}
        onReextract={canReextract ? () => reextract.mutate(source.source_key) : undefined}
      />
    </div>
  );
}
