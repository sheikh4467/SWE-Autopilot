export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-3">
      <span className="relative grid size-9 place-items-center rounded-[13px] border border-cyan/40 bg-cyan/[0.08] shadow-[0_0_30px_rgba(101,233,255,0.18)]">
        <span className="absolute inset-[5px] rounded-[8px] border border-cyan/50" />
        <span className="relative size-2 rounded-full bg-cyan shadow-[0_0_12px_#65e9ff]" />
      </span>
      {!compact && (
        <span className="text-[15px] font-semibold tracking-[-0.04em] text-white">
          SWE <span className="text-cyan">Autopilot</span>
        </span>
      )}
    </span>
  );
}
