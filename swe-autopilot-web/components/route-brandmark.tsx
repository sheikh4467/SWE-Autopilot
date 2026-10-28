type RouteBrandKind = "platform" | "workflow" | "security" | "about";

type RouteBrandMarkProps = {
  kind: RouteBrandKind;
};

export function RouteBrandMark({ kind }: RouteBrandMarkProps) {
  if (kind === "workflow") {
    return (
      <span className="route-brand route-brand-workflow" aria-label="SWE Autopilot Workflow">
        <span className="route-brand-glyph"><i /><i /><i /></span>
        <span><b>FLOW</b><small>/ SWE AUTOPILOT</small></span>
      </span>
    );
  }

  if (kind === "security") {
    return (
      <span className="route-brand route-brand-security" aria-label="SWE Autopilot Security">
        <span className="route-brand-glyph"><i>✓</i></span>
        <span><b>GUARD</b><small>/ SWE AUTOPILOT</small></span>
      </span>
    );
  }

  if (kind === "about") {
    return (
      <span className="route-brand route-brand-about" aria-label="SWE Autopilot About">
        <span className="route-brand-glyph"><i /><i /><i /></span>
        <span><b>ORIGIN</b><small>/ SWE AUTOPILOT</small></span>
      </span>
    );
  }

  return (
    <span className="route-brand route-brand-platform" aria-label="SWE Autopilot Platform">
      <span className="route-brand-glyph"><i /><i /></span>
      <span><b>PLATFORM</b><small>/ SWE AUTOPILOT</small></span>
    </span>
  );
}
