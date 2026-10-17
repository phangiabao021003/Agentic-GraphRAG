import { useState, type FormEvent } from "react";
import { Button } from "../components/common/Button";
import { Input } from "../components/common/Input";
import { AuthLayout } from "../layouts/AuthLayout";

type Props = {
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string) => Promise<void>;
};

export function AuthPage({ onLogin, onRegister }: Props) {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (tab === "login") await onLogin(email, password);
      else await onRegister(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đã xảy ra lỗi");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout>
      <div className="flex mb-6 rounded-lg bg-slate-100 p-1">
        {(["login", "register"] as const).map((t) => (
          <button
            key={t}
            className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === t ? "bg-white shadow text-emerald-700" : "text-slate-500"
            }`}
            onClick={() => { setTab(t); setError(null); }}
          >
            {t === "login" ? "Đăng nhập" : "Đăng ký"}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Input label="Email" type="email" value={email} required
               onChange={(e) => setEmail(e.target.value)} />
        <Input label="Mật khẩu" type="password" value={password} required minLength={8}
               onChange={(e) => setPassword(e.target.value)} />
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <Button type="submit" disabled={busy}>
          {busy ? "Đang xử lý..." : tab === "login" ? "Đăng nhập" : "Tạo tài khoản"}
        </Button>
      </form>
    </AuthLayout>
  );
}
