import { UploadButton } from "./UploadButton";

type Props = {
  docIds: string[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  uploading: boolean;
  onUpload: (file: File) => void;
};

export function DocumentPanel({ docIds, selected, onToggle, uploading, onUpload }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Tài liệu</h3>
      {docIds.length === 0 && <p className="text-xs text-slate-400">Chưa có tài liệu nào.</p>}
      {docIds.map((id) => (
        <label key={id} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
          <input
            type="checkbox"
            checked={selected.has(id)}
            onChange={() => onToggle(id)}
            className="accent-emerald-600"
          />
          <span className="truncate" title={id}>{id}</span>
        </label>
      ))}
      {selected.size > 0 && (
        <p className="text-xs text-emerald-700">Chỉ tìm trong {selected.size} tài liệu đã chọn</p>
      )}
      <UploadButton uploading={uploading} onUpload={onUpload} />
    </div>
  );
}
