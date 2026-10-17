import { useRef } from "react";
import { Button } from "../common/Button";
import { Spinner } from "../common/Spinner";

type Props = { uploading: boolean; onUpload: (file: File) => void };

export function UploadButton({ uploading, onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file);
          e.target.value = ""; // allow re-selecting the same file
        }}
      />
      <Button variant="ghost" className="w-full border border-slate-300" disabled={uploading}
              onClick={() => inputRef.current?.click()}>
        {uploading ? <span className="flex items-center gap-2 justify-center"><Spinner /> Đang xử lý PDF...</span> : "📄 Tải lên PDF"}
      </Button>
    </>
  );
}
