import React from "react";

export function ExpertCouncilIcon({ size = 40, className = "", ...props }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <circle
        cx="16"
        cy="16"
        r="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeOpacity="0.45"
      />
      <path
        d="M9 12.5C9 10.567 10.567 9 12.5 9H15.5C17.433 9 19 10.567 19 12.5C19 14.433 17.433 16 15.5 16H13.4L11.3 17.9C11.06 18.12 10.7 17.95 10.7 17.63V16C9.76 15.53 9 14.46 9 13.2V12.5Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M17 13.5C17 11.843 18.343 10.5 20 10.5H21.2C22.857 10.5 24.2 11.843 24.2 13.5C24.2 15.157 22.857 16.5 21.2 16.5H20.3V18.1C20.3 18.42 19.94 18.59 19.7 18.37L18.15 16.98"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <circle
        className="expert-dot expert-dot-1"
        cx="13"
        cy="12.8"
        r="0.9"
        fill="currentColor"
      />
      <circle
        className="expert-dot expert-dot-2"
        cx="16"
        cy="12.8"
        r="0.9"
        fill="currentColor"
      />
      <circle
        className="expert-dot expert-dot-3"
        cx="19"
        cy="13.1"
        r="0.9"
        fill="currentColor"
      />
    </svg>
  );
}

