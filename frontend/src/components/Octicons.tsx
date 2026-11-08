import React from "react";

interface IconProps {
  size?: number;
  className?: string;
  style?: React.CSSProperties;
  color?: string;
}

export function IssueOpenedIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" />
      <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z" />
    </svg>
  );
}

export function StarIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z" />
    </svg>
  );
}

export function SyncIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M1.705 8.005a.75.75 0 0 1 .834.656 5.5 5.5 0 0 0 9.592 2.97l-1.204-1.204a.25.25 0 0 1 .177-.427h3.646a.25.25 0 0 1 .25.25v3.646a.25.25 0 0 1-.427.177l-1.38-1.38A7.002 7.002 0 0 1 1.05 8.84a.75.75 0 0 1 .656-.834ZM8 2.5a5.487 5.487 0 0 0-4.131 1.869l1.204 1.204A.25.25 0 0 1 4.896 6H1.25A.25.25 0 0 1 1 5.75V2.104a.25.25 0 0 1 .427-.177l1.38 1.38A7.002 7.002 0 0 1 14.95 7.16a.75.75 0 0 1-1.49.178A5.5 5.5 0 0 0 8 2.5Z" />
    </svg>
  );
}

export function GearIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M8 0a8.2 8.2 0 0 1 .701.031C9.444.095 9.99.645 10.16 1.29l.288 1.107c.377.098.733.25 1.062.448l1.01-.52c.604-.312 1.35-.14 1.77.413a8.092 8.092 0 0 1 1.127 1.95c.294.615.11 1.353-.432 1.758l-.907.677c.07.382.07.776 0 1.158l.907.677c.542.405.726 1.143.432 1.758a8.092 8.092 0 0 1-1.127 1.95c-.42.553-1.166.725-1.77.413l-1.01-.52c-.329.198-.685.35-1.062.448l-.288 1.107c-.17.645-.716 1.195-1.459 1.259A8.2 8.2 0 0 1 8 16a8.2 8.2 0 0 1-.701-.031c-.743-.064-1.289-.614-1.459-1.259l-.288-1.107a5.994 5.994 0 0 1-1.062-.448l-1.01.52c-.604.312-1.35.14-1.77-.413a8.092 8.092 0 0 1-1.127-1.95c-.294-.615-.11-1.353.432-1.758l.907-.677a5.982 5.982 0 0 1 0-1.158l-.907-.677c-.542-.405-.726-1.143-.432-1.758a8.092 8.092 0 0 1 1.127-1.95c.42-.553 1.166-.725 1.77-.413l1.01.52c.329-.198.685-.35 1.062-.448l.288-1.107c.17-.645.716-1.195 1.459-1.259A8.2 8.2 0 0 1 8 0Zm0 10.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />
    </svg>
  );
}

export function SunIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M8 12a4 4 0 1 1 0-8 4 4 0 0 1 0 8Zm0-1.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Zm5.657-8.157a.75.75 0 0 1 0 1.06l-.707.708a.75.75 0 0 1-1.06-1.06l.707-.708a.75.75 0 0 1 1.06 0Zm-9.193 9.192a.75.75 0 0 1 0 1.06l-.707.708a.75.75 0 0 1-1.06-1.06l.707-.708a.75.75 0 0 1 1.06 0ZM8 0a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1A.75.75 0 0 1 8 0Zm0 13.5a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1a.75.75 0 0 1 .75-.75Zm7.25-6.25a.75.75 0 0 1 0 1.5h-1a.75.75 0 0 1 0-1.5h1ZM2.5 7.25a.75.75 0 0 1 0 1.5h-1a.75.75 0 0 1 0-1.5h1Zm10.157 5.657a.75.75 0 0 1-1.06 0l-.708-.707a.75.75 0 0 1 1.06-1.06l.708.707a.75.75 0 0 1 0 1.06ZM4.464 3.404a.75.75 0 0 1-1.06 0l-.708-.707a.75.75 0 0 1 1.06-1.06l.708.707a.75.75 0 0 1 0 1.06Z" />
    </svg>
  );
}

export function MoonIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M9.598 1.591a.749.749 0 0 1 .785-.175 7.001 7.001 0 1 1-8.967 8.967.75.75 0 0 1 .961-.96 5.5 5.5 0 0 0 7.046-7.046.75.75 0 0 1 .175-.786Zm1.616 1.945a7 7 0 0 1-7.67 7.67 5.509 5.509 0 0 0 7.67-7.67Z" />
    </svg>
  );
}

export function CheckIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z" />
    </svg>
  );
}

export function CopyIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z" />
      <path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z" />
    </svg>
  );
}

export function AlertIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M6.457 1.047c.659-1.234 2.427-1.234 3.086 0l6.082 11.378A1.75 1.75 0 0 1 14.082 15H1.918a1.75 1.75 0 0 1-1.543-2.575Zm1.763.707a.25.25 0 0 0-.44 0L1.698 13.132a.25.25 0 0 0 .22.368h12.164a.25.25 0 0 0 .22-.368Zm.53 3.996v2.5a.75.75 0 0 1-1.5 0v-2.5a.75.75 0 0 1 1.5 0ZM9 11a1 1 0 1 1-2 0 1 1 0 0 1 2 0Z" />
    </svg>
  );
}

