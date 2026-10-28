import { FeaturePage } from "@/components/feature-page";

export default function SecurityPage() {
  return (
    <FeaturePage
      eyebrow="03 / Security"
      title="Safety is part of the workflow, not a final checkbox."
      description="SWE Autopilot keeps identity, permissions, sandbox execution, verification evidence, and approval gates in the same operational loop."
      accent="lime"
      visual="security"
      quote="Generated code is a hypothesis. The system earns trust by showing what it ran, what it observed, and who approved the next step."
      cards={[
        { number: "01", tag: "Identity", title: "Verified accounts only.", text: "Email OTP verification and provider-verified identities stop unverified accounts before workspace access." },
        { number: "02", tag: "Permissions", title: "Tools are explicit and auditable.", text: "Agents do not receive unlimited access. Sensitive actions are scoped, reviewed, and recorded." },
        { number: "03", tag: "Sandbox", title: "Generated software runs behind a boundary.", text: "Docker execution keeps build and runtime behavior away from an unrestricted host environment." },
        { number: "04", tag: "Evidence", title: "Failure stays visible.", text: "Incomplete checks, malformed output, and policy blocks remain visible instead of becoming silent success." },
      ]}
    />
  );
}
