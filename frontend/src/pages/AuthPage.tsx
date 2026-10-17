import { useState, type FormEvent } from "react";
import { Button } from "../components/common/Button";
import { Input } from "../components/common/Input";
import { googleErrorMessage, googleLoginUrl } from "../api/googleLogin";
import { AuthLayout } from "../layouts/AuthLayout";

function GoogleIcon() {
  return (
    <svg viewBox="0 0 48 48" className="w-4 h-4" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/>
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/>
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/>
    </svg>
  );
}

type Props = {
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (email: string, password: string) => Promise<void>;
  googleError?: string | null;
};

export function AuthPage({ onLogin, onRegister, googleError }: Props) {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // The Google error from the redirect shows until the user tries again.
  const [showGoogleError, setShowGoogleError] = useState(true);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setShowGoogleError(false);
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
        {!error && googleError && showGoogleError && (
          <p className="text-sm text-rose-600">{googleErrorMessage(googleError)}</p>
        )}
        <Button type="submit" disabled={busy}>
          {busy ? "Đang xử lý..." : tab === "login" ? "Đăng nhập" : "Tạo tài khoản"}
        </Button>
      </form>
      <div className="my-4 flex items-center gap-3 text-xs text-slate-400">
        <span className="h-px flex-1 bg-slate-200" />
        hoặc
        <span className="h-px flex-1 bg-slate-200" />
      </div>
      <a
        href={googleLoginUrl()}
        className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        <GoogleIcon />
        Đăng nhập bằng Google
      </a>
    </AuthLayout>
  );
}