export function InfoIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm8-6.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM6.5 7.75A.75.75 0 0 1 7.25 7h1a.75.75 0 0 1 .75.75v2.75h.25a.75.75 0 0 1 0 1.5h-2a.75.75 0 0 1 0-1.5h.25v-2h-.25a.75.75 0 0 1-.75-.75ZM8 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z" />
    </svg>
  );
}

export function XIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.749.749 0 0 1 1.275.326.749.749 0 0 1-.215.734L9.06 8l3.22 3.22a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215L8 9.06l-3.22 3.22a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z" />
    </svg>
  );
}

export function TrashIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M11 1.75V3h2.25a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1 0-1.5H5V1.75C5 .784 5.784 0 6.75 0h2.5C10.216 0 11 .784 11 1.75ZM4.496 6.675l.66 6.6a1.75 1.75 0 0 0 1.744 1.725h2.2c.928 0 1.69-.724 1.744-1.725l.66-6.6a.75.75 0 0 0-1.492-.15l-.66 6.6a.25.25 0 0 1-.248.25h-2.2a.25.25 0 0 1-.248-.25l-.66-6.6a.75.75 0 0 0-1.492.15ZM6.5 1.75V3h3V1.75a.25.25 0 0 0-.25-.25h-2.5a.25.25 0 0 0-.25.25Z" />
    </svg>
  );
}

export function GitPullRequestIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.5 5.404V4.75a.75.75 0 0 1 1.5 0v3.086a2.25 2.25 0 1 1-1.5 0V6.657L7.707 4.864l-.53.53a.75.75 0 0 1-1.06-1.06l1.06-1.26Z" />
    </svg>
  );
}

export function GitMergeIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M5 3.254V3.25a2.25 2.25 0 1 1 3.445 1.912 4.497 4.497 0 0 1-.945 1.696v4.896a2.25 2.25 0 1 1-1.5 0V8.25a2.998 2.998 0 0 0 1.25-2.45c0-.44-.095-.858-.266-1.233A2.25 2.25 0 0 1 5 3.254Z" />
    </svg>
  );
}

export function GitPullRequestClosedIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm10 7.5a2.25 2.25 0 1 1 3 2.122v.378a.75.75 0 0 1-1.5 0v-.378a2.25 2.25 0 0 1-1.5-2.122Zm-4.22-6.53a.75.75 0 0 1 1.06 0L10.5 6.38l2.16-2.16a.75.75 0 1 1 1.06 1.06L11.56 7.44l2.16 2.16a.75.75 0 1 1-1.06 1.06L10.5 8.5l-2.16 2.16a.75.75 0 0 1-1.06-1.06l2.16-2.16L7.28 5.28a.75.75 0 0 1 0-1.06Z" />
    </svg>
  );
}

export function RepoIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h6.5a.25.25 0 0 1 .25.25v1.5a.25.25 0 0 1-.25.25h-6.5a.25.25 0 0 1-.25-.25Z" />
    </svg>
  );
}

export function MenuIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M1 2.75A.75.75 0 0 1 1.75 2h12.5a.75.75 0 0 1 0 1.5H1.75A.75.75 0 0 1 1 2.75Zm0 5A.75.75 0 0 1 1.75 7h12.5a.75.75 0 0 1 0 1.5H1.75A.75.75 0 0 1 1 7.75Zm0 5a.75.75 0 0 1 .75-.75h12.5a.75.75 0 0 1 0 1.5H1.75a.75.75 0 0 1-.75-.75Z" />
    </svg>
  );
}

export function SearchIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 4.499 0 0 0 11.5 7Z" />
    </svg>
  );
}

export function BookIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M0 1.75A.75.75 0 0 1 .75 1h4.253c1.227 0 2.317.59 3 1.501A3.743 3.743 0 0 1 11.006 1h4.244a.75.75 0 0 1 .75.75v10.5a.75.75 0 0 1-.75.75h-4.244a2.25 2.25 0 0 0-1.506.572V14.5a.75.75 0 0 1-1.5 0v-.928A2.25 2.25 0 0 0 6.506 13H1.75a.75.75 0 0 1-.75-.75V1.75Zm1.5.75v8.5h3.506a3.75 3.75 0 0 1 1.5.312V3.25a2.25 2.25 0 0 0-1.5-.5H1.5Zm13 0h-3.506a2.25 2.25 0 0 0-1.5.5v8.062a3.75 3.75 0 0 1 1.5-.312h3.506V2.5Z" />
    </svg>
  );
}

export function PulseIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="M6 2a.75.75 0 0 1 .696.471L10 10.731l1.304-3.26A.75.75 0 0 1 12 7h3.25a.75.75 0 0 1 0 1.5H12.45l-1.754 4.385a.75.75 0 0 1-1.392 0L6 4.269l-1.304 3.26A.75.75 0 0 1 4 8H.75a.75.75 0 0 1 0-1.5H3.55l1.754-4.385A.75.75 0 0 1 6 2Z" />
    </svg>
  );
}

export function TriangleDownIcon({ size = 16, style, className, color }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 16 16"
      version="1.1"
      width={size}
      fill="currentColor"
      style={{ color, ...style }}
      className={className}
    >
      <path d="m4.427 7.427 3.396 3.396a.25.25 0 0 0 .354 0l3.396-3.396A.25.25 0 0 0 11.396 7H4.604a.25.25 0 0 0-.177.427Z" />
    </svg>
  );
}
