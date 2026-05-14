// Daystar — minimal icon set (24px stroke=1.75)
const Icon = ({ d, children, size = 18, fill = 'none', stroke = 'currentColor', strokeWidth = 1.75, ...props }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke={stroke} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" {...props}>
    {d ? <path d={d} /> : children}
  </svg>
);

const Icons = {
  Logo: ({ size = 20 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="2" y="2" width="20" height="20" rx="6" fill="url(#dsg)" />
      <path d="M7 12 L11 16 L17 8" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <defs>
        <linearGradient id="dsg" x1="0" y1="0" x2="24" y2="24">
          <stop offset="0" stopColor="#fb923c" />
          <stop offset="1" stopColor="#f97316" />
        </linearGradient>
      </defs>
    </svg>
  ),
  Home: (p) => <Icon {...p}><path d="M3 12 L12 4 L21 12" /><path d="M5 10 V20 H19 V10" /></Icon>,
  Box: (p) => <Icon {...p}><path d="M21 8 L12 3 L3 8 L12 13 Z" /><path d="M3 8 V16 L12 21 L21 16 V8" /><path d="M12 13 V21" /></Icon>,
  Cart: (p) => <Icon {...p}><circle cx="9" cy="20" r="1.5" /><circle cx="17" cy="20" r="1.5" /><path d="M3 4 H6 L8 14 H18 L20 7 H7" /></Icon>,
  Tag: (p) => <Icon {...p}><path d="M3 12 V3 H12 L21 12 L12 21 Z" /><circle cx="7.5" cy="7.5" r="1.2" fill="currentColor" stroke="none"/></Icon>,
  Users: (p) => <Icon {...p}><circle cx="9" cy="8" r="3.5" /><path d="M3 20 C3 16 6 14 9 14 C12 14 15 16 15 20" /><circle cx="17" cy="9" r="2.5" /><path d="M16 14 C19 14 21 16 21 20" /></Icon>,
  Settings: (p) => <Icon {...p}><circle cx="12" cy="12" r="3" /><path d="M12 2 V4 M12 20 V22 M4.93 4.93 L6.34 6.34 M17.66 17.66 L19.07 19.07 M2 12 H4 M20 12 H22 M4.93 19.07 L6.34 17.66 M17.66 6.34 L19.07 4.93" /></Icon>,
  Search: (p) => <Icon {...p} size={p.size || 16}><circle cx="11" cy="11" r="7" /><path d="M16 16 L21 21" /></Icon>,
  Bell: (p) => <Icon {...p}><path d="M6 8 C6 5 8 3 12 3 C16 3 18 5 18 8 V13 L20 16 H4 L6 13 Z" /><path d="M10 19 C10.5 20 11.2 20.5 12 20.5 C12.8 20.5 13.5 20 14 19" /></Icon>,
  Plus: (p) => <Icon {...p}><path d="M12 5 V19 M5 12 H19" /></Icon>,
  Filter: (p) => <Icon {...p}><path d="M3 5 H21 L14 13 V20 L10 18 V13 Z" /></Icon>,
  Download: (p) => <Icon {...p}><path d="M12 4 V15 M7 11 L12 16 L17 11" /><path d="M4 19 H20" /></Icon>,
  ChevronDown: (p) => <Icon {...p}><path d="M6 9 L12 15 L18 9" /></Icon>,
  ChevronRight: (p) => <Icon {...p}><path d="M9 6 L15 12 L9 18" /></Icon>,
  ChevronLeft: (p) => <Icon {...p}><path d="M15 6 L9 12 L15 18" /></Icon>,
  Up: (p) => <Icon {...p} size={p.size || 12}><path d="M5 15 L12 8 L19 15" /></Icon>,
  Down: (p) => <Icon {...p} size={p.size || 12}><path d="M5 9 L12 16 L19 9" /></Icon>,
  Check: (p) => <Icon {...p}><path d="M5 12 L10 17 L19 7" /></Icon>,
  X: (p) => <Icon {...p}><path d="M6 6 L18 18 M18 6 L6 18" /></Icon>,
  Mail: (p) => <Icon {...p}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 7 L12 13 L21 7" /></Icon>,
  Lock: (p) => <Icon {...p}><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11 V7 C8 4.5 9.8 3 12 3 C14.2 3 16 4.5 16 7 V11" /></Icon>,
  Eye: (p) => <Icon {...p}><path d="M2 12 C4 6 8 4 12 4 C16 4 20 6 22 12 C20 18 16 20 12 20 C8 20 4 18 2 12 Z" /><circle cx="12" cy="12" r="3" /></Icon>,
  EyeOff: (p) => <Icon {...p}><path d="M3 3 L21 21" /><path d="M9.5 9.5 C9 10.2 8.7 11.1 8.7 12 C8.7 13.8 10.2 15.3 12 15.3 C12.9 15.3 13.8 15 14.5 14.5" /><path d="M6 6.5 C4 8 3 10 2 12 C4 18 8 20 12 20 C13.6 20 15.1 19.7 16.5 19" /><path d="M11 4.1 C11.3 4 11.6 4 12 4 C16 4 20 6 22 12 C21.4 13.5 20.7 14.7 19.9 15.7" /></Icon>,
  ArrowLeft: (p) => <Icon {...p}><path d="M19 12 H5 M12 5 L5 12 L12 19" /></Icon>,
  ArrowRight: (p) => <Icon {...p}><path d="M5 12 H19 M12 5 L19 12 L12 19" /></Icon>,
  Trend: (p) => <Icon {...p}><path d="M3 17 L9 11 L13 15 L21 7" /><path d="M14 7 H21 V14" /></Icon>,
  Star: (p) => <Icon {...p}><path d="M12 3 L14.5 9 L21 9.5 L16 14 L17.5 20.5 L12 17 L6.5 20.5 L8 14 L3 9.5 L9.5 9 Z" /></Icon>,
  Edit: (p) => <Icon {...p}><path d="M4 20 H8 L19 9 L15 5 L4 16 Z" /><path d="M14 6 L18 10" /></Icon>,
  Copy: (p) => <Icon {...p}><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8 V6 C16 4.9 15.1 4 14 4 H6 C4.9 4 4 4.9 4 6 V14 C4 15.1 4.9 16 6 16 H8" /></Icon>,
  More: (p) => <Icon {...p}><circle cx="6" cy="12" r="1.2" fill="currentColor" /><circle cx="12" cy="12" r="1.2" fill="currentColor" /><circle cx="18" cy="12" r="1.2" fill="currentColor" /></Icon>,
  Calendar: (p) => <Icon {...p}><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10 H21 M8 3 V7 M16 3 V7" /></Icon>,
  Clock: (p) => <Icon {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7 V12 L15 14" /></Icon>,
  Pin: (p) => <Icon {...p}><path d="M12 2 V12 L18 18 V21 H6 V18 L12 12" /><path d="M9 8 H15" /></Icon>,
  Truck: (p) => <Icon {...p}><rect x="2" y="7" width="13" height="10" rx="1" /><path d="M15 10 H19 L22 14 V17 H15" /><circle cx="6" cy="18" r="1.8" /><circle cx="18" cy="18" r="1.8" /></Icon>,
  AlertTriangle: (p) => <Icon {...p}><path d="M12 4 L22 20 H2 Z" /><path d="M12 10 V14 M12 17 V17.1" /></Icon>,
  Logout: (p) => <Icon {...p}><path d="M16 17 L21 12 L16 7" /><path d="M21 12 H9" /><path d="M9 4 H5 C3.9 4 3 4.9 3 6 V18 C3 19.1 3.9 20 5 20 H9" /></Icon>,
  Camera: (p) => <Icon {...p}><rect x="3" y="7" width="18" height="13" rx="2" /><circle cx="12" cy="13" r="3.5" /><path d="M8 7 L9.5 4 H14.5 L16 7" /></Icon>,
  Building: (p) => <Icon {...p}><rect x="4" y="3" width="16" height="18" rx="1" /><path d="M9 7 H10 M14 7 H15 M9 11 H10 M14 11 H15 M9 15 H10 M14 15 H15 M10 21 V18 H14 V21" /></Icon>,
};

window.Icons = Icons;
