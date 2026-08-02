import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {QuoteCardProps} from './types';

export const QuoteCard: React.FC<QuoteCardProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const startFrame = Math.round((props.start_ms / 1000) * fps);
  const endFrame = Math.round((props.end_ms / 1000) * fps);
  if (frame < startFrame || frame >= endFrame) return null;
  const localFrame = Math.max(0, frame - startFrame);
  const progress = spring({fps, frame: localFrame, config: {damping: 18, stiffness: 150, mass: 0.8}});
  const opacity = interpolate(progress, [0, 0.2, 1], [0, 1, 1], {extrapolateRight: 'clamp'});
  const translateY = interpolate(progress, [0, 1], [48, 0], {extrapolateRight: 'clamp'});
  const headlineSize = Math.max(24, Math.min(34, Math.round(props.width / 10)));
  const bodySize = Math.max(28, Math.min(42, Math.round(props.width / 8)));
  return <div style={{position: 'absolute', left: '8%', right: '8%', bottom: '18%', opacity, transform: `translateY(${translateY}px)`}}>
    <div style={{backgroundColor: 'rgba(9, 16, 29, 0.90)', borderLeft: `12px solid ${props.accent_color}`, borderRadius: 20, boxShadow: '0 16px 36px rgba(0,0,0,0.38)', color: '#fff', fontFamily: 'Microsoft YaHei, sans-serif', padding: '30px 34px'}}>
      <div style={{color: props.accent_color, fontSize: headlineSize, fontWeight: 800, letterSpacing: 2, marginBottom: 12, overflowWrap: 'anywhere'}}>{props.headline}</div>
      <div style={{fontSize: bodySize, fontWeight: 600, lineHeight: 1.35, overflowWrap: 'anywhere'}}>{props.body}</div>
    </div>
  </div>;
};
