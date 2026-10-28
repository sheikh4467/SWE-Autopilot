import { PageShell } from "@/components/page-shell";

type FeatureCard = {
  number: string;
  title: string;
  text: string;
  tag: string;
};

type FeaturePageProps = {
  eyebrow: string;
  title: string;
  description: string;
  accent: "cyan" | "violet" | "lime" | "orange";
  cards: FeatureCard[];
  quote: string;
  visual: "platform" | "workflow" | "security" | "about";
};

function Visual({ type }: { type: FeaturePageProps["visual"] }) {
  if (type === "workflow") {
    return (
      <div className="feature-visual feature-visual-workflow" aria-hidden="true">
        <span className="workflow-line workflow-line-one" />
        <span className="workflow-line workflow-line-two" />
        <span className="workflow-line workflow-line-three" />
        <div className="workflow-node workflow-node-one"><b>REQ</b><small>intent</small></div>
        <div className="workflow-node workflow-node-two"><b>ARC</b><small>architecture</small></div>
        <div className="workflow-node workflow-node-three"><b>RUN</b><small>evidence</small></div>
        <div className="workflow-node workflow-node-four"><b>SHIP</b><small>release gate</small></div>
      </div>
    );
  }

  if (type === "security") {
    return (
      <div className="feature-visual feature-visual-security" aria-hidden="true">
        <div className="security-shield"><span>✓</span></div>
        <span className="security-orbit security-orbit-one" />
        <span className="security-orbit security-orbit-two" />
        <span className="security-signal signal-one">AUTH / OK</span>
        <span className="security-signal signal-two">TOOLS / LOCKED</span>
        <span className="security-signal signal-three">EVIDENCE / LIVE</span>
      </div>
    );
  }

  if (type === "about") {
    return (
      <div className="feature-visual feature-visual-about" aria-hidden="true">
        <div className="about-stack about-stack-back">HUMAN INTENT</div>
        <div className="about-stack about-stack-middle">AGENT RUNTIME</div>
        <div className="about-stack about-stack-front">VERIFIED SOFTWARE</div>
        <span className="about-pin about-pin-one" />
        <span className="about-pin about-pin-two" />
        <span className="about-pin about-pin-three" />
      </div>
    );
  }

  return (
    <div className="feature-visual feature-visual-platform" aria-hidden="true">
      <div className="platform-grid" />
      <div className="platform-core"><span>RUNTIME</span><strong>01</strong></div>
      <span className="platform-node platform-node-one">REQ</span>
      <span className="platform-node platform-node-two">CODE</span>
      <span className="platform-node platform-node-three">TEST</span>
      <span className="platform-node platform-node-four">SHIP</span>
    </div>
  );
}

export function FeaturePage({
  eyebrow,
  title,
  description,
  accent,
  cards,
  quote,
  visual,
}: FeaturePageProps) {
  const introCopy = {
    platform: { eyebrow: "System map", title: "The platform is the connective tissue." },
    workflow: { eyebrow: "Sequence", title: "The work moves in deliberate stages." },
    security: { eyebrow: "Trust layer", title: "Protection is visible at every boundary." },
    about: { eyebrow: "Point of view", title: "The idea behind the control plane." },
  }[visual];

  return (
    <PageShell eyebrow={eyebrow} title={title} description={description} accent={accent} kind={visual}>
      <section className={`feature-intro feature-intro-${visual} route-depth-layer`}>
        <div>
          <span className="section-kicker">{introCopy.eyebrow}</span>
          <h2>{introCopy.title}</h2>
        </div>
        <Visual type={visual} />
      </section>

      <section className={`feature-card-grid feature-card-grid-${visual} route-depth-layer`}>
        {cards.map((card) => (
          <article className={`feature-card feature-card-${visual} depth-card`} key={card.number}>
            <div className="feature-card-top"><span>{card.number}</span><small>{card.tag}</small></div>
            <h3>{card.title}</h3>
            <p>{card.text}</p>
            <span className="feature-card-arrow">↗</span>
          </article>
        ))}
      </section>

      <section className="feature-quote route-depth-layer">
        <span className="quote-mark">“</span>
        <p>{quote}</p>
      </section>
    </PageShell>
  );
}
