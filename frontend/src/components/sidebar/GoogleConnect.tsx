import { useEffect, useState } from "react";
import { apiJson } from "../../api/client";
import { Button } from "../common/Button";

export function GoogleConnect() {
  const [connected, setConnected] = useState<boolean | null>(null);

  useEffect(() => {
    apiJson<{ connected: boolean }>("/auth/google/status")
      .then((s) => setConnected(s.connected))
      .catch(() => setConnected(null));
  }, []);

  const connect = async () => {
    const { url } = await apiJson<{ url: string }>("/auth/google/connect");
    window.location.href = url;
  };

  if (connected) {
    return <p className="text-sm text-emerald-700">✓ Đã kết nối Google Calendar</p>;
  }
  return (
    <Button variant="ghost" className="w-full border border-slate-300" onClick={connect}>
      📅 Kết nối Google Calendar
    </Button>
  );
}
