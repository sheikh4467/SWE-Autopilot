import { FeaturePage } from "@/components/feature-page";

export default function AboutPage() {
  return (
    <FeaturePage
      eyebrow="04 / About"
      title="We are engineering an autonomous workflow."
      description="SWE Autopilot is an FYP platform for making software development more traceable, reviewable, and evidence-driven across the full SDLC."
      accent="orange"
      visual="about"
      quote="A better coding assistant writes a file. A better engineering system explains why the file exists, what it changed, and whether it can be trusted."
      cards={[
        { number: "01", tag: "Mission", title: "Give every idea a system view.", text: "Make the moving parts of software visible from the first requirement through the final verification decision." },
        { number: "02", tag: "Research", title: "Coordinate specialized agents.", text: "Explore how an Agent Runtime can make LLM-based engineering workflows more deterministic and accountable." },
        { number: "03", tag: "FYP", title: "Build the foundation first.", text: "FYP-I focuses on requirements, architecture, code generation, sandbox execution, and initial evidence-based verification." },
        { number: "04", tag: "People", title: "Keep human judgment in the loop.", text: "The system automates repeatable work while preserving explicit review gates for the decisions that matter." },
      ]}
    />
  );
}
