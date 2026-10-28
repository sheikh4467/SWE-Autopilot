"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useAuthSession } from "@/components/auth-session";
import { BrandMark } from "@/components/brand-mark";
import { Button } from "@/components/ui/button";

type AuthMode = "login" | "signup";
type AuthStep = "form" | "verify" | "success";
type VerificationProvider = "email" | "google" | "github";
type AuthSuccessKind = "verified" | "signed-in";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const VERIFICATION_RESEND_COOLDOWN_SECONDS = 60;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getStringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function normalizeEmailForDisplay(email: string): string {
  return email.trim().toLowerCase();
}

function getProviderLabel(provider: VerificationProvider): string {
  if (provider === "google") return "Google";
  if (provider === "github") return "GitHub";
  return "email";
}

function getOAuthProvider(value: string | null): VerificationProvider | null {
  return value === "google" || value === "github" ? value : null;
}

function getAuthErrorMessage(result: unknown, fallback: string): string {
  if (!isRecord(result)) return fallback;

  const detail = result.detail;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (Array.isArray(detail)) {
    const firstMessage = detail.find((item) => isRecord(item) && typeof item.msg === "string");
    if (isRecord(firstMessage) && typeof firstMessage.msg === "string" && firstMessage.msg.trim()) {
      return firstMessage.msg.trim();
    }
  }
  if (isRecord(detail)) {
    const nestedMessage = getStringValue(detail.message) ?? getStringValue(detail.detail);
    if (nestedMessage) return nestedMessage;
  }

  return getStringValue(result.message) ?? fallback;
}

function getVerificationDetails(result: unknown, fallbackEmail: string): { email: string } | null {
  if (!isRecord(result)) return null;

  const detail = isRecord(result.detail) ? result.detail : null;
  const verificationRequired = result.verification_required === true || detail?.verification_required === true;
  if (!verificationRequired) return null;

  const email = getStringValue(result.email) ?? (detail ? getStringValue(detail.email) : null) ?? fallbackEmail;
  return { email: normalizeEmailForDisplay(email) };
}

