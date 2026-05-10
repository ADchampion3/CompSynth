import { useState, useCallback, useEffect } from "react";
import {
  useSettings,
  useSettingsSchema,
  useUpdateSettings,
} from "../../api/hooks";
import { ApiError } from "../../api/client";
import type { SettingsSchemaField } from "../../api/types";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import ErrorCard from "../ui/ErrorCard";
import LoadingSkeleton from "../ui/LoadingSkeleton";

const GROUP_ORDER = ["llm", "crawler", "storage", "output"] as const;
const GROUP_LABELS: Record<string, string> = {
  llm: "LLM Configuration",
  crawler: "Crawler",
  storage: "Storage",
  output: "Output",
};
const MASKED_SENTINEL = "***configured***";
const RESTART_KEY = "compsynth-restart-pending";

function getApiBaseUrl(): string {
  return localStorage.getItem("compsynth-api-base") || "";
}

function setApiBaseUrl(url: string) {
  if (url) {
    localStorage.setItem("compsynth-api-base", url);
  } else {
    localStorage.removeItem("compsynth-api-base");
  }
}

export default function SettingsPage() {
  useDocumentTitle("Settings");

  const { data: settings, isLoading, error } = useSettings();
  const { data: schema } = useSettingsSchema();
  const updateMutation = useUpdateSettings();

  const [edited, setEdited] = useState<Record<string, string>>({});
  const [restartPending, setRestartPending] = useState(
    () => localStorage.getItem(RESTART_KEY) === "true",
  );
  const [apiBaseUrl, setApiBaseUrlState] = useState(getApiBaseUrl);
  const [apiBaseUrlEdited, setApiBaseUrlEdited] = useState(getApiBaseUrl);
  const [savedGroups, setSavedGroups] = useState<Set<string>>(new Set());

  const handleFieldChange = useCallback((key: string, value: string) => {
    setEdited((prev) => ({ ...prev, [key]: value }));
    setSavedGroups(new Set());
  }, []);

  const handleSaveGroup = useCallback(
    (group: string) => {
      if (!schema) return;
      const fieldsInGroup = Object.entries(schema.fields)
        .filter(([, f]) => f.group === group)
        .map(([k]) => k);
      const changes: Record<string, string> = {};
      for (const key of fieldsInGroup) {
        if (key in edited) {
          changes[key] = edited[key];
        }
      }
      if (Object.keys(changes).length === 0) return;
      updateMutation.mutate(changes, {
        onSuccess: () => {
          setEdited((prev) => {
            const next = { ...prev };
            for (const key of fieldsInGroup) delete next[key];
            return next;
          });
          setSavedGroups((prev) => new Set(prev).add(group));
          setRestartPending(true);
          localStorage.setItem(RESTART_KEY, "true");
          setTimeout(() => setSavedGroups(new Set()), 2000);
        },
      });
    },
    [schema, edited, updateMutation],
  );

  const handleSaveApiBase = useCallback(() => {
    setApiBaseUrl(apiBaseUrlEdited);
    setApiBaseUrlState(apiBaseUrlEdited);
    setRestartPending(true);
    localStorage.setItem(RESTART_KEY, "true");
  }, [apiBaseUrlEdited]);

  const dismissRestart = useCallback(() => {
    setRestartPending(false);
    localStorage.removeItem(RESTART_KEY);
  }, []);

  if (isLoading) {
    return (
      <div className="p-6 md:p-8 max-w-3xl">
        <LoadingSkeleton lines={8} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 md:p-8 max-w-3xl">
        <h1 className="font-display text-2xl font-bold text-ink mb-6">Settings</h1>
        <ErrorCard error={error} />
        <ConnectionSection
          apiBaseUrl={apiBaseUrlEdited}
          onChange={setApiBaseUrlEdited}
          onSave={handleSaveApiBase}
          saved={savedGroups.has("connection")}
        />
      </div>
    );
  }

  const groups = schema
    ? GROUP_ORDER.filter((g) =>
        Object.values(schema.fields).some((f) => f.group === g),
      )
    : [];

  return (
    <div className="p-6 md:p-8 max-w-3xl space-y-8">
      <h1 className="font-display text-2xl font-bold text-ink">Settings</h1>

      {restartPending && <RestartBanner onDismiss={dismissRestart} />}

      <ConnectionSection
        apiBaseUrl={apiBaseUrlEdited}
        onChange={setApiBaseUrlEdited}
        onSave={handleSaveApiBase}
        saved={savedGroups.has("connection")}
      />

      {groups.map((group) => {
        const allFields = schema
          ? Object.entries(schema.fields).filter(([, f]) => f.group === group)
          : [];
        const hasEdits = allFields.some(([k]) => k in edited);
        return (
          <SettingsGroupCard
            key={group}
            group={group}
            title={GROUP_LABELS[group] || group}
            fields={allFields}
            values={settings || {}}
            edited={edited}
            onChange={handleFieldChange}
            onSave={() => handleSaveGroup(group)}
            hasEdits={hasEdits}
            saving={updateMutation.isPending}
            saved={savedGroups.has(group)}
            error={updateMutation.error}
          />
        );
      })}
    </div>
  );
}

