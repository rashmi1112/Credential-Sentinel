"use client";

/**
 * "Senty" — the credential-sentinel mascot, flat vector style (solid colors, no
 * gradients). Floats gently and blinks. Pure inline SVG, no assets.
 */
export function SentinelMascot({ size = 180 }: { size?: number }) {
  return (
    <div
      className="animate-float select-none"
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg viewBox="0 0 200 200" width={size} height={size}>
        {/* flat ground shadow */}
        <ellipse cx="100" cy="176" rx="52" ry="8" fill="#4F46E5" opacity="0.12" />

        {/* antenna */}
        <line x1="100" y1="36" x2="100" y2="16" stroke="#A5B4FC" strokeWidth="4" strokeLinecap="round" />
        <circle cx="100" cy="13" r="6" fill="#F59E0B">
          <animate attributeName="opacity" values="1;0.5;1" dur="2.2s" repeatCount="indefinite" />
        </circle>

        {/* shield body — solid */}
        <path
          d="M100 36 C 70 48, 50 50, 40 52 C 40 112, 60 152, 100 172 C 140 152, 160 112, 160 52 C 150 50, 130 48, 100 36 Z"
          fill="#6366F1"
        />
        {/* inner band */}
        <path
          d="M100 50 C 78 60, 62 61, 56 62 C 57 110, 74 142, 100 156 C 126 142, 143 110, 144 62 C 138 61, 122 60, 100 50 Z"
          fill="#EEF1FF"
        />
        {/* face panel — solid */}
        <circle cx="100" cy="100" r="30" fill="#ffffff" />
        <circle cx="100" cy="100" r="30" fill="none" stroke="#C7D2FE" strokeWidth="2" />

        {/* eyes (blink by squashing ry) */}
        <ellipse cx="88" cy="98" rx="6.5" ry="6.5" fill="#3730A3">
          <animate attributeName="ry" values="6.5;6.5;0.6;6.5" keyTimes="0;0.9;0.95;1" dur="4s" repeatCount="indefinite" />
        </ellipse>
        <ellipse cx="112" cy="98" rx="6.5" ry="6.5" fill="#3730A3">
          <animate attributeName="ry" values="6.5;6.5;0.6;6.5" keyTimes="0;0.9;0.95;1" dur="4s" repeatCount="indefinite" />
        </ellipse>

        {/* cheeks — flat soft pink */}
        <circle cx="78" cy="110" r="5" fill="#FBCFE8" />
        <circle cx="122" cy="110" r="5" fill="#FBCFE8" />
        {/* smile */}
        <path d="M90 110 Q100 119 110 110" fill="none" stroke="#3730A3" strokeWidth="3" strokeLinecap="round" />

        {/* check badge — solid */}
        <g>
          <animateTransform attributeName="transform" type="translate" values="0 0; 0 -3; 0 0" dur="3s" repeatCount="indefinite" />
          <circle cx="138" cy="132" r="14" fill="#10B981" stroke="#ffffff" strokeWidth="3" />
          <path d="M131 132 l5 5 l9 -11" fill="none" stroke="#ffffff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      </svg>
    </div>
  );
}
