"use client";

import { useEffect, useState, type ReactNode } from "react";

/**
 * Renders an AI-generated illustration from `public/illustrations/...` if it
 * exists, otherwise renders `fallback`. Drop the PNG in and it appears on the
 * next load — no code change needed.
 *
 * We preload the image and only swap in the <img> once it has *successfully*
 * loaded. That avoids the broken-image flash you'd get from an <img onError>
 * when the file is absent (the 404 can fire before React attaches its handler).
 */
export function DropInImage({
  src,
  alt,
  size,
  className,
  fallback,
}: {
  src: string;
  alt: string;
  size: number;
  className?: string;
  fallback: ReactNode;
}) {
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    const img = new window.Image();
    img.onload = () => active && setLoaded(true);
    img.onerror = () => active && setLoaded(false);
    img.src = src;
    return () => {
      active = false;
    };
  }, [src]);

  if (!loaded) return <>{fallback}</>;

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      className={className}
      style={{ width: size, height: size, objectFit: "contain" }}
    />
  );
}
