"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { useAuthSession } from "@/components/auth-session";
import { RouteBrandMark } from "@/components/route-brandmark";
import { Button } from "@/components/ui/button";

const navigation = [
  { href: "/platform", label: "Platform" },
  { href: "/workflow", label: "Workflow" },
  { href: "/security", label: "Security" },
  { href: "/about", label: "About" },
];

type PageShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  accent?: "cyan" | "violet" | "lime" | "orange";
  kind: "platform" | "workflow" | "security" | "about";
  children: ReactNode;
};

function RouteHeroVisual({ kind }: { kind: PageShellProps["kind"] }) {
  if (kind === "workflow") {
    return (
      <div className="route-hero-visual route-hero-visual-workflow" aria-hidden="true">
        <span className="hero-workflow-track hero-workflow-track-one" />
        <span className="hero-workflow-track hero-workflow-track-two" />
        <div className="hero-workflow-stage hero-workflow-stage-one"><b>01</b><small>INTENT</small></div>
        <div className="hero-workflow-stage hero-workflow-stage-two"><b>02</b><small>BUILD</small></div>
        <div className="hero-workflow-stage hero-workflow-stage-three"><b>03</b><small>PROVE</small></div>
      </div>
    );
  }

  if (kind === "security") {
    return (
      <div className="route-hero-visual route-hero-visual-security" aria-hidden="true">
        <div className="hero-security-lock"><span>✓</span><small>VERIFIED</small></div>
        <span className="hero-security-ring hero-security-ring-one" />
        <span className="hero-security-ring hero-security-ring-two" />
        <span className="hero-security-chip hero-security-chip-one">IDENTITY</span>
        <span className="hero-security-chip hero-security-chip-two">EVIDENCE</span>
      </div>
    );
  }

  if (kind === "about") {
    return (
      <div className="route-hero-visual route-hero-visual-about" aria-hidden="true">
        <div className="hero-about-sun" />
        <div className="hero-about-orbit hero-about-orbit-one" />
        <div className="hero-about-orbit hero-about-orbit-two" />
        <div className="hero-about-label hero-about-label-one">HUMAN</div>
        <div className="hero-about-label hero-about-label-two">AGENT</div>
        <div className="hero-about-label hero-about-label-three">SYSTEM</div>
      </div>
    );
  }

  return (
    <div className="route-hero-visual route-hero-visual-platform" aria-hidden="true">
      <div className="route-hero-core"><span>SWE</span><strong>AUTO</strong><small>control plane</small></div>
      <div className="route-hero-ring route-hero-ring-one" />
      <div className="route-hero-ring route-hero-ring-two" />
      <div className="route-hero-ring route-hero-ring-three" />
      <span className="route-hero-node route-hero-node-one" />
      <span className="route-hero-node route-hero-node-two" />
      <span className="route-hero-node route-hero-node-three" />
    </div>
  );
}

export function PageShell({
  eyebrow,
  title,
  description,
  accent = "cyan",
  kind,
  children,
}: PageShellProps) {
  const pathname = usePathname();
  const { user, loading: sessionLoading, logout } = useAuthSession();
  const [scrollProgress, setScrollProgress] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const updateScene = () => {
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      const progress = maxScroll > 0 ? window.scrollY / maxScroll : 0;
      setScrollProgress(progress * 100);
      document.documentElement.style.setProperty("--scene-progress", progress.toFixed(3));
      document.documentElement.style.setProperty("--scene-tilt", `${(progress * 2.4).toFixed(2)}deg`);
    };

    updateScene();
    window.addEventListener("scroll", updateScene, { passive: true });
    return () => window.removeEventListener("scroll", updateScene);
  }, []);

  const openAuth = (mode: "login" | "signup") => {
    window.location.assign(`/?openAuth=${mode}`);
  };

  const handleLogout = async () => {
    await logout();
  };

  return (
    <main className={`route-shell route-shell-${accent} route-shell-${kind}`}>
      <div className="scroll-progress" style={{ width: `${scrollProgress}%` }} />
      <div className="ambient ambient-one" aria-hidden="true" />
      <div className="ambient ambient-two" aria-hidden="true" />
      <div className="page-grid" aria-hidden="true" />
      <div className="noise-layer" aria-hidden="true" />

      <header className="route-header">
        <div className="route-header-inner">
          <Link href="/" aria-label="SWE Autopilot home" onClick={() => setMenuOpen(false)}>
            <RouteBrandMark kind={kind} />
          </Link>
          <nav className="route-nav" aria-label="Primary navigation">
            {navigation.map((item) => (
              <Link
                key={item.href}
                className={pathname === item.href ? "route-nav-link is-active" : "route-nav-link"}
                href={item.href}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="route-actions">
            {sessionLoading ? (
              <span className="route-signin">Checking session…</span>
            ) : user ? (
              <>
                <Link className="route-signin" href="/workspace">Hi, {user.name}</Link>
                <button className="route-signout" onClick={() => void handleLogout()}>Sign out</button>
              </>
            ) : (
              <>
                <Link className="route-signin" href="/?openAuth=login">Sign in</Link>
                <Button className="route-cta" onClick={() => openAuth("signup")}>
                  Get started
                </Button>
              </>
            )}
          </div>
          <button
            className="route-menu-button"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span />
            <span />
          </button>
        </div>
        {menuOpen && (
          <div className="route-mobile-menu">
            {navigation.map((item) => (
              <Link key={item.href} href={item.href} onClick={() => setMenuOpen(false)}>
                {item.label}
              </Link>
            ))}
            <div className="route-mobile-actions">
              {sessionLoading ? (
                <span className="route-signin">Checking session…</span>
              ) : user ? (
                <>
                  <Link href="/workspace" onClick={() => setMenuOpen(false)}>Workspace · {user.name}</Link>
                  <button className="route-signout" onClick={() => { setMenuOpen(false); void handleLogout(); }}>Sign out</button>
                </>
              ) : (
                <>
                  <Link href="/?openAuth=login" onClick={() => setMenuOpen(false)}>Sign in</Link>
                  <Button onClick={() => openAuth("signup")}>Get started</Button>
                </>
              )}
            </div>
          </div>
        )}
      </header>

      <section className="route-hero route-depth-layer">
        <div className="route-hero-copy">
          <span className="section-kicker">{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <RouteHeroVisual kind={kind} />
      </section>

      <div className="route-content">{children}</div>

      <footer className="route-footer">
        <RouteBrandMark kind={kind} />
        <span>Traceable software engineering / SZABIST FYP 2026</span>
        <Link href="/workspace">Open workspace →</Link>
      </footer>
    </main>
  );
}
