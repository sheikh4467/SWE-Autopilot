import { FeaturePage } from "@/components/feature-page";

export default function WorkflowPage() {
  return (
    <FeaturePage
      eyebrow="02 / Workflow"
      title="Move from first thought to verified release."
      description="The workflow turns a changing requirement into a controlled sequence of analysis, architecture, generation, execution, review, and evidence."
      accent="violet"
      visual="workflow"
      quote="The human stays in control of the gates. Agents handle the repetition, the coordination, and the heavy lifting between them."
      cards={[
        { number: "01", tag: "Understand", title: "Compile intent into testable work.", text: "Detect ambiguity, missing acceptance criteria, conflicts, and risk before implementation begins." },
        { number: "02", tag: "Design", title: "Challenge architecture before code.", text: "Generate alternatives, run critic reviews, and keep the rationale attached to the approved direction." },
        { number: "03", tag: "Build", title: "Generate with bounded permissions.", text: "Specialized agents create application artifacts while the runtime controls repository and tool access." },
        { number: "04", tag: "Verify", title: "Execute and inspect real evidence.", text: "Run generated software inside a Docker boundary and use the observed results to decide what happens next." },
      ]}
    />
  );
}