function RestartBanner({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-md bg-warn-muted border border-rule px-4 py-3 text-sm text-warn">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
      <span className="flex-1">Some changes require a server restart to take effect.</span>
      <button
        onClick={onDismiss}
        className="text-warn hover:text-ink font-medium text-xs uppercase tracking-wide transition-colors"
      >
        Dismiss
      </button>
    </div>
  );
}

function ConnectionSection({
  apiBaseUrl,
  onChange,
  onSave,
  saved,
}: {
  apiBaseUrl: string;
  onChange: (v: string) => void;
  onSave: () => void;
  saved: boolean;
}) {
  return (
    <div className="rounded-md border border-rule bg-paper-2/50 p-5 space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="font-display text-lg font-bold text-ink">Connection</h2>
        <span className="text-[0.625rem] font-semibold uppercase tracking-wider text-ink-4 bg-paper-3 px-2 py-0.5 rounded">
          Frontend &middot; localStorage
        </span>
      </div>
      <p className="text-sm text-ink-3">
        The backend URL the frontend connects to. Stored locally, not synced via API.
      </p>
      <div>
        <label className="block text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 mb-1">
          API Base URL
        </label>
        <input
          type="text"
          value={apiBaseUrl}
          onChange={(e) => onChange(e.target.value)}
          placeholder="http://localhost:8000"
          className="w-full rounded-md border border-rule bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-1 focus:ring-accent"
        />
      </div>
      <div className="flex justify-end">
        <button
          onClick={onSave}
          className="px-4 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wide bg-accent text-white hover:bg-accent/90 transition-colors"
        >
          {saved ? "Saved" : "Save"}
        </button>
      </div>
    </div>
  );
}

