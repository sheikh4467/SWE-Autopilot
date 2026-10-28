import { FeaturePage } from "@/components/feature-page";

export default function PlatformPage() {
  return (
    <FeaturePage
      eyebrow="01 / Platform"
      title="One control plane for the whole build."
      description="SWE Autopilot connects requirements, architecture, code, verification, and release decisions so your team can see the system instead of chasing disconnected outputs."
      accent="cyan"
      visual="platform"
      quote="The platform is not another chat box. It is the layer that keeps every engineering decision attached to the work it created."
      cards={[
        { number: "01", tag: "Traceability", title: "Requirements become a living system map.", text: "Turn natural language into structured requirements, stories, acceptance criteria, and relationships that survive every downstream change." },
        { number: "02", tag: "Runtime", title: "Agents work inside explicit guardrails.", text: "Every tool call, artifact version, approval, and execution state is controlled by a deterministic runtime." },
        { number: "03", tag: "Evidence", title: "Release decisions come with receipts.", text: "Build output, runtime logs, test results, and security signals stay attached to the artifacts they verify." },
        { number: "04", tag: "Workspace", title: "The project history stays queryable.", text: "Keep the people, agents, decisions, risks, and evidence in one workspace that can be reviewed at any point." },
      ]}
    />
  );
}
