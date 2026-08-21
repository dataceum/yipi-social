/**
 * Small hand-picked set of stroke icons (Feather-style, MIT-license-alike
 * simple paths) so the app has no icon-font/icon-package dependency.
 * Usage: <Icon.Home /> — every icon accepts standard svg props (size, etc).
 */
const base = {
  xmlns: 'http://www.w3.org/2000/svg',
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

function make(paths, size = 20) {
  return function IconCmp(props) {
    return (
      <svg {...base} width={size} height={size} {...props}>
        {paths}
      </svg>
    )
  }
}

export const Icon = {
  Home: make(<path d="M3 11.5 12 4l9 7.5M5 10v10h5v-6h4v6h5V10" />),
  Search: make(<><circle cx="11" cy="11" r="7" /><path d="m20 20-3.2-3.2" /></>),
  Spaces: make(
    <>
      <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z" />
      <path d="M7 11a5 5 0 0 0 10 0M12 19v3" />
    </>
  ),
  User: make(<><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" /></>),
  Settings: make(
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1Z" />
    </>
  ),
  Heart: make(<path d="M12 20.5s-7-4.35-9.5-8.9C.86 8.15 2.5 4.5 6.2 4.5c2.1 0 3.5 1.15 5.8 3.65 2.3-2.5 3.7-3.65 5.8-3.65 3.7 0 5.34 3.65 3.7 7.1-2.5 4.55-9.5 8.9-9.5 8.9Z" />),
  Comment: make(<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5c-1.35 0-2.62-.31-3.75-.86L3 21l1.86-5.75A8.5 8.5 0 1 1 21 11.5Z" />),
  Repeat: make(<><path d="m17 2 4 4-4 4" /><path d="M3 11V9a4 4 0 0 1 4-4h14" /><path d="m7 22-4-4 4-4" /><path d="M21 13v2a4 4 0 0 1-4 4H3" /></>),
  Flag: make(<><path d="M5 3v18" /><path d="M5 4h11l-2 4 2 4H5" /></>),
  Share: make(<><circle cx="18" cy="5" r="2.5" /><circle cx="6" cy="12" r="2.5" /><circle cx="18" cy="19" r="2.5" /><path d="m8.2 10.7 7.6-4.4M8.2 13.3l7.6 4.4" /></>),
  Plus: make(<><path d="M12 5v14" /><path d="M5 12h14" /></>),
  Image: make(<><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8.5" cy="8.5" r="1.6" /><path d="m21 15-5-5-9 9" /></>),
  Mic: make(<><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10a7 7 0 0 0 14 0M12 21v-4" /></>),
  Video: make(<><rect x="2" y="6" width="14" height="12" rx="2" /><path d="m22 8-6 4 6 4Z" /></>),
  MessageDot: make(<><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5c-1.35 0-2.62-.31-3.75-.86L3 21l1.86-5.75A8.5 8.5 0 1 1 21 11.5Z" /><circle cx="8.5" cy="11.5" r="1" fill="currentColor" /><circle cx="12" cy="11.5" r="1" fill="currentColor" /><circle cx="15.5" cy="11.5" r="1" fill="currentColor" /></>),
  LogOut: make(<><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5" /><path d="M21 12H9" /></>),
  ChevronLeft: make(<path d="m15 18-6-6 6-6" />),
  Send: make(<><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></>),
  X: make(<><path d="m18 6-12 12" /><path d="m6 6 12 12" /></>),
  MoreHorizontal: make(<><circle cx="5" cy="12" r="1.3" fill="currentColor" /><circle cx="12" cy="12" r="1.3" fill="currentColor" /><circle cx="19" cy="12" r="1.3" fill="currentColor" /></>),
  Sparkle: make(<path d="M12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M6 18l2-2M16 8l2-2" />),
  Radio: make(<><circle cx="12" cy="12" r="2.2" /><path d="M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7M5.5 5.5a9 9 0 0 0 0 13M18.5 5.5a9 9 0 0 1 0 13" /></>),
  Calendar: make(<><rect x="3" y="4.5" width="18" height="16" rx="2.5" /><path d="M3 9.5h18M8 2.5v4M16 2.5v4" /></>),
  Play: make(<path d="M7 4.5v15l13-7.5Z" />),
}
