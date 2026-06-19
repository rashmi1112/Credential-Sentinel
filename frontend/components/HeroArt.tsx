"use client";

import { useState } from "react";

export function HeroArt({ size = 420 }: { size?: number }) {
  const [pointer, setPointer] = useState({ x: 50, y: 50 });

  return (
    <div
      aria-label="Animated credential coverage map"
      role="img"
      className="credential-art group relative isolate aspect-square w-full max-w-[min(92vw,var(--art-size))] overflow-hidden rounded-none"
      style={
        {
          "--art-size": `${size}px`,
          "--pointer-x": `${pointer.x}%`,
          "--pointer-y": `${pointer.y}%`,
        } as React.CSSProperties
      }
      onPointerMove={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        setPointer({
          x: ((event.clientX - rect.left) / rect.width) * 100,
          y: ((event.clientY - rect.top) / rect.height) * 100,
        });
      }}
      onPointerLeave={() => setPointer({ x: 50, y: 50 })}
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_var(--pointer-x)_var(--pointer-y),rgba(212,255,71,0.28),transparent_26%),radial-gradient(circle_at_50%_45%,rgba(255,255,255,0.12),transparent_38%)]" />
      <div className="absolute inset-[8%] rounded-full border border-white/10" />
      <div className="absolute inset-[18%] rounded-full border border-lime-300/20" />
      <div className="absolute left-1/2 top-1/2 size-[34%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-lime-300/50 bg-black/35 shadow-[0_0_80px_rgba(212,255,71,0.18)] backdrop-blur-sm">
        <div className="absolute inset-[18%] rounded-full bg-lime-300 shadow-[0_0_38px_rgba(212,255,71,0.72)]" />
        <div className="absolute left-1/2 top-1/2 size-[35%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-black" />
      </div>

      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 520 520" fill="none">
        <defs>
          <linearGradient id="signalGradient" x1="80" x2="440" y1="90" y2="430">
            <stop stopColor="#D4FF47" />
            <stop offset="0.58" stopColor="#9DFFB5" />
            <stop offset="1" stopColor="#FFFFFF" stopOpacity="0.72" />
          </linearGradient>
        </defs>
        <g className="credential-art__orbit credential-art__orbit--slow">
          <path d="M94 274C132 126 311 78 426 176" stroke="url(#signalGradient)" strokeWidth="2" strokeLinecap="round" strokeDasharray="6 18" />
          <path d="M112 360C202 456 363 441 428 322" stroke="white" strokeOpacity=".28" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="3 16" />
        </g>
        <g className="credential-art__orbit credential-art__orbit--fast">
          <path d="M144 142C263 86 413 148 432 282" stroke="#D4FF47" strokeOpacity=".82" strokeWidth="2" strokeLinecap="round" strokeDasharray="10 18" />
          <path d="M90 248C132 399 308 465 432 354" stroke="#FFFFFF" strokeOpacity=".36" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="4 18" />
        </g>
        {[
          [96, 266, "UNM"],
          [158, 134, "TLS"],
          [422, 180, "CI"],
          [436, 322, "API"],
          [142, 384, "VM"],
        ].map(([cx, cy, label]) => (
          <g key={label} className="credential-art__node">
            <circle cx={cx} cy={cy} r="25" fill="#0D0F0B" stroke="#D4FF47" strokeOpacity=".64" />
            <circle cx={cx} cy={cy} r="5" fill="#D4FF47" />
            <text x={cx} y={Number(cy) + 43} fill="white" fillOpacity=".72" fontSize="14" textAnchor="middle" fontFamily="monospace">
              {label}
            </text>
          </g>
        ))}
      </svg>

      <div className="credential-art__scan absolute left-[10%] top-0 h-full w-px bg-lime-300/70 shadow-[0_0_30px_rgba(212,255,71,0.85)]" />
      <div className="absolute bottom-[12%] left-[12%] right-[12%] flex items-center justify-between border-t border-white/10 pt-4 font-mono text-[0.62rem] uppercase text-white/54">
        <span>coverage</span>
        <span className="text-lime-300">live</span>
        <span>human gate</span>
      </div>
    </div>
  );
}
