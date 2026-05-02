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
    <div>
      <h3 className="text-xs font-semibold text-gray-500 mb-2">Notes</h3>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={10000}
        rows={4}
        className="w-full rounded border border-gray-300 px-3 py-2 text-sm resize-y"
        placeholder="Add your notes..."
      />
      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={() => {
            saveNote.mutate(
              { articleId, userNote: note },
              { onSuccess: () => setLastSaved(note) },
            );
          }}
          disabled={saveNote.isPending || note === lastSaved}
          className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saveNote.isPending ? "Saving..." : "Save Note"}
        </button>
        {saveNote.isError && (
          <span className="text-xs text-red-600">Save failed</span>
        )}
        {saveNote.isSuccess && note === lastSaved && (
          <span className="text-xs text-green-600">Saved</span>
        )}
      </div>
    </div>
  );
}
