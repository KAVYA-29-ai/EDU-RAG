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
    </div>
  );
};

export default AnimatedBackground;
