import { useState } from "react";
import type { ArticleStateResponse } from "../../api/types";
import { useUpdateArticleNote } from "../../api/hooks";

export default function NotePanel({
  articleId,
  state,
}: {
  articleId: string;
  state: ArticleStateResponse | undefined;
}) {
  const [note, setNote] = useState(state?.user_note ?? "");
  const [lastSaved, setLastSaved] = useState(state?.user_note ?? "");
  const saveNote = useUpdateArticleNote();

  const serverNote = state?.user_note ?? "";
  if (serverNote !== lastSaved && !saveNote.isPending) {
    setNote(serverNote);
    setLastSaved(serverNote);
  }

  return (
    <section className="mt-6">
      <h3 className="text-[0.6875rem] font-semibold uppercase tracking-wider text-ink-4 mb-2">
        Notes
      </h3>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={10000}
        rows={4}
        className="w-full rounded-md border border-rule bg-paper px-3 py-2 text-sm text-ink resize-y focus:border-accent focus:outline-none transition-colors placeholder:text-ink-4"
        placeholder="Add your notes…"
      />
      <div className="flex items-center gap-3 mt-2">
        <button
          onClick={() => {
            saveNote.mutate(
              { articleId, userNote: note },
              { onSuccess: () => setLastSaved(note) },
            );
          }}
          disabled={saveNote.isPending || note === lastSaved}
          className="rounded-md bg-accent px-3 py-1 text-xs font-medium text-paper hover:bg-accent-hover disabled:opacity-40 transition-colors"
        >
          {saveNote.isPending ? "Saving…" : "Save Note"}
        </button>
        {saveNote.isError && (
          <span className="text-xs text-err">Save failed</span>
        )}
        {saveNote.isSuccess && note === lastSaved && (
          <span className="text-xs text-ok">Saved</span>
        )}
      </div>
    </section>
  );
}
