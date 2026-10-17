import { Spinner } from "./components/common/Spinner";
import { useAuth } from "./hooks/useAuth";
import { ToastProvider } from "./hooks/useToast";
import { AuthPage } from "./pages/AuthPage";
import { ChatPage } from "./pages/ChatPage";

function App() {
  const { user, login, register, logout, googleError } = useAuth();

  if (user === undefined) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  return (
    <ToastProvider>
      {user === null ? (
        <AuthPage onLogin={login} onRegister={register} googleError={googleError} />
      ) : (
        <ChatPage user={user} onLogout={logout} />
      )}
    </ToastProvider>
  );
}

export default App;
