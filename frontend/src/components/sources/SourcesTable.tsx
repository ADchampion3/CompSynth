import type { SourceResponse } from "../../api/types";
import { safeHref } from "../../api/client";
import { truncate } from "../../lib/format";
import Badge from "../ui/Badge";

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
          <tr className="border-b border-gray-200 text-left text-xs text-gray-500">
            <th className="pb-2 pr-4">Name</th>
            <th className="pb-2 pr-4">Type</th>
            <th className="pb-2 pr-4">URL</th>
            <th className="pb-2">Enabled</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {sources.map((source) => (
            <tr key={source.source_key}>
              <td className="py-2 pr-4 font-medium">
                {source.name ?? source.source_key}
              </td>
              <td className="py-2 pr-4">
                <Badge label={source.source_type} />
              </td>
              <td className="py-2 pr-4">
                <a
                  href={safeHref(source.url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                  title={source.url}
                >
                  {truncate(source.url, 50)}
                </a>
              </td>
              <td className="py-2">
                {source.enabled ? (
                  <Badge label="Enabled" variant="success" />
                ) : (
                  <Badge label="Disabled" variant="danger" />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile card list */}
      <div className="md:hidden space-y-3">
        {sources.map((source) => (
          <div key={source.source_key} className="rounded border border-gray-200 p-3">
            <div className="font-medium text-sm">
              {source.name ?? source.source_key}
            </div>
            <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
              <Badge label={source.source_type} />
              {source.enabled ? (
                <Badge label="Enabled" variant="success" />
              ) : (
                <Badge label="Disabled" variant="danger" />
              )}
            </div>
            <a
              href={safeHref(source.url)}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 block text-xs text-blue-600 hover:underline truncate"
            >
              {source.url}
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
