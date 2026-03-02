interface Props {
  size?: number;
  withText?: boolean;
}

export default function Brand({ size = 22, withText = true }: Props) {
  return (
    <div className="brand-mark">
      <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
        <defs>
          <linearGradient id="brand-g" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--brand-g1)" />
            <stop offset="100%" stopColor="var(--brand-g2)" />
          </linearGradient>
        </defs>
        <circle cx="32" cy="32" r="28" fill="none" stroke="url(#brand-g)" strokeWidth="3.5" />
        <g fill="url(#brand-g)">
          <polygon points="32,10 46,20 32,32 18,20" />
          <polygon points="54,32 50,50 32,32 50,14" opacity="0.85" />
          <polygon points="32,54 18,44 32,32 46,44" opacity="0.75" />
          <polygon points="10,32 14,50 32,32 14,14" opacity="0.65" />
        </g>
        <circle cx="32" cy="32" r="3.5" fill="var(--bg)" />
      </svg>
      {withText && <span className="brand-text">Aperture</span>}
    </div>
  );
}