function SettingsGroupCard({
  group,
  title,
  fields,
  values,
  edited,
  onChange,
  onSave,
  hasEdits,
  saving,
  saved,
  error,
}: {
  group: string;
  title: string;
  fields: [string, SettingsSchemaField][];
  values: Record<string, string>;
  edited: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onSave: () => void;
  hasEdits: boolean;
  saving: boolean;
  saved: boolean;
  error: unknown;
}) {
  const isLLM = group === "llm";
  const providerKey = "llm_provider";
  const selectedProvider = (edited[providerKey] ?? values[providerKey] ?? "openai") as string;

  const providerDefaults = isLLM
    ? (fields.find(([k]) => k === "model")?.[1].provider_defaults ?? {})
    : {};

  const visibleFields = isLLM
    ? fields.filter(([k, f]) => {
        if (k === providerKey) return false;
        if (!f.provider) return true;
        return f.provider === selectedProvider;
      })
    : fields;

  const switchProvider = (newProvider: string) => {
    const prevProvider = selectedProvider;
    onChange(providerKey, newProvider);
    const currentModel = edited["model"] ?? values["model"] ?? "";
    if (providerDefaults[prevProvider] && currentModel === providerDefaults[prevProvider]) {
      onChange("model", providerDefaults[newProvider]);
    }
  };

  return (
    <div className="rounded-md border border-rule bg-paper p-5 space-y-4">
      <h2 className="font-display text-lg font-bold text-ink">{title}</h2>

      {isLLM && (
        <div className="flex rounded-md border border-rule overflow-hidden">
          <button
            type="button"
            onClick={() => switchProvider("openai")}
            className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
              selectedProvider === "openai"
                ? "bg-accent text-white"
                : "bg-paper-2 text-ink-3 hover:text-ink"
            }`}
          >
            OpenAI Compatible
          </button>
          <button
            type="button"
            onClick={() => switchProvider("anthropic")}
            className={`flex-1 px-4 py-2 text-sm font-medium transition-colors border-l border-rule ${
              selectedProvider === "anthropic"
                ? "bg-accent text-white"
                : "bg-paper-2 text-ink-3 hover:text-ink"
            }`}
          >
            Anthropic
          </button>
        </div>
      )}

      <div className="space-y-4">
        {visibleFields.map(([key, field]) => (
          <SettingsField
            key={selectedProvider + "-" + key}
            fieldKey={key}
            field={field}
            currentValue={values[key] ?? ""}
            editedValue={edited[key]}
            onChange={onChange}
          />
        ))}
      </div>

      {error && (
        <div className="rounded-md bg-err-muted p-3 text-sm text-err">
          {error instanceof ApiError
            ? error.problem
            : error instanceof Error
              ? error.message
              : "Failed to save settings"}
        </div>
      )}

      <div className="flex justify-end items-center gap-2">
        {saved && <span className="text-xs text-ok" aria-live="polite">Saved</span>}
        <button
          onClick={onSave}
          disabled={!hasEdits || saving}
          className={`px-4 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wide transition-colors ${
            saved
              ? "bg-ok text-paper"
              : hasEdits
                ? "bg-accent text-white hover:bg-accent/90"
                : "bg-paper-3 text-ink-3 cursor-not-allowed"
          }`}
        >
          {saved ? "Saved" : saving ? "Saving..." : hasEdits ? "Save changes" : "No changes"}
        </button>
      </div>
    </div>
  );
}

function SettingsField({
  fieldKey,
  field,
  currentValue,
  editedValue,
  onChange,
}: {
  fieldKey: string;
  field: SettingsSchemaField;
  currentValue: string;
  editedValue: string | undefined;
  onChange: (key: string, value: string) => void;
}) {
  const isSensitive = field.sensitive;
  const isConfigured = isSensitive && currentValue === MASKED_SENTINEL;
  const displayValue = editedValue ?? (isConfigured ? "" : currentValue);

  return (
    <div>
      <label className="flex items-center gap-2 mb-1">
        <span className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4">
          {field.label}
        </span>
        {isConfigured && (
          <span className="flex items-center gap-1 text-[0.625rem] font-medium text-ok">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-ok" />
            configured
          </span>
        )}
      </label>
      {field.description && (
        <p className="text-xs text-ink-3 mb-1.5">{field.description}</p>
      )}
      {field.type === "select" && field.options ? (
        <select
          value={displayValue || String(field.default)}
          onChange={(e) => onChange(fieldKey, e.target.value)}
          className="w-full rounded-md border border-rule bg-paper px-3 py-2 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-accent"
        >
          {field.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt === "openai" ? "OpenAI Compatible" : opt === "anthropic" ? "Anthropic" : opt}
            </option>
          ))}
        </select>
      ) : (
        <input
          type={isSensitive ? "password" : "text"}
          value={displayValue}
          onChange={(e) => onChange(fieldKey, e.target.value)}
          placeholder={isConfigured ? "Enter new value to update" : String(field.default)}
          className="w-full rounded-md border border-rule bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-1 focus:ring-accent"
        />
      )}
      {field.constraints && (
        <p className="text-[0.625rem] text-ink-4 mt-1">
          Range: {field.constraints.minimum} – {field.constraints.maximum}
        </p>
      )}
    </div>
  );
}
