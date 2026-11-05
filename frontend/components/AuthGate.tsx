"use client";

import {
  createContext,
  type FormEvent,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";

type AuthContextValue = {
  session: Session;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuthSession(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuthSession must be used inside AuthGate.");
  return context;
}

export function AccountControls() {
  const { session, signOut } = useAuthSession();
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const label = session.user.email || session.user.phone || "Signed in";

  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase || passwordBusy) return;
    if (password.length < 8) {
      setError("Choose a password with at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }

    setPasswordBusy(true);
    setError("");
    setStatus("");
    try {
      const { error: updateError } = await supabase.auth.updateUser({ password });
      if (updateError) throw updateError;
      setPassword("");
      setConfirmPassword("");
      setStatus("Password saved. You can now sign in with your user ID and password.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save your password.");
    } finally {
      setPasswordBusy(false);
    }
  }

  async function handleSignOut() {
    setError("");
    setStatus("");
    try {
      await signOut();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not sign out.");
    }
  }

  return (
    <div className="auth-account-controls">
      <span className="auth-account-label" title={label}>{label}</span>
      <details className="auth-password-setup">
        <summary>Set password</summary>
        <form onSubmit={(event) => void savePassword(event)}>
          <label className="auth-field">
            New password
            <input
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              disabled={passwordBusy}
            />
          </label>
          <label className="auth-field">
            Confirm password
            <input
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
              disabled={passwordBusy}
            />
          </label>
          <button type="submit" disabled={passwordBusy}>
            {passwordBusy ? "Saving…" : "Save password"}
          </button>
        </form>
      </details>
      <button type="button" onClick={() => void handleSignOut()}>Sign out</button>
      {error && <span className="auth-account-error" role="alert">{error}</span>}
      {status && <span className="auth-account-status" role="status">{status}</span>}
    </div>
  );
}

function SignInScreen({ startupError }: { startupError: string }) {
  const [tab, setTab] = useState<"password" | "code">("password");
  const [method, setMethod] = useState<"email" | "phone">("email");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [noticeAccepted, setNoticeAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(startupError);

  function chooseTab(nextTab: "password" | "code") {
    setTab(nextTab);
    setCodeSent(false);
    setCode("");
    setError("");
  }

  function chooseMethod(nextMethod: "email" | "phone") {
    setMethod(nextMethod);
    setCodeSent(false);
    setCode("");
    setError("");
  }

  async function signInWithPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase || busy || !noticeAccepted) return;
    const value = identifier.trim();
    if (method === "phone" && !/^\+[1-9]\d{7,14}$/.test(value)) {
      setError("Enter your phone number in international format, for example +14155552671.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const { error: signInError } = await supabase.auth.signInWithPassword(
        method === "email"
          ? { email: value.toLowerCase(), password }
          : { phone: value, password },
      );
      if (signInError) throw signInError;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not sign in with that user ID and password.");
    } finally {
      setBusy(false);
    }
  }

  async function requestCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase || busy || !noticeAccepted) return;
    const value = identifier.trim();
    if (method === "phone" && !/^\+[1-9]\d{7,14}$/.test(value)) {
      setError("Enter your phone number in international format, for example +14155552671.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const { error: requestError } = await supabase.auth.signInWithOtp(
        method === "email"
          ? { email: value.toLowerCase(), options: { shouldCreateUser: true } }
          : { phone: value, options: { shouldCreateUser: true } },
      );
      if (requestError) throw requestError;
      setCodeSent(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not send the verification code.");
    } finally {
      setBusy(false);
    }
  }

  async function verifyCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase || busy) return;
    setBusy(true);
    setError("");
    try {
      const value = identifier.trim();
      const { error: verifyError } = await supabase.auth.verifyOtp(
        method === "email"
          ? { email: value.toLowerCase(), token: code.trim(), type: "email" }
          : { phone: value, token: code.trim(), type: "sms" },
      );
      if (verifyError) throw verifyError;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The verification code was not accepted.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-card" aria-labelledby="auth-title">
        <p className="auth-eyebrow">DIVA · STUDENT SIGN IN</p>
        <h1 id="auth-title">Continue learning</h1>
        {!supabase ? (
          <p role="alert">
            Sign-in is not configured yet. The app administrator must add the Supabase
            project URL and publishable key to the frontend environment.
          </p>
        ) : (
          <>
            <p className="auth-intro">
              Sign in with your email or phone and password, or use a one-time verification code.
              Use the same verified user ID each time to access the same study history.
            </p>
            <div className="auth-tabs" role="tablist" aria-label="Sign-in method">
              <button
                type="button"
                role="tab"
                aria-selected={tab === "password"}
                className={tab === "password" ? "selected" : ""}
                onClick={() => chooseTab("password")}
                disabled={busy}
              >
                Password
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={tab === "code"}
                className={tab === "code" ? "selected" : ""}
                onClick={() => chooseTab("code")}
                disabled={busy}
              >
                One-time code
              </button>
            </div>
            <div className="auth-methods" role="group" aria-label="Choose sign-in method">
              <button
                type="button"
                className={method === "email" ? "selected" : ""}
                onClick={() => chooseMethod("email")}
                disabled={busy}
              >
                Email
              </button>
              <button
                type="button"
                className={method === "phone" ? "selected" : ""}
                onClick={() => chooseMethod("phone")}
                disabled={busy}
              >
                Phone
              </button>
            </div>

            <form onSubmit={tab === "password" ? signInWithPassword : codeSent ? verifyCode : requestCode}>
              <label className="auth-field">
                {method === "email" ? "User ID (email address)" : "User ID (phone number)"}
                <input
                  type={method === "email" ? "email" : "tel"}
                  autoComplete={method === "email" ? "email" : "tel"}
                  inputMode={method === "phone" ? "tel" : "email"}
                  placeholder={method === "email" ? "you@example.com" : "+14155552671"}
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  required
                  disabled={(tab === "code" && codeSent) || busy}
                />
              </label>

              {tab === "password" ? (
                <label className="auth-field">
                  Password
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    disabled={busy}
                  />
                </label>
              ) : codeSent ? (
                <>
                  <p className="auth-code-hint">
                    Enter the one-time code sent to {identifier.trim()}.
                  </p>
                  <label className="auth-field">
                    Verification code
                    <input
                      type="text"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      value={code}
                      onChange={(event) => setCode(event.target.value)}
                      required
                      maxLength={12}
                      autoFocus
                    />
                  </label>
                  <button
                    className="auth-secondary"
                    type="button"
                    onClick={() => { setCodeSent(false); setCode(""); setError(""); }}
                    disabled={busy}
                  >
                    Change email or phone
                  </button>
                </>
              ) : null}

              {!(tab === "code" && codeSent) && (
                <label className="auth-consent">
                  <input
                    type="checkbox"
                    checked={noticeAccepted}
                    onChange={(event) => setNoticeAccepted(event.target.checked)}
                  />
                  <span>
                    I understand that my email or phone is used for sign-in; the app stores
                    my study progress, chat messages and uploaded study materials; and my
                    questions are sent to the configured AI service to generate answers.
                    Existing anonymous browser data will not be linked to this account.
                    I will not upload sensitive personal information.
                  </span>
                </label>
              )}
              {error && <p className="auth-error" role="alert">{error}</p>}
              <button
                className="auth-submit"
                type="submit"
                disabled={busy || (tab === "code" && codeSent ? false : !noticeAccepted)}
              >
                {busy
                  ? "Please wait…"
                  : tab === "password"
                    ? "Sign in"
                    : codeSent
                      ? "Verify and sign in"
                      : "Send one-time code"}
              </button>
            </form>
            <p className="auth-footnote">
              {tab === "password"
                ? "New or OTP-only users: use the One-time code tab to sign in, then choose Set password in your account controls."
                : method === "phone"
                  ? "Use international format. SMS delivery requires the administrator to configure an SMS provider."
                  : "Email delivery depends on the administrator’s Supabase email settings."}
            </p>
          </>
        )}
      </section>
    </main>
  );
}

export default function AuthGate({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (process.env.NEXT_PUBLIC_REQUIRE_SIGN_IN !== "true") return;
    if (!supabase) {
      setLoading(false);
      return;
    }

    let active = true;
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (!active) return;
      setSession(nextSession);
      setLoading(false);
    });

    void supabase.auth.getSession()
      .then(({ data, error: sessionError }) => {
        if (!active) return;
        if (sessionError) setError(sessionError.message);
        setSession(data.session);
        setLoading(false);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "Could not check your sign-in.");
        setLoading(false);
      });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  if (process.env.NEXT_PUBLIC_REQUIRE_SIGN_IN !== "true") return children;

  if (loading) {
    return <main className="auth-screen"><p role="status">Checking your sign-in…</p></main>;
  }
  if (!session) return <SignInScreen startupError={error} />;

  const signOut = async () => {
    if (!supabase) throw new Error("Supabase authentication is not configured.");
    const { error: signOutError } = await supabase.auth.signOut();
    if (signOutError) throw signOutError;
  };

  return (
    <AuthContext.Provider value={{ session, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
