
import React from "react";

const Svg = ({children, size=20, className="", viewBox="0 0 24 24", fill="none", stroke="currentColor", strokeWidth=1.9}) => (
  <svg className={className} width={size} height={size} viewBox={viewBox} fill={fill} stroke={stroke}
       strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

export const PlayIcon = (p) => <Svg {...p}><path d="M8 5v14l11-7z"/></Svg>;
export const MicIcon = (p) => <Svg {...p}><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6"/></Svg>;
export const BlurIcon = (p) => <Svg {...p}><rect x="4" y="4" width="16" height="16" rx="3" strokeDasharray="3 3"/><path d="M8 12h8"/></Svg>;
export const GearIcon = (p) => <Svg {...p}><path d="M12 8.2a3.8 3.8 0 1 0 0 7.6 3.8 3.8 0 0 0 0-7.6Z"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.05.05-2.83 2.83-.05-.05a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.55V21h-4v-.08A1.7 1.7 0 0 0 8.97 19.4a1.7 1.7 0 0 0-1.88.34l-.05.05-2.83-2.83.05-.05A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.52-1.03H3v-4h.08A1.7 1.7 0 0 0 4.6 8.94a1.7 1.7 0 0 0-.34-1.88l-.05-.05 2.83-2.83.05.05a1.7 1.7 0 0 0 1.88.34A1.7 1.7 0 0 0 10 3.05V3h4v.05a1.7 1.7 0 0 0 1.03 1.52 1.7 1.7 0 0 0 1.88-.34l.05-.05 2.83 2.83-.05.05a1.7 1.7 0 0 0-.34 1.88A1.7 1.7 0 0 0 20.92 10H21v4h-.08A1.7 1.7 0 0 0 19.4 15Z"/></Svg>;
export const ReviewIcon = (p) => <Svg {...p}><path d="M5 4h10l4 4v12H5z"/><path d="M15 4v4h4M8 13l2.2 2.2L16 10"/></Svg>;
export const FolderIcon = (p) => <Svg {...p}><path d="M3 7h7l2-2h9v14H3z"/></Svg>;
export const UploadIcon = (p) => <Svg {...p}><path d="M12 16V5M8 9l4-4 4 4"/><path d="M4 15v5h16v-5"/></Svg>;
export const DownloadIcon = (p) => <Svg {...p}><path d="M12 4v11M8 11l4 4 4-4"/><path d="M4 19h16"/></Svg>;
export const MoonIcon = (p) => <Svg {...p}><path d="M20 15.5A8 8 0 0 1 8.5 4 8 8 0 1 0 20 15.5Z"/></Svg>;
export const SunIcon = (p) => <Svg {...p}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42"/></Svg>;
export const BellIcon = (p) => <Svg {...p}><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 7h18s-3 0-3-7M10 19h4"/></Svg>;
export const SparkIcon = (p) => <Svg {...p}><path d="M12 2l1.5 4.5L18 8l-4.5 1.5L12 14l-1.5-4.5L6 8l4.5-1.5z"/><path d="M18.5 14l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/></Svg>;
export const BotIcon = (p) => <Svg {...p}><rect x="4" y="6" width="16" height="13" rx="3"/><path d="M9 11h.01M15 11h.01M8 15h8M12 6V3M10 3h4"/></Svg>;
export const CheckIcon = (p) => <Svg {...p}><path d="m5 12 4 4L19 6"/></Svg>;
export const ChevronRightIcon = (p) => <Svg {...p}><path d="m9 6 6 6-6 6"/></Svg>;
export const ScissorsIcon = (p) => <Svg {...p}><circle cx="6" cy="7" r="3"/><circle cx="6" cy="17" r="3"/><path d="m8.6 8.5 11.4 6.5M8.6 15.5 20 9"/></Svg>;
export const CropIcon = (p) => <Svg {...p}><path d="M7 3v14a2 2 0 0 0 2 2h12M3 7h14a2 2 0 0 1 2 2v12"/></Svg>;
export const WandIcon = (p) => <Svg {...p}><path d="m15 4 5 5L9 20l-5-5zM14 5l5 5M4 4v4M2 6h4M19 15v5M16.5 17.5h5"/></Svg>;
export const CameraIcon = (p) => <Svg {...p}><path d="M4 7h4l1.5-2h5L16 7h4v12H4z"/><circle cx="12" cy="13" r="4"/></Svg>;
export const MoreIcon = (p) => <Svg {...p}><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none"/></Svg>;
export const VolumeIcon = (p) => <Svg {...p}><path d="M5 9v6h4l5 4V5L9 9zM18 9a4 4 0 0 1 0 6"/></Svg>;
export const ExpandIcon = (p) => <Svg {...p}><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></Svg>;
export const HeadphoneIcon = (p) => <Svg {...p}><path d="M4 13a8 8 0 0 1 16 0v5h-4v-5h4M4 13v5h4v-5z"/></Svg>;
export const EyeIcon = (p) => <Svg {...p}><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.5"/></Svg>;
export const TrashIcon = (p) => <Svg {...p}><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></Svg>;
export const PlusIcon = (p) => <Svg {...p}><path d="M12 5v14M5 12h14"/></Svg>;
export const GlobeIcon = (p) => <Svg {...p}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></Svg>;
export const RefreshIcon = (p) => <Svg {...p}><path d="M20 6v5h-5M4 18v-5h5"/><path d="M6.1 9a7 7 0 0 1 11.3-2.2L20 11M4 13l2.6 4.2A7 7 0 0 0 17.9 15"/></Svg>;
export const SearchIcon = (p) => <Svg {...p}><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></Svg>;
export const FileIcon = (p) => <Svg {...p}><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 12h6M9 16h6"/></Svg>;
export const TerminalIcon = (p) => <Svg {...p}><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/></Svg>;
export const HelpIcon = (p) => <Svg {...p}><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.6 2.6 0 1 1 4.1 2.1c-1 .7-1.6 1.1-1.6 2.4M12 17h.01"/></Svg>;
export const FlagIcon = (p) => <Svg {...p}><path d="M5 21V4M5 5h11l-1 4 1 4H5"/></Svg>;
export const MessageIcon = (p) => <Svg {...p}><path d="M4 5h16v12H8l-4 4z"/></Svg>;
export const SaveIcon = (p) => <Svg {...p}><path d="M5 4h12l2 2v14H5z"/><path d="M8 4v6h8V4M8 20v-6h8v6"/></Svg>;
export const CloseIcon = (p) => <Svg {...p}><path d="m6 6 12 12M18 6 6 18"/></Svg>;

export const ExportVideoIcon = ({size=28, className=""}) => (
  <svg className={className} width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <rect x="3.5" y="6.5" width="20" height="19" rx="4" stroke="currentColor" strokeWidth="2.2"/>
    <path d="m23.5 12 5-3v14l-5-3" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round"/>
    <path d="M13.5 10.5v9M10 16l3.5 3.5L17 16" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

export const CapCutIcon = ({size=30, className=""}) => (
  <svg className={className} width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
    <path d="M7 10h26L10 30h23" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M7 30h26L10 10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

export const LogoGlyph = ({size=42}) => (
  <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
    <path d="M9 8v32h8V27l10 13h10L25 24 39 8H28L17 22V8H9Z" fill="currentColor"/>
    <path d="M31 19v10l8-5-8-5Z" fill="white"/>
  </svg>
);