function getRetryAfterSeconds(response: Response): number | null {
  const value = response.headers.get("Retry-After");
  if (!value) return null;

  const seconds = Number.parseInt(value, 10);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

type IconProps = {
  className?: string;
};

function ArrowUpRight({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M4 12 12 4M5 4h7v7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronDown({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="m3.5 6 4.5 4 4.5-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Check({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="m3.25 8.25 3.1 3.1 6.4-6.7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Spark({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 1.75 9.1 6.9 14.25 8l-5.15 1.1L8 14.25 6.9 9.1 1.75 8 6.9 6.9 8 1.75Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  );
}

function Shield({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 1.75 13 3.7v3.65c0 3.15-2.05 5.75-5 6.9-2.95-1.15-5-3.75-5-6.9V3.7l5-1.95Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
      <path d="m5.6 8 1.55 1.55L10.55 6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GitBranch({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="4" cy="4" r="1.75" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="12" cy="4" r="1.75" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="12" cy="12" r="1.75" stroke="currentColor" strokeWidth="1.2" />
      <path d="M5.75 4h3.1A3.15 3.15 0 0 1 12 7.15V10.25M4 5.75v3.1A3.15 3.15 0 0 0 7.15 12H10.25" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function Play({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="m6 4.25 5.25 3.75L6 11.75V4.25Z" fill="currentColor" />
    </svg>
  );
}

function X({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function Eye({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M1.75 8s2.05-3.25 6.25-3.25S14.25 8 14.25 8 12.2 11.25 8 11.25 1.75 8 1.75 8Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
      <circle cx="8" cy="8" r="1.65" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function EyeOff({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2.25 2.25 13.75 13.75M6.85 5.05A3.7 3.7 0 0 1 8 4.75c4.2 0 6.25 3.25 6.25 3.25a11.4 11.4 0 0 1-2.1 2.25M4.1 4.85C2.55 5.7 1.75 8 1.75 8s2.05 3.25 6.25 3.25c.55 0 1.05-.07 1.5-.18" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GoogleIcon({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M21.35 12.27c0-.71-.06-1.4-.18-2.06H12v3.9h5.23a4.47 4.47 0 0 1-1.94 2.93v2.43h3.14c1.84-1.7 2.92-4.21 2.92-7.2Z" />
      <path fill="#34A853" d="M12 21.8c2.63 0 4.84-.87 6.45-2.33l-3.14-2.43c-.87.58-1.98.92-3.31.92-2.55 0-4.71-1.72-5.49-4.03H3.27v2.5A9.75 9.75 0 0 0 12 21.8Z" />
      <path fill="#FBBC05" d="M6.51 13.93A5.86 5.86 0 0 1 6.2 12c0-.67.11-1.32.31-1.93v-2.5H3.27A9.74 9.74 0 0 0 2.25 12c0 1.57.38 3.05 1.02 4.43l3.24-2.5Z" />
      <path fill="#EA4335" d="M12 6.04c1.43 0 2.71.49 3.72 1.45l2.79-2.79C16.84 3.14 14.63 2.2 12 2.2a9.75 9.75 0 0 0-8.73 5.37l3.24 2.5c.78-2.31 2.94-4.03 5.49-4.03Z" />
    </svg>
  );
}

function GitHubIcon({ className = "size-4" }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2.25a9.75 9.75 0 0 0-3.08 19c.49.09.67-.21.67-.47v-1.67c-2.73.6-3.31-1.16-3.31-1.16-.45-1.14-1.1-1.44-1.1-1.44-.89-.61.07-.6.07-.6.98.07 1.5 1 1.5 1 .88 1.5 2.31 1.07 2.87.82.09-.64.35-1.07.63-1.32-2.18-.25-4.47-1.09-4.47-4.86 0-1.07.38-1.94 1-2.62-.1-.25-.43-1.25.1-2.59 0 0 .82-.26 2.69 1a9.33 9.33 0 0 1 4.9 0c1.87-1.26 2.69-1 2.69-1 .53 1.34.2 2.34.1 2.59.62.68 1 1.55 1 2.62 0 3.78-2.3 4.61-4.49 4.85.36.31.68.91.68 1.84v2.73c0 .26.18.56.68.47A9.75 9.75 0 0 0 12 2.25Z" />
    </svg>
  );
}

const orbitNodes = [
  { label: "Requirements", short: "REQ", position: "node-requirements", color: "cyan" },
  { label: "Architect", short: "ARC", position: "node-architect", color: "violet" },
  { label: "Testing", short: "QA", position: "node-testing", color: "lime" },
  { label: "Security", short: "SEC", position: "node-security", color: "orange" },
  { label: "Deployment", short: "DEP", position: "node-deployment", color: "blue" },
];

const workflow = [
  {
    number: "01",
    eyebrow: "Understand",
    title: "Turn intent into a system map.",
    text: "Compile natural-language requirements into structured artifacts, acceptance criteria, IDs, and traceable relationships.",
    accent: "cyan",
  },
  {
    number: "02",
    eyebrow: "Build",
    title: "Let agents move with guardrails.",
    text: "Coordinate architecture, code, and data agents through a deterministic runtime with explicit tool permissions.",
    accent: "violet",
  },
  {
    number: "03",
    eyebrow: "Verify",
    title: "Trust evidence, not promises.",
    text: "Build, execute, test, red-team, recover, and gate releases using real runtime evidence and human approval when it matters.",
    accent: "lime",
  },
];

const platformPillars = [
  { icon: GitBranch, title: "Traceable by design", text: "Requirement → story → architecture → code → test → evidence." },
  { icon: Spark, title: "Closed-loop execution", text: "Detect → diagnose → repair → rebuild → retest, with bounded recovery." },
  { icon: Shield, title: "Security stays in the loop", text: "Defensive red-team checks and regression memory protect every change." },
];

export default function Home() {
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [authStep, setAuthStep] = useState<AuthStep>("form");
  const [authSuccessKind, setAuthSuccessKind] = useState<AuthSuccessKind>("signed-in");
  const [showPassword, setShowPassword] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authNotice, setAuthNotice] = useState<string | null>(null);
  const [verificationEmail, setVerificationEmail] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [verificationProvider, setVerificationProvider] = useState<VerificationProvider>("email");
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resendLoading, setResendLoading] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const { user: currentUser, refresh: refreshSession, logout: logoutSession } = useAuthSession();

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 },
    );

    document.querySelectorAll("[data-reveal]").forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const updateProgress = () => {
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      setScrollProgress(maxScroll > 0 ? (window.scrollY / maxScroll) * 100 : 0);
    };

    updateProgress();
    window.addEventListener("scroll", updateProgress, { passive: true });
    return () => window.removeEventListener("scroll", updateProgress);
  }, []);

  useEffect(() => {
    if (resendCooldown <= 0) return;

    const timeout = window.setTimeout(() => {
      setResendCooldown((remaining) => Math.max(0, remaining - 1));
    }, 1000);

    return () => window.clearTimeout(timeout);
  }, [resendCooldown]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const authResult = params.get("auth");

    if (authResult === "verify") {
      const provider = getOAuthProvider(params.get("provider"));
      const email = params.get("email") ? normalizeEmailForDisplay(params.get("email") as string) : "";

      window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.hash}`);

      if (!provider || !email) {
        setAuthNotice("We could not start email verification. Please try signing in again.");
        return;
      }

      setAuthMode("login");
      setAuthStep("verify");
      setAuthSuccessKind("verified");
      setAuthOpen(true);
      setAuthError(null);
      setAuthLoading(false);
      setResendLoading(false);
      setVerificationEmail(email);
      setVerificationCode("");
      setVerificationProvider(provider);
      setResendCooldown(VERIFICATION_RESEND_COOLDOWN_SECONDS);
      return;
    }

    if (authResult !== "success") {
      const requestedMode = params.get("openAuth");
      if (requestedMode === "login" || requestedMode === "signup") {
        setAuthMode(requestedMode);
        setAuthOpen(true);
        setAuthError(null);
        window.history.replaceState({}, document.title, window.location.pathname);
      }
      return;
    }

    const provider = params.get("provider");
    const providerLabel = provider === "github" ? "GitHub" : provider === "google" ? "Google" : "OAuth";

    refreshSession()
      .then((user) => {
        if (!user) throw new Error("Could not load the authenticated user.");
        setAuthNotice(`Signed in with ${providerLabel} as ${user.name}.`);
        window.location.replace("/workspace");
      })
      .catch(() => {
        setAuthNotice(`${providerLabel} authentication completed. Start the API to load your workspace session.`);
      })
      .finally(() => {
        window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.hash}`);
      });
  }, [refreshSession]);

  const openAuth = (mode: AuthMode) => {
    setAuthMode(mode);
    setAuthStep("form");
    setAuthSuccessKind("signed-in");
    setAuthOpen(true);
    setAuthError(null);
    setAuthLoading(false);
    setResendLoading(false);
    setVerificationEmail("");
    setVerificationCode("");
    setVerificationProvider("email");
    setResendCooldown(0);
    setMenuOpen(false);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const endpoint = authMode === "login" ? "/auth/login" : "/auth/signup";
    const payload = authMode === "login"
      ? {
          email: String(formData.get("email") ?? ""),
          password: String(formData.get("password") ?? ""),
        }
      : {
          name: String(formData.get("name") ?? ""),
          email: String(formData.get("email") ?? ""),
          password: String(formData.get("password") ?? ""),
        };

    setAuthLoading(true);
    setAuthError(null);

    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      const result = (await response.json().catch(() => null)) as unknown;

      if (!response.ok) {
        if (authMode === "login") {
          const verification = getVerificationDetails(result, payload.email);
          if (response.status === 403 && verification) {
            setAuthStep("verify");
            setAuthSuccessKind("verified");
            setVerificationEmail(verification.email);
            setVerificationCode("");
            setVerificationProvider("email");
            setResendLoading(false);
            setResendCooldown(getRetryAfterSeconds(response) ?? 0);
            return;
          }
        }

        throw new Error(getAuthErrorMessage(result, "Authentication failed. Please try again."));
      }

      if (authMode === "signup") {
        if (!isRecord(result) || result.verification_required !== true) {
          throw new Error("We could not start email verification. Please try again.");
        }

        const email = normalizeEmailForDisplay(getStringValue(result.email) ?? payload.email);
        setAuthStep("verify");
        setAuthSuccessKind("verified");
        setVerificationEmail(email);
        setVerificationCode("");
        setVerificationProvider("email");
        setResendLoading(false);
        setResendCooldown(VERIFICATION_RESEND_COOLDOWN_SECONDS);
        return;
      }

      const sessionUser = await refreshSession();
      if (!sessionUser) throw new Error("Signed in, but we could not load your session. Please try again.");
      window.location.assign("/workspace");
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Authentication failed. Please try again.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleVerify = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!verificationEmail) {
      setAuthError("Enter your email again to request a verification code.");
      return;
    }
    if (verificationCode.length !== 6) {
      setAuthError("Enter the 6-digit verification code from your email.");
      return;
    }

    setAuthLoading(true);
    setAuthError(null);

    try {
      const response = await fetch(`${API_URL}/auth/verify-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: verificationEmail, code: verificationCode }),
      });
      const result = (await response.json().catch(() => null)) as unknown;

      if (!response.ok) {
        throw new Error(getAuthErrorMessage(result, "That verification code is invalid or expired."));
      }

      const sessionUser = await refreshSession();
      if (!sessionUser) throw new Error("Your email was verified, but we could not load your session. Please try again.");
      window.location.assign("/workspace");
      setVerificationCode("");
      setResendCooldown(0);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "That verification code is invalid or expired.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleResendVerification = async () => {
    if (!verificationEmail || resendLoading || resendCooldown > 0) return;

    setResendLoading(true);
    setAuthError(null);

    try {
      const response = await fetch(`${API_URL}/auth/resend-verification`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: verificationEmail }),
      });
      const result = (await response.json().catch(() => null)) as unknown;

      if (!response.ok) {
        const retryAfter = getRetryAfterSeconds(response);
        if (retryAfter) setResendCooldown(retryAfter);
        throw new Error(getAuthErrorMessage(result, "Unable to resend the verification email. Please try again."));
      }

      setResendCooldown(VERIFICATION_RESEND_COOLDOWN_SECONDS);
      setAuthNotice(getAuthErrorMessage(result, "If an unverified account exists, a new verification email has been sent."));
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Unable to resend the verification email. Please try again.");
    } finally {
      setResendLoading(false);
    }
  };

  const handleOAuth = (provider: "google" | "github") => {
    setAuthError(null);
    window.location.assign(`${API_URL}/auth/${provider}/login`);
  };

  const handleLogout = async () => {
    await logoutSession();
    setAuthOpen(false);
    setAuthStep("form");
    setVerificationEmail("");
    setVerificationCode("");
    setResendCooldown(0);
    setAuthNotice("You have been signed out.");
  };

  const verificationProviderLabel = getProviderLabel(verificationProvider);
  const authTitle = authStep === "verify"
    ? "Verify your email."
    : authStep === "success"
      ? authSuccessKind === "verified" ? "Account verified." : "Signed in."
      : authMode === "login" ? "Welcome back." : "Start your workspace.";
  const authDescription = authStep === "verify"
    ? verificationProvider === "email"
      ? "Enter the 6-digit code we sent to your email."
      : `Enter the 6-digit code sent to continue with ${verificationProviderLabel}.`
    : authStep === "success"
      ? authSuccessKind === "verified"
        ? "Your email is verified and your account is ready for the control room."
        : "Your SWE Autopilot session is ready."
      : authMode === "login" ? "Continue orchestrating your software lifecycle." : "Build your first traceable software workflow.";

  return (
    <main className="min-h-screen overflow-x-clip bg-ink text-white selection:bg-cyan selection:text-ink">
      <div className="scroll-progress" style={{ width: `${scrollProgress}%` }} />
      <div className="ambient ambient-one" aria-hidden="true" />
      <div className="ambient ambient-two" aria-hidden="true" />
      <div className="page-grid" aria-hidden="true" />
      <div className="noise-layer" aria-hidden="true" />

      {authNotice && (
        <div className="auth-notice" role="status">
          <span className="auth-notice-icon"><Check className="size-3.5" /></span>
          <span>{authNotice}</span>
          <button aria-label="Dismiss authentication notice" onClick={() => setAuthNotice(null)}><X className="size-3.5" /></button>
        </div>
      )}

      <header className="sticky top-0 z-40 border-b border-white/[0.07] bg-ink/70 backdrop-blur-xl">
        <div className="mx-auto flex h-[74px] max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
          <a href="#top" aria-label="SWE Autopilot home" onClick={() => setMenuOpen(false)}>
            <BrandMark />
          </a>

          <nav className="hidden items-center gap-8 text-[13px] text-slate-400 lg:flex" aria-label="Primary navigation">
            <Link className="nav-link" href="/platform">Platform</Link>
            <Link className="nav-link" href="/workflow">Workflow</Link>
            <Link className="nav-link" href="/security">Security</Link>
            <Link className="nav-link" href="/about">About</Link>
          </nav>

          <div className="hidden items-center gap-3 sm:flex">
            {currentUser ? (
              <>
                <span className="max-w-[150px] truncate text-sm text-slate-400">Hi, {currentUser.name}</span>
                <button className="text-sm font-medium text-slate-300 transition hover:text-white" onClick={handleLogout}>Sign out</button>
              </>
            ) : (
              <>
                <button className="text-sm font-medium text-slate-300 transition hover:text-white" onClick={() => openAuth("login")}>
                  Sign in
                </button>
                <Button className="px-4 py-2.5" onClick={() => openAuth("signup")}>
                  Get started <ArrowUpRight />
                </Button>
              </>
            )}
          </div>

          <button
            className="grid size-10 place-items-center rounded-full border border-white/10 bg-white/[0.04] text-slate-300 sm:hidden"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <X /> : <span className="flex flex-col gap-1"><span className="h-px w-4 bg-current" /><span className="h-px w-4 bg-current" /></span>}
          </button>
        </div>

        {menuOpen && (
          <div className="border-t border-white/[0.07] px-5 py-5 sm:hidden">
            <nav className="flex flex-col gap-4 text-sm text-slate-300" aria-label="Mobile navigation">
              <Link href="/platform" onClick={() => setMenuOpen(false)}>Platform</Link>
              <Link href="/workflow" onClick={() => setMenuOpen(false)}>Workflow</Link>
              <Link href="/security" onClick={() => setMenuOpen(false)}>Security</Link>
              <Link href="/about" onClick={() => setMenuOpen(false)}>About</Link>
              <div className="mt-2 flex gap-3 border-t border-white/[0.08] pt-4">
                {currentUser ? (
                  <Button variant="outline" className="flex-1" onClick={handleLogout}>Sign out</Button>
                ) : (
                  <>
                    <Button variant="outline" className="flex-1" onClick={() => openAuth("login")}>Sign in</Button>
                    <Button className="flex-1" onClick={() => openAuth("signup")}>Get started</Button>
                  </>
                )}
              </div>
            </nav>
          </div>
        )}
      </header>

      <section id="top" className="relative mx-auto grid min-h-[calc(100svh-74px)] max-w-7xl items-center gap-10 px-5 pb-16 pt-14 sm:px-8 lg:grid-cols-[0.93fr_1.07fr] lg:px-10 lg:pb-20 lg:pt-16">
        <div className="relative z-10 max-w-2xl">
          <div className="eyebrow-pill mb-7 animate-fade-up">
            <span className="live-dot" />
            <span>Autonomous SDLC / control plane</span>
          </div>
          <h1 className="max-w-3xl animate-fade-up text-[clamp(3.4rem,7.5vw,7.3rem)] font-semibold leading-[0.91] tracking-[-0.075em] [animation-delay:100ms]">
            Build with a
            <span className="gradient-text block">system view.</span>
          </h1>
          <p className="mt-8 max-w-xl animate-fade-up text-base leading-7 text-slate-400 [animation-delay:200ms] sm:text-lg sm:leading-8">
            SWE Autopilot turns changing requirements into traceable, tested, and release-ready software — with specialized agents, real execution evidence, and a runtime that keeps every decision accountable.
          </p>
          <div className="mt-9 flex flex-col gap-3 animate-fade-up [animation-delay:300ms] sm:flex-row">
            <Button className="group" onClick={() => openAuth("signup")}>
              Enter the control room <ArrowUpRight className="transition duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </Button>
            <Link className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-5 py-3 text-sm font-semibold text-white transition duration-300 hover:-translate-y-0.5 hover:border-white/25 hover:bg-white/[0.07]" href="/workflow">
              <span className="grid size-5 place-items-center rounded-full bg-white/10"><Play className="size-3" /></span>
              See how it works
            </Link>
          </div>
          <div className="mt-10 flex flex-wrap gap-x-6 gap-y-3 text-xs text-slate-500 animate-fade-up [animation-delay:400ms]">
            <span className="inline-flex items-center gap-2"><Check className="text-cyan" /> Human approval gates</span>
            <span className="inline-flex items-center gap-2"><Check className="text-cyan" /> Evidence before release</span>
          </div>
        </div>

        <div className="hero-stage mx-auto h-[min(82vw,650px)] w-full max-w-[650px] lg:h-[650px]" aria-label="Animated overview of the SWE Autopilot agent system">
          <div className="hero-stage-glow" />
          <div className="hero-orbit hero-orbit-outer" />
          <div className="hero-orbit hero-orbit-middle" />
          <div className="hero-orbit hero-orbit-inner" />
          <div className="hero-axis hero-axis-one" />
          <div className="hero-axis hero-axis-two" />
          <div className="hero-core">
            <div className="hero-core-ring" />
            <div className="hero-core-inner">
              <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-cyan/70">SWE</span>
              <strong className="mt-1 text-2xl font-semibold tracking-[-0.08em] text-white">AUTO</strong>
              <span className="mt-1 text-[9px] uppercase tracking-[0.24em] text-slate-500">agent runtime</span>
            </div>
          </div>
          {orbitNodes.map((node) => (
            <div key={node.label} className={`orbit-node ${node.position} orbit-node-${node.color}`}>
              <span className="orbit-node-dot" />
              <span className="orbit-node-copy"><strong>{node.short}</strong><small>{node.label}</small></span>
            </div>
          ))}
          <div className="floating-card floating-card-top">
            <span className="status-check"><Check /></span>
            <span><small>Verification status</small><strong>Evidence captured</strong></span>
            <span className="font-mono text-[10px] text-lime">98.4%</span>
          </div>
          <div className="floating-card floating-card-bottom">
            <span className="signal-bars"><i /><i /><i /><i /></span>
            <span><small>Workflow state</small><strong>Release gate ready</strong></span>
            <span className="live-dot live-dot-small" />
          </div>
          <div className="stage-caption"><span>REQ-001</span><span className="stage-caption-line" /><span>DEPLOY</span></div>
        </div>

        <Link className="absolute bottom-5 left-5 hidden items-center gap-3 text-[10px] uppercase tracking-[0.24em] text-slate-500 transition hover:text-white lg:flex" href="/platform">
          <span className="scroll-line" /> Scroll to explore <ChevronDown />
        </Link>
      </section>

      <section id="platform" className="relative mx-auto max-w-7xl scroll-mt-24 px-5 pb-28 sm:px-8 lg:px-10 lg:pb-40">
        <div className="section-rule" />
        <div className="grid gap-10 py-16 lg:grid-cols-[0.8fr_1.2fr] lg:gap-20 lg:py-24" data-reveal>
          <div>
            <span className="section-kicker">01 / The idea</span>
            <h2 className="mt-5 max-w-md text-4xl font-semibold leading-[0.98] tracking-[-0.06em] sm:text-5xl">
              Software gets complex. Your control plane shouldn&apos;t.
            </h2>
          </div>
          <div className="max-w-2xl">
            <p className="text-lg leading-8 text-slate-300 sm:text-xl sm:leading-9">
              We are building the layer between a human idea and production software. SWE Autopilot coordinates specialized agents across the SDLC so requirements, architecture, code, tests, security, and deployment stay connected as the system evolves.
            </p>
            <div className="mt-10 grid gap-4 sm:grid-cols-3">
              {platformPillars.map((pillar) => {
                const Icon = pillar.icon;
                return (
                  <article key={pillar.title} className="glass-card group p-5">
                    <span className="mb-7 grid size-9 place-items-center rounded-xl border border-cyan/20 bg-cyan/[0.08] text-cyan transition duration-300 group-hover:rotate-6 group-hover:bg-cyan/[0.14]"><Icon /></span>
                    <h3 className="text-sm font-semibold tracking-[-0.02em] text-white">{pillar.title}</h3>
                    <p className="mt-2 text-xs leading-5 text-slate-500">{pillar.text}</p>
                  </article>
                );
              })}
            </div>
          </div>
        </div>

        <div className="metric-strip" data-reveal>
          <div><strong>01</strong><span>Agent runtime</span></div>
          <div><strong>07</strong><span>SDLC surfaces</span></div>
          <div><strong>03</strong><span>Auto-repair attempts</span></div>
          <div><strong>∞</strong><span>Traceable decisions</span></div>
        </div>
      </section>

      <section id="workflow" className="relative mx-auto max-w-7xl scroll-mt-24 px-5 pb-28 sm:px-8 lg:px-10 lg:pb-40">
        <div className="section-rule" />
        <div className="flex flex-col justify-between gap-8 py-16 sm:flex-row sm:items-end lg:py-24" data-reveal>
          <div>
            <span className="section-kicker">02 / The workflow</span>
            <h2 className="mt-5 max-w-2xl text-4xl font-semibold leading-[0.98] tracking-[-0.06em] sm:text-6xl">
              From first thought to verified release.
            </h2>
          </div>
          <p className="max-w-sm text-sm leading-6 text-slate-500 sm:text-right">
            A visual, stateful workflow that keeps the human in control while agents do the heavy lifting.
          </p>
        </div>

        <div className="workflow-rail">
          {workflow.map((step, index) => (
            <article key={step.number} className={`workflow-card workflow-card-${step.accent}`} data-reveal>
              <div className="flex items-start justify-between">
                <span className="workflow-number">{step.number}</span>
                <span className="workflow-arrow"><ArrowUpRight /></span>
              </div>
              <div className="mt-20 sm:mt-28">
                <span className="font-mono text-[10px] uppercase tracking-[0.24em] text-slate-500">{step.eyebrow}</span>
                <h3 className="mt-4 max-w-xs text-2xl font-semibold leading-[1.02] tracking-[-0.05em] text-white sm:text-3xl">{step.title}</h3>
                <p className="mt-5 max-w-sm text-sm leading-6 text-slate-400">{step.text}</p>
              </div>
              <div className="workflow-graphic" aria-hidden="true">
                {index === 0 && <><span className="graphic-node graphic-node-a" /><span className="graphic-node graphic-node-b" /><span className="graphic-line graphic-line-a" /><span className="graphic-line graphic-line-b" /><span className="graphic-center"><Spark /></span></>}
                {index === 1 && <><span className="graphic-ring graphic-ring-a" /><span className="graphic-ring graphic-ring-b" /><span className="graphic-ring graphic-ring-c" /><span className="graphic-center graphic-center-orbit"><span /></span></>}
                {index === 2 && <><span className="graphic-check"><Check /></span><span className="graphic-scan graphic-scan-a" /><span className="graphic-scan graphic-scan-b" /><span className="graphic-scan graphic-scan-c" /></>}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="security" className="relative mx-auto max-w-7xl scroll-mt-24 px-5 pb-28 sm:px-8 lg:px-10 lg:pb-40">
        <div className="section-rule" />
        <div className="grid items-center gap-12 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:gap-24 lg:py-24" data-reveal>
          <div className="security-console-wrap">
            <div className="security-console-glow" />
            <div className="security-console">
              <div className="console-topbar">
                <div className="flex items-center gap-2"><span className="console-dot console-dot-red" /><span className="console-dot console-dot-yellow" /><span className="console-dot console-dot-green" /></div>
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-600">agent-runtime / live</span>
                <span className="live-dot live-dot-small" />
              </div>
              <div className="console-body">
                <div className="console-command"><span className="text-cyan">$</span> autopilot verify --project pulse-api</div>
                <div className="console-divider" />
                <div className="console-row"><span className="console-label"><span className="console-check">✓</span> Build integrity</span><span className="text-lime">PASSED</span><span className="console-time">1.8s</span></div>
                <div className="console-row"><span className="console-label"><span className="console-check">✓</span> Contract tests</span><span className="text-lime">PASSED</span><span className="console-time">4.2s</span></div>
                <div className="console-row"><span className="console-label"><span className="console-check">✓</span> Security probes</span><span className="text-lime">PASSED</span><span className="console-time">6.7s</span></div>
                <div className="console-row console-row-warn"><span className="console-label"><span className="console-warn">↻</span> Regression replay</span><span className="text-orange-300">RUNNING</span><span className="console-time">—</span></div>
                <div className="console-divider" />
                <div className="console-footer"><span>4 checks complete</span><strong>release gate <span className="text-lime">ready</span></strong></div>
              </div>
            </div>
            <div className="console-chip console-chip-left"><span className="text-violet">AST</span> dependency graph synced</div>
            <div className="console-chip console-chip-right"><Shield className="text-cyan" /> Attack Memory armed</div>
          </div>

          <div>
            <span className="section-kicker">03 / Evidence first</span>
            <h2 className="mt-5 max-w-xl text-4xl font-semibold leading-[0.98] tracking-[-0.06em] sm:text-5xl">
              Your release should have receipts.
            </h2>
            <p className="mt-7 max-w-lg text-base leading-7 text-slate-400 sm:text-lg sm:leading-8">
              Generated code is only a hypothesis. SWE Autopilot builds the app, runs the checks, captures the evidence, and keeps the full engineering history attached to the decision.
            </p>
            <div className="mt-9 space-y-4">
              {[
                ["Bounded recovery", "No runaway loops. Repair attempts stop, escalate, or roll back."],
                ["Security memory", "Confirmed findings become regression checks for the next change."],
                ["Human release gates", "Architecture, security, and deployment decisions stay reviewable."],
              ].map(([title, text]) => (
                <div key={title} className="flex gap-4 border-t border-white/[0.08] pt-4">
                  <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-cyan/[0.1] text-cyan"><Check className="size-3.5" /></span>
                  <div><h3 className="text-sm font-semibold text-white">{title}</h3><p className="mt-1 text-sm leading-6 text-slate-500">{text}</p></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="about" className="relative mx-auto max-w-7xl scroll-mt-24 px-5 pb-20 sm:px-8 lg:px-10 lg:pb-28">
        <div className="section-rule" />
        <div className="grid gap-10 py-16 lg:grid-cols-[0.72fr_1.28fr] lg:items-end lg:py-24" data-reveal>
          <div>
            <span className="section-kicker">04 / Why us</span>
            <h2 className="mt-5 max-w-sm text-4xl font-semibold leading-[0.98] tracking-[-0.06em] sm:text-5xl">Not another coding assistant.</h2>
          </div>
          <div>
            <p className="max-w-3xl text-2xl font-medium leading-[1.2] tracking-[-0.04em] text-slate-200 sm:text-4xl">
              We are engineering an autonomous workflow — not wrapping an LLM in a chat box.
            </p>
            <div className="mt-8 flex flex-wrap gap-2">
              {['Requirements', 'Architecture', 'Code', 'Testing', 'Security', 'Deployment'].map((label, index) => (
                <span key={label} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-slate-400 transition hover:border-cyan/40 hover:text-cyan">{String(index + 1).padStart(2, '0')} / {label}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="relative mx-auto max-w-7xl px-5 pb-20 sm:px-8 lg:px-10 lg:pb-28">
        <div className="cta-panel" data-reveal>
          <div className="cta-orbit cta-orbit-one" aria-hidden="true" />
          <div className="cta-orbit cta-orbit-two" aria-hidden="true" />
          <div className="relative z-10 max-w-2xl">
            <span className="section-kicker text-cyan">Start at the requirement.</span>
            <h2 className="mt-5 text-4xl font-semibold leading-[0.95] tracking-[-0.06em] sm:text-6xl">Give your next idea a system view.</h2>
            <p className="mt-6 max-w-lg text-sm leading-6 text-slate-400 sm:text-base sm:leading-7">Create a workspace for your product, map the moving parts, and let every agent work from the same source of truth.</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button onClick={() => openAuth("signup")}>Create a workspace <ArrowUpRight /></Button>
              <button className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/[0.08]" onClick={() => openAuth("login")}>I already have an account</button>
            </div>
          </div>
          <div className="cta-mark" aria-hidden="true"><BrandMark compact /><span className="cta-mark-label">SWE / 001</span></div>
        </div>
      </section>

      <footer className="border-t border-white/[0.08]">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-8 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-10">
          <BrandMark />
          <p>Built for traceable software engineering.</p>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em]">SZABIST / FYP 2026</p>
        </div>
      </footer>

      {authOpen && (
        <div className="auth-backdrop" role="presentation" onClick={() => setAuthOpen(false)}>
          <div className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="auth-title" onClick={(event) => event.stopPropagation()}>
            <button className="auth-close" aria-label="Close authentication dialog" onClick={() => setAuthOpen(false)}><X /></button>
            <div className="mb-8"><BrandMark /><h2 id="auth-title" className="mt-8 text-3xl font-semibold tracking-[-0.06em]">{authTitle}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{authDescription}</p></div>
            {authStep === "form" && <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
              <button className={authMode === "login" ? "is-active" : ""} role="tab" aria-selected={authMode === "login"} onClick={() => { setAuthMode("login"); setAuthStep("form"); setAuthError(null); setVerificationCode(""); setResendCooldown(0); }}>Sign in</button>
              <button className={authMode === "signup" ? "is-active" : ""} role="tab" aria-selected={authMode === "signup"} onClick={() => { setAuthMode("signup"); setAuthStep("form"); setAuthError(null); setVerificationCode(""); setResendCooldown(0); }}>Create account</button>
            </div>}
            {authStep === "success" ? (
              <div className="auth-success">
                <span className="auth-success-icon"><Check /></span>
                <h3>{authSuccessKind === "verified" ? "Account verified." : `Signed in${currentUser ? `, ${currentUser.name}` : ""}.`}</h3>
                <p>{authSuccessKind === "verified" ? "Your email is verified and you are signed in to SWE Autopilot." : "Your SWE Autopilot account is connected and ready for the control room."}</p>
                <Button className="mt-6 w-full" onClick={() => { setAuthStep("form"); setAuthError(null); }}>Back to form</Button>
              </div>
            ) : authStep === "verify" ? (
              <form className="auth-form" onSubmit={handleVerify}>
                <div className="verification-context">
                  <span className="verification-context-icon"><Shield className="size-3.5" /></span>
                  <p>A one-time code was requested for <strong>{verificationEmail}</strong>. You must receive and enter it to continue; an unverified address cannot access a workspace.</p>
                </div>
                <label>Verification code<input className="verification-code" name="verificationCode" type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} placeholder="000000" value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6))} required /></label>
                {authError && <div className="auth-error" role="alert">{authError}</div>}
                <Button type="submit" className="mt-2 w-full" disabled={authLoading || resendLoading}>{authLoading ? "Verifying…" : "Verify email"}<Check /></Button>
                <button type="button" className="verification-resend" onClick={handleResendVerification} disabled={authLoading || resendLoading || resendCooldown > 0}>
                  {resendLoading ? "Sending verification email…" : resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : "Resend verification code"}
                </button>
                <button type="button" className="verification-back" onClick={() => { setAuthStep("form"); setAuthError(null); setVerificationCode(""); setResendCooldown(0); }}>Use a different email</button>
              </form>
            ) : (
              <form className="auth-form" onSubmit={handleSubmit}>
                <div className="oauth-actions" aria-label="Social authentication options">
                  <button type="button" className="oauth-button" onClick={() => handleOAuth("google")}><GoogleIcon />Continue with Google</button>
                  <button type="button" className="oauth-button" onClick={() => handleOAuth("github")}><GitHubIcon />Continue with GitHub</button>
                </div>
                <div className="auth-divider"><span>or continue with email</span></div>
                {authMode === "signup" && <label>Full name<input name="name" type="text" placeholder="Ada Lovelace" maxLength={24} autoComplete="name" required /><span className="auth-field-hint">Maximum 24 characters</span></label>}
                <label>Work email<input name="email" type="email" placeholder="you@company.com" maxLength={320} autoComplete="email" required /><span className="auth-field-hint">You must be able to receive the verification code</span></label>
                <label>Password<div className="password-field"><input name="password" type={showPassword ? "text" : "password"} placeholder="••••••••" minLength={8} required /><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? <EyeOff /> : <Eye />}</button></div></label>
                {authMode === "login" && <div className="flex justify-end"><button type="button" className="text-xs text-cyan transition hover:text-white">Forgot password?</button></div>}
                {authError && <div className="auth-error" role="alert">{authError}</div>}
                <Button type="submit" className="mt-2 w-full" disabled={authLoading}>{authLoading ? "Connecting…" : authMode === "login" ? "Sign in to Autopilot" : "Create account"}<ArrowUpRight /></Button>
                <p className="text-center text-[11px] leading-5 text-slate-600">By continuing, you agree to the workspace terms and release-gate policy.</p>
              </form>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
