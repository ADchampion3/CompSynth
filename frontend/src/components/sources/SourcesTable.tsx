import type { SourceResponse } from "../../api/types";
import { safeHref } from "../../api/client";
import { truncate } from "../../lib/format";

export default function SourcesTable({
  sources,
}: {
  sources: SourceResponse[];
}) {
  return (
    <div className="overflow-auto">
      {/* Desktop table */}
      <table className="hidden md:table w-full text-sm">
        <thead>
          <tr className="border-b border-rule text-left">
            <th className="pb-2 pr-4 text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4">
              Name
            </th>
            <th className="pb-2 pr-4 text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4">
              Type
            </th>
            <th className="pb-2 pr-4 text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4">
              URL
            </th>
            <th className="pb-2 text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {sources.map((source) => (
            <tr key={source.source_key} className="group">
              <td className="py-2.5 pr-4 font-medium text-ink">
                {source.name ?? source.source_key}
              </td>
              <td className="py-2.5 pr-4">
                <span className="rounded-sm bg-paper-3 px-1.5 py-0.5 text-[0.6875rem] font-medium text-ink-3">
                  {source.source_type}
                </span>
              </td>
              <td className="py-2.5 pr-4">
                <a
                  href={safeHref(source.url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent-text hover:underline text-xs"
                  title={source.url}
                >
                  {truncate(source.url, 50)}
                </a>
              </td>
              <td className="py-2.5">
                {source.enabled ? (
                  <span className="rounded-sm bg-ok-muted px-1.5 py-0.5 text-[0.6875rem] font-medium text-ok">
                    Active
                  </span>
                ) : (
                  <span className="rounded-sm bg-err-muted px-1.5 py-0.5 text-[0.6875rem] font-medium text-err">
                    Disabled
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile card list */}
      <div className="md:hidden divide-y divide-rule">
        {sources.map((source) => (
          <div key={source.source_key} className="py-3">
            <div className="font-medium text-sm text-ink">
              {source.name ?? source.source_key}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="rounded-sm bg-paper-3 px-1.5 py-0.5 text-[0.6875rem] font-medium text-ink-3">
                {source.source_type}
              </span>
              {source.enabled ? (
                <span className="rounded-sm bg-ok-muted px-1.5 py-0.5 text-[0.6875rem] font-medium text-ok">
                  Active
                </span>
              ) : (
                <span className="rounded-sm bg-err-muted px-1.5 py-0.5 text-[0.6875rem] font-medium text-err">
                  Disabled
                </span>
              )}
            </div>
            <a
              href={safeHref(source.url)}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 block text-xs text-accent-text hover:underline truncate"
            >
              {source.url}
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
