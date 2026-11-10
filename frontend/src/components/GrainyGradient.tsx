import React from 'react';

/**
 * Atmosfera Mineral Obsidian (Inteligentte Lab — Dual Prestige Precision).
 * Substitui orbes neon saturados por iluminação zenital fria de baixíssima intensidade
 * e micro-granulação óptica de estúdio para profundidade sem fadiga visual.
 */
export const GrainyGradient: React.FC = () => {
  return (
    <div className="ambient-backdrop" aria-hidden="true">
      <div className="ambient-zenith-ai" />
      <div className="ambient-zenith-closer" />
      <svg className="ambient-grain-svg" xmlns="http://www.w3.org/2000/svg">
        <filter id="obsidianMicroGrain">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.82"
            numOctaves={3}
            stitchTiles="stitch"
          />
        </filter>
        <rect width="100%" height="100%" filter="url(#obsidianMicroGrain)" />
      </svg>
    </div>
  );
};
