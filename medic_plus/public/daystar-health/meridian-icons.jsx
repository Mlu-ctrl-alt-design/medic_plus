// Meridian icons — extends Daystar icon set
const MIcon = ({ d, children, size = 18, fill = 'none', stroke = 'currentColor', strokeWidth = 1.75, ...props }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke={stroke} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" {...props}>
    {d ? <path d={d} /> : children}
  </svg>
);

const MeridianLogo = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <rect x="2" y="2" width="20" height="20" rx="6" fill="url(#mhg)" />
    <path d="M5 14 L8 14 L10 10 L13 16 L15 12 L19 12" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    <defs>
      <linearGradient id="mhg" x1="0" y1="0" x2="24" y2="24">
        <stop offset="0" stopColor="#3b82f6" />
        <stop offset="1" stopColor="#2563eb" />
      </linearGradient>
    </defs>
  </svg>
);

window.MIcons = {
  ...window.Icons,
  Logo: MeridianLogo,
  Stethoscope: (p) => <MIcon {...p}><path d="M5 3 V10 C5 13 7 15 10 15 C13 15 15 13 15 10 V3" /><path d="M3 3 H7 M13 3 H17" /><path d="M10 15 V18 C10 20 12 21 14 21 C16 21 18 20 18 18 V16" /><circle cx="18" cy="14" r="2" /></MIcon>,
  Heart: (p) => <MIcon {...p}><path d="M12 21 C7 17 3 13 3 9 C3 6 5 4 8 4 C10 4 11 5 12 7 C13 5 14 4 16 4 C19 4 21 6 21 9 C21 13 17 17 12 21 Z" /></MIcon>,
  Pill: (p) => <MIcon {...p}><rect x="3" y="9" width="18" height="6" rx="3" transform="rotate(-30 12 12)" /><line x1="9" y1="6" x2="15" y2="18" /></MIcon>,
  ClipBoard: (p) => <MIcon {...p}><rect x="6" y="4" width="12" height="17" rx="2" /><rect x="9" y="2" width="6" height="3" rx="1" /><path d="M9 11 H15 M9 14 H15 M9 17 H13" /></MIcon>,
  Beaker: (p) => <MIcon {...p}><path d="M9 3 V10 L4 19 C3.5 20 4 21 5 21 H19 C20 21 20.5 20 20 19 L15 10 V3" /><path d="M8 3 H16" /><path d="M6 16 H18" /></MIcon>,
  Activity: (p) => <MIcon {...p}><path d="M3 12 H7 L9 6 L13 18 L15 12 L17 14 H21" /></MIcon>,
  Menu: (p) => <MIcon {...p}><path d="M4 7 H20 M4 12 H20 M4 17 H20" /></MIcon>,
};
