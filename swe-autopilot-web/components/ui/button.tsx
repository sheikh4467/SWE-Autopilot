import * as React from "react";

type ButtonVariant = "primary" | "ghost" | "outline" | "dark";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-cyan text-ink shadow-[0_10px_35px_rgba(101,233,255,0.22)] hover:-translate-y-0.5 hover:bg-[#8bf0ff]",
  ghost:
    "bg-white/[0.05] text-white hover:-translate-y-0.5 hover:bg-white/[0.1]",
  outline:
    "border border-white/15 bg-white/[0.03] text-white hover:-translate-y-0.5 hover:border-cyan/60 hover:bg-cyan/[0.08]",
  dark:
    "bg-ink text-white shadow-[0_15px_45px_rgba(7,17,31,0.2)] hover:-translate-y-0.5 hover:bg-[#10213a]",
};

export function Button({
  className = "",
  variant = "primary",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-semibold tracking-[-0.01em] transition duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-ink disabled:pointer-events-none disabled:opacity-50 ${variantClasses[variant]} ${className}`}
      {...props}
    />
  );
}
