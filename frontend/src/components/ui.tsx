import type { ReactNode } from 'react';

import { statusLabel, statusTone, type Tone } from '../lib/format';

/** Small, consistent set of primitives — one component system, no overlapping libraries. */

/* ------------------------------------------------------------------ button */

type ButtonVariant = 'primary' | 'secondary' | 'ghost';
type ButtonSize = 'md' | 'sm';

const BUTTON_BASE =
  'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors ' +
  'disabled:cursor-not-allowed disabled:opacity-50 select-none';

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: 'bg-accent-600 text-white hover:bg-accent-700',
  secondary: 'bg-surface text-ink border border-line-strong hover:bg-surface-muted',
  ghost: 'text-ink-muted hover:text-ink hover:bg-surface-muted',
};

const BUTTON_SIZE: Record<ButtonSize, string> = {
  md: 'h-9 px-3.5 text-sm',
  sm: 'h-8 px-3 text-xs',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  className = '',
  children,
  ...rest
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={`${BUTTON_BASE} ${BUTTON_VARIANT[variant]} ${BUTTON_SIZE[size]} ${className}`}
      disabled={rest.disabled || loading}
      {...rest}
    >
      {loading ? <Spinner /> : null}
      {children}
    </button>
  );
}

export function Spinner({ className = '' }: { className?: string }) {
  return (
    <svg
      className={`h-3.5 w-3.5 animate-spin ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ------------------------------------------------------------------ status */

const TONE_CLASS: Record<Tone, string> = {
  ok: 'border-ok/25 bg-ok-bg text-ok',
  warn: 'border-warn/25 bg-warn-bg text-warn',
  danger: 'border-danger/25 bg-danger-bg text-danger',
  neutral: 'border-line-strong bg-surface-muted text-ink-muted',
  muted: 'border-line-strong bg-surface-muted text-ink-muted',
};

export function StatusPill({
  status,
  label,
  tone,
  title,
}: {
  status?: string | null;
  label?: string;
  tone?: Tone;
  title?: string;
}) {
  const resolvedTone = tone ?? statusTone(status);
  const text = label ?? statusLabel(status);
  return (
    <span
      title={title}
      className={`inline-flex items-center whitespace-nowrap rounded-sm border px-1.5 py-0.5 text-xs font-medium ${TONE_CLASS[resolvedTone]}`}
    >
      {text}
    </span>
  );
}

/** Marks data that a human typed in, rather than data retrieved from a source. */
export function TestTag({ title }: { title?: string }) {
  return (
    <span
      title={title ?? 'Entered manually for testing — not retrieved from a live source'}
      className="inline-flex items-center rounded-sm border border-line-strong bg-surface-muted px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-ink-subtle"
    >
      Test data
    </span>
  );
}

/* -------------------------------------------------------------- layout bits */

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-xl">{title}</h1>
        {description ? (
          <p className="mt-1 max-w-2xl text-sm text-ink-muted">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Panel({
  title,
  description,
  actions,
  children,
  className = '',
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-lg border border-line bg-surface shadow-xs ${className}`}
    >
      {title || actions ? (
        <header className="flex items-center justify-between gap-4 border-b border-line px-5 py-3.5">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold">{title}</h2>
            {description ? (
              <p className="mt-0.5 text-xs text-ink-subtle">{description}</p>
            ) : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </header>
      ) : null}
      <div className="p-5">{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------------- states */

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div
      className="flex items-center gap-2.5 rounded-lg border border-line bg-surface px-5 py-8 text-sm text-ink-muted"
      role="status"
      aria-live="polite"
    >
      <Spinner className="text-accent-600" />
      {label}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      className="rounded-lg border border-danger/30 bg-danger-bg px-5 py-4"
      role="alert"
    >
      <p className="text-sm font-medium text-danger">Something went wrong</p>
      <p className="mt-1 break-words text-sm text-ink-muted">{message}</p>
      {onRetry ? (
        <div className="mt-3">
          <Button size="sm" onClick={onRetry}>
            Try again
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-line-strong bg-surface-muted px-6 py-10 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-ink-muted">{description}</p>
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ table */

export function Table({ children, caption }: { children: ReactNode; caption?: string }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full border-collapse text-sm">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        {children}
      </table>
    </div>
  );
}

export function TH({
  children,
  className = '',
  align = 'left',
}: {
  children?: ReactNode;
  className?: string;
  align?: 'left' | 'right' | 'center';
}) {
  return (
    <th
      scope="col"
      className={`border-b border-line bg-surface-muted px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-ink-subtle ${
        align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'
      } ${className}`}
    >
      {children}
    </th>
  );
}

export function TD({
  children,
  className = '',
  align = 'left',
}: {
  children?: ReactNode;
  className?: string;
  align?: 'left' | 'right' | 'center';
}) {
  return (
    <td
      className={`border-b border-line px-4 py-3 align-middle text-ink-muted last:border-b-0 ${
        align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'
      } ${className}`}
    >
      {children}
    </td>
  );
}

/* ------------------------------------------------------------------- forms */

export function Field({
  label,
  hint,
  htmlFor,
  required,
  children,
}: {
  label: string;
  hint?: string;
  htmlFor: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="mb-1.5 block text-sm font-medium text-ink"
      >
        {label}
        {required ? <span className="ml-0.5 text-danger">*</span> : null}
      </label>
      {children}
      {hint ? <p className="mt-1.5 text-xs text-ink-subtle">{hint}</p> : null}
    </div>
  );
}

export const inputClass =
  'block h-9 w-full rounded-md border border-line-strong bg-surface px-3 text-sm text-ink ' +
  'placeholder:text-ink-subtle hover:border-line-strong focus:border-accent-500 focus:outline-none ' +
  'focus:ring-2 focus:ring-accent-500/20 disabled:bg-surface-muted disabled:text-ink-subtle';

/* ------------------------------------------------------------------ card */

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-line bg-surface shadow-xs ${className}`}>{children}</section>;
}

export function CardHeader({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <header className={`border-b border-line px-5 py-3.5 ${className}`}>{children}</header>;
}

export function CardContent({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`p-5 ${className}`}>{children}</div>;
}

/* ------------------------------------------------------------------ badge */

type BadgeColor = 'ok' | 'warn' | 'danger' | 'neutral' | 'error' | 'muted';

const BADGE_COLOR: Record<BadgeColor, string> = {
  ok: 'border-ok/25 bg-ok-bg text-ok',
  warn: 'border-warn/25 bg-warn-bg text-warn',
  danger: 'border-danger/25 bg-danger-bg text-danger',
  error: 'border-danger/25 bg-danger-bg text-danger',
  neutral: 'border-line-strong bg-surface-muted text-ink-muted',
  muted: 'border-line-strong bg-surface-muted text-ink-muted',
};

export function Badge({ color = 'neutral', children, className = '' }: { color?: BadgeColor; children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-sm border px-1.5 py-0.5 text-xs font-medium ${BADGE_COLOR[color]} ${className}`}>
      {children}
    </span>
  );
}

/* ---------------------------------------------------------------- table wrappers */

export function TableHeader({ children }: { children: ReactNode }) {
  return <thead>{children}</thead>;
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function TableRow({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <tr className={className}>{children}</tr>;
}

export function TableCell({ children, className = '', align = 'left' }: { children: ReactNode; className?: string; align?: 'left' | 'right' | 'center' }) {
  return (
    <td className={`border-b border-line px-4 py-3 align-middle text-ink-muted last:border-b-0 ${align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'} ${className}`}>
      {children}
    </td>
  );
}

export function TableHead({ children, className = '', align = 'left' }: { children: ReactNode; className?: string; align?: 'left' | 'right' | 'center' }) {
  return (
    <th scope="col" className={`border-b border-line bg-surface-muted px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-ink-subtle ${align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'} ${className}`}>
      {children}
    </th>
  );
}

/* ---------------------------------------------------------------- layout */

export function Separator({ orientation = 'horizontal', className = '' }: { orientation?: 'horizontal' | 'vertical'; className?: string }) {
  if (orientation === 'vertical') {
    return <span className={`h-6 w-px bg-line ${className}`} aria-hidden="true" />;
  }
  return <hr className={`w-full border-t border-line ${className}`} aria-hidden="true" />;
}

export function Flex({ children, className = '', justify, align, gap, wrap, ...rest }: {
  children: ReactNode;
  className?: string;
  justify?: 'start' | 'center' | 'end' | 'between' | 'around';
  align?: 'start' | 'center' | 'end' | 'stretch' | 'baseline';
  gap?: number | string;
  wrap?: boolean;
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`flex ${wrap ? 'flex-wrap' : ''} ${justify ? `justify-${justify}` : ''} ${align ? `items-${align}` : ''} ${gap ? `gap-${gap}` : ''} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export function Box({ children, className = '', ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={className} {...rest}>{children}</div>;
}

export function Heading({ children, size = 'md', className = '', weight, ...rest }: {
  children: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl';
  className?: string;
  weight?: 'normal' | 'medium' | 'semibold' | 'bold';
} & React.HTMLAttributes<HTMLHeadingElement>) {
  const SIZE_CLASS: Record<string, string> = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
    xl: 'text-xl',
    '2xl': 'text-2xl',
    '3xl': 'text-3xl',
    '4xl': 'text-4xl',
  };
  const WEIGHT_CLASS: Record<string, string> = {
    normal: 'font-normal',
    medium: 'font-medium',
    semibold: 'font-semibold',
    bold: 'font-bold',
  };
  return <h1 className={`${SIZE_CLASS[size]} ${WEIGHT_CLASS[weight ?? 'semibold']} ${className}`} {...rest}>{children}</h1>;
}

export function Text({ children, className = '', size = 'md', color, weight, ...rest }: {
  children: ReactNode;
  className?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  color?: 'ink' | 'ink-muted' | 'ink-subtle' | 'muted' | 'ok' | 'warn' | 'danger' | 'accent' | 'error';
  weight?: 'normal' | 'medium' | 'semibold' | 'bold';
} & React.HTMLAttributes<HTMLSpanElement>) {
  const SIZE_CLASS: Record<string, string> = {
    xs: 'text-xs',
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
    xl: 'text-xl',
  };
  const COLOR_CLASS: Record<string, string> = {
    ink: 'text-ink',
    'ink-muted': 'text-ink-muted',
    'ink-subtle': 'text-ink-subtle',
    muted: 'text-ink-muted',
    ok: 'text-ok',
    warn: 'text-warn',
    danger: 'text-danger',
    accent: 'text-accent-600',
    error: 'text-danger',
  };
  const WEIGHT_CLASS: Record<string, string> = {
    normal: 'font-normal',
    medium: 'font-medium',
    semibold: 'font-semibold',
    bold: 'font-bold',
  };
  return <span className={`${SIZE_CLASS[size]} ${COLOR_CLASS[color ?? 'ink']} ${WEIGHT_CLASS[weight ?? 'normal']} ${className}`} {...rest}>{children}</span>;
}

export function Stack({ children, className = '', gap = 4, ...rest }: { children: ReactNode; className?: string; gap?: number | string; } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`flex flex-col ${gap ? `gap-${gap}` : ''} ${className}`} {...rest}>{children}</div>;
}
