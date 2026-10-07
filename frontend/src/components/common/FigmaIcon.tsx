import React from 'react';

export type FigmaIconName =
  | 'analysis'
  | 'chevron'
  | 'clock'
  | 'file'
  | 'filter'
  | 'folder'
  | 'gallery'
  | 'grid'
  | 'image'
  | 'logo'
  | 'more'
  | 'plus'
  | 'search'
  | 'settings'
  | 'sort'
  | 'upload'
  | 'sparkles'
  | 'check'
  | 'trash'
  | 'external'
  | 'close'
  | 'video'
  | 'music'
  | 'code'
  | 'archive';

const iconPaths: Record<FigmaIconName, React.ReactNode> = {
  analysis: (
    <>
      <path d="M5 20V10M12 20V4M19 20v-7" />
      <path d="M3 20h18" opacity=".35" />
    </>
  ),
  chevron: <path d="m9 18 6-6-6-6" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  file: (
    <>
      <path d="M6 2.8h8l4 4V21H6z" />
      <path d="M14 3v5h4M9 12h6M9 15h6M9 18h4" />
    </>
  ),
  filter: <path d="M4 6h16M7 12h10M10 18h4" />,
  folder: (
    <path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h4l2 2H19a2 2 0 0 1 2 2v8.5a2.5 2.5 0 0 1-2.5 2h-13A2.5 2.5 0 0 1 3 17V7.5Z" />
  ),
  gallery: (
    <>
      <rect x="3" y="5" width="15" height="15" rx="2.5" />
      <path d="m5 17 4-4 3 3 2-2 4 4M14 9h.01" />
      <path d="M8 5V3h13v14h-3" />
    </>
  ),
  grid: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="2" />
      <rect x="14" y="3" width="7" height="7" rx="2" />
      <rect x="3" y="14" width="7" height="7" rx="2" />
      <rect x="14" y="14" width="7" height="7" rx="2" />
    </>
  ),
  image: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <circle cx="9" cy="9" r="2" />
      <path d="m21 15-5-5L5 21" />
    </>
  ),
  logo: (
    <>
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h4l2 2H19a2 2 0 0 1 2 2v10.5a2.5 2.5 0 0 1-2.5 2h-12A2.5 2.5 0 0 1 4 17V5.5Z" />
      <path d="m9 11 3 3 3-3M12 8v6" />
    </>
  ),
  more: (
    <>
      <circle cx="5" cy="12" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="19" cy="12" r="1.2" fill="currentColor" stroke="none" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  search: (
    <>
      <circle cx="10.8" cy="10.8" r="6.8" />
      <path d="m20 20-4.4-4.4" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
    </>
  ),
  sort: <path d="M8 6h12M8 12h8M8 18h4M4 4v16m0 0-2-2m2 2 2-2" />,
  upload: (
    <>
      <path d="M12 16V4M7 9l5-5 5 5" />
      <path d="M5 14v5h14v-5" />
    </>
  ),
  sparkles: (
    <>
      <path d="m12 3 1.9 4.8L18.7 9.7l-4.8 1.9L12 16.4l-1.9-4.8L5.3 9.7l4.8-1.9L12 3z" />
      <path d="M19 16l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2z" />
    </>
  ),
  check: <path d="M20 6 9 17l-5-5" />,
  trash: (
    <>
      <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M10 11v6M14 11v6" />
    </>
  ),
  external: (
    <>
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <path d="M15 3h6v6M10 14 21 3" />
    </>
  ),
  close: <path d="M18 6 6 18M6 6l12 12" />,
  video: (
    <>
      <rect x="2" y="4" width="15" height="16" rx="3" />
      <path d="m17 9 5-3v12l-5-3z" />
    </>
  ),
  music: (
    <>
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="16" r="3" />
    </>
  ),
  code: (
    <>
      <polyline points="16 18 22 12 16 6" />
      <polyline points="8 6 2 12 8 18" />
    </>
  ),
  archive: (
    <>
      <polyline points="21 8 21 21 3 21 3 8" />
      <rect x="1" y="3" width="22" height="5" />
      <line x1="10" y1="12" x2="14" y2="12" />
    </>
  ),
};

export const FigmaIcon: React.FC<{ name: FigmaIconName; size?: number; className?: string }> = ({
  name,
  size = 20,
  className = '',
}) => {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {iconPaths[name] || iconPaths.file}
    </svg>
  );
};
