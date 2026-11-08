/** Thin-stroke icons with square caps (STYLE_GUIDE.md). Decorative: hidden from screen
 *  readers; the button or link around them carries the label. */
type Props = { size?: number; className?: string };

function Icon({ size = 22, className, children }: Props & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="square"
      aria-hidden="true"
      className={className}
    >
      {children}
    </svg>
  );
}

export const InboxIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M3 13l2.5-8h13L21 13v7H3z" />
    <path d="M3 13h5l1.5 2.5h5L16 13h5" />
  </Icon>
);
export const FolderIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M3 5h6l2 2h10v12H3z" />
  </Icon>
);
export const SearchIcon = (p: Props) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="M20 20l-4.2-4.2" />
  </Icon>
);
export const BackIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M15 5l-7 7 7 7" strokeWidth={2} />
  </Icon>
);
export const ChevronIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M9 6l6 6-6 6" />
  </Icon>
);
export const GripIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M4 8h16M4 12h16M4 16h16" strokeWidth={2} />
  </Icon>
);
export const PlusIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" strokeWidth={2} />
  </Icon>
);
export const GearIcon = (p: Props) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" />
  </Icon>
);
export const MoreIcon = ({ size = 22, className }: Props) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
    className={className}
  >
    <circle cx="5" cy="12" r="1.6" />
    <circle cx="12" cy="12" r="1.6" />
    <circle cx="19" cy="12" r="1.6" />
  </svg>
);
