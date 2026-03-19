/**
 * AnimatedBackground.js - Animated background component for MINI-RAG frontend.
 *
 * Renders animated blobs and glow orbs for visual effect.
 */
import React from 'react';
import './AnimatedBackground.css';

const AnimatedBackground = () => {
  return (
    <div className="animated-bg-container">
      <div className="blob blob-1"></div>
      <div className="blob blob-2"></div>
      <div className="blob blob-3"></div>
      <div className="glow-orb orb-1"></div>
      <div className="glow-orb orb-2"></div>
      {/* Animated glowing lines for "vibes" */}
      <div className="vibe-line vibe-line1" style={{top: '15vh'}}></div>
      <div className="vibe-line vibe-line2"></div>
      <div className="vibe-line vibe-line3"></div>
      {/* SVG vines/circuit lines with white glow */}
      <svg className="vines-bg" width="100vw" height="100vh" viewBox="0 0 1440 900" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M 100 100 Q 200 200 300 100 T 500 100 Q 600 200 700 100" stroke="white" strokeWidth="2" opacity="0.08" filter="url(#glow)"/>
        <path d="M 200 400 Q 400 300 600 400 T 1000 400" stroke="white" strokeWidth="2" opacity="0.08" filter="url(#glow)"/>
        <path d="M 1200 200 Q 1100 300 900 200 T 600 200" stroke="white" strokeWidth="2" opacity="0.08" filter="url(#glow)"/>
        <defs>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
      </svg>
    </div>
  );
};

export default AnimatedBackground;
