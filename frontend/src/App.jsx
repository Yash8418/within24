import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, RequireAuth, useAuth } from "./auth.jsx";
import AuthPage from "./pages/AuthPage.jsx";

function Home() {
  const { user, signOut } = useAuth();
  return (
    <main className="page">
      <p>Signed in as {user.email}.</p>
      <button className="button" type="button" onClick={signOut}>
        Sign out
      </button>
    </main>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<AuthPage mode="login" />} />
        <Route path="/register" element={<AuthPage mode="register" />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Home />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
