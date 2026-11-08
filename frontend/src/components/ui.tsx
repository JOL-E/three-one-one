import { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router";

import type { ItemStatus } from "../api/types";
import { onToast } from "../lib/toast";
import { BackIcon } from "./icons";

/** A screen's top: optional back link, a small mono kicker, the large title, actions. */
export function ScreenHeader({
  title,
  kicker,
  back,
  actions,
  children,
}: {
  title: ReactNode;
  kicker?: ReactNode;
  back?: { to: string; label: string };
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="border-rule pt-edge shrink-0 border-b-2 lg:pt-0">
      {back ? (
        <div className="px-2 pt-2 lg:hidden">
          <Link
            to={back.to}
            className="text-accent inline-flex h-11 items-center gap-1 px-2 text-[17px] active:opacity-50"
          >
            <BackIcon size={20} />
            {back.label}
          </Link>
        </div>
      ) : null}
      <div className={`flex flex-col gap-1 px-5 pb-3 lg:px-7 lg:pt-7 ${back ? "" : "pt-4"}`}>
        {kicker ? <div className="label text-muted text-[12px]">{kicker}</div> : null}
        <div className="flex items-end justify-between gap-3">
          <h1 className="m-0 min-w-0 text-[34px] leading-tight font-extrabold tracking-[-0.02em] break-words lg:text-[32px]">
            {title}
          </h1>
          {actions ? <div className="flex shrink-0 items-center gap-1 pb-1">{actions}</div> : null}
        </div>
        {children}
      </div>
    </header>
  );
}

/** Square button with a 2px border; "ink" fills with the text color, "accent" with green. */
export function Button({
  tone = "outline",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "outline" | "ink" | "accent" | "danger" }) {
  const tones = {
    outline: "border-rule text-text bg-transparent",
    ink: "border-text bg-text text-ground",
    accent: "border-accent bg-accent text-on-accent",
    danger: "border-danger text-danger-text bg-transparent",
  };
  return (
    <button
      type="button"
      {...props}
      className={`label inline-flex h-11 items-center justify-center border-2 px-4 text-[12px] active:opacity-60 disabled:opacity-40 ${tones[tone]} ${className}`}
    />
  );
}

export function IconButton({
  label,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      {...props}
      className={`text-text flex h-11 w-11 items-center justify-center active:opacity-50 ${props.className ?? ""}`}
    />
  );
}

export function ShortId({ id, className = "" }: { id: string; className?: string }) {
  return (
    <span className={`text-accent font-mono text-[13px] font-semibold ${className}`}>#{id}</span>
  );
}

/** Status stamp: Doing is filled green; Open shows none; Done is said by the strikethrough. */
export function Stamp({ status }: { status: ItemStatus }) {
  if (status !== "doing") return null;
  return <span className="label bg-accent text-on-accent shrink-0 px-2 py-[3px]">Doing</span>;
}

/** A labelled text field with the hard 2px border. */
export function Field({
  label,
  multiline = false,
  ...props
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
  type?: string;
}) {
  const { value, onChange, ...rest } = props;
  const className =
    "border-rule bg-surface text-text w-full border-2 px-3 py-2.5 text-[17px] outline-none focus:border-accent";
  return (
    <label className="flex flex-col gap-1.5">
      <span className="label text-muted">{label}</span>
      {multiline ? (
        <textarea
          rows={4}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={className}
          {...rest}
        />
      ) : (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={className}
          {...rest}
        />
      )}
    </label>
  );
}

export function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <div aria-hidden="true">
      {Array.from({ length: count }, (_, n) => (
        <div key={n} className="border-hairline flex h-[66px] items-center gap-3 border-b px-5">
          <span className="bg-hairline animate-shimmer h-3 w-10" />
          <span className="bg-hairline animate-shimmer h-3.5 flex-1" />
        </div>
      ))}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-muted px-5 py-10 text-center text-[15px] lg:px-7">{children}</p>;
}

/** Shows toast() messages at the bottom for a few seconds (refused writes, mostly). */
export function Toaster() {
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const off = onToast((m) => {
      setMessage(m);
      clearTimeout(timer);
      timer = setTimeout(() => setMessage(null), 4500);
    });
    return () => {
      off();
      clearTimeout(timer);
    };
  }, []);
  if (!message) return null;
  return (
    <div
      role="status"
      className="bg-text text-ground animate-fade-in fixed inset-x-4 bottom-[calc(env(safe-area-inset-bottom)+76px)] z-[60] mx-auto max-w-md px-4 py-3 text-[15px] lg:bottom-6"
    >
      {message}
    </div>
  );
}
