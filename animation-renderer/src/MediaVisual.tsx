import React from 'react';
import {Img, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {MediaVisualProps} from './types';

export const MediaVisual: React.FC<MediaVisualProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const startFrame = Math.round((props.start_ms / 1000) * fps);
  const endFrame = Math.round((props.end_ms / 1000) * fps);
  if (frame < startFrame || frame >= endFrame) return null;
  const localFrame = Math.max(0, frame - startFrame);
  const progress = spring({fps, frame: localFrame, config: {damping: 17, stiffness: 140, mass: 0.8}});
  const opacity = interpolate(progress, [0, 0.2, 1], [0, 1, 1], {extrapolateRight: 'clamp'});
  const scale = interpolate(progress, [0, 1], [0.92, 1], {extrapolateRight: 'clamp'});
  const size = Math.max(96, Math.min(168, Math.round(props.width * 0.27)));
  return <div style={{position: 'absolute', left: '5%', top: '5%', width: size, height: Math.round(size * 1.2), opacity, transform: `scale(${scale})`, transformOrigin: 'top left'}}>
    {props.data_uri ? <Img src={props.data_uri} style={{width: '100%', height: '100%', objectFit: 'contain', filter: 'drop-shadow(0 16px 24px rgba(0,0,0,0.35))'}} /> : null}
  </div>;
};
