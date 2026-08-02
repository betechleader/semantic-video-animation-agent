import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {KeywordPopProps} from './types';

const positions: Record<KeywordPopProps['position'], React.CSSProperties> = {
  'top-left': {left: '8%', top: '10%'},
  'top-right': {right: '8%', top: '10%'},
  'bottom-left': {bottom: '10%', left: '8%'},
  'bottom-right': {bottom: '10%', right: '8%'},
  center: {left: '50%', top: '50%', transform: 'translate(-50%, -50%)'},
};

export const KeywordPop: React.FC<KeywordPopProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const startFrame = Math.round((props.start_ms / 1000) * fps);
  const endFrame = Math.round((props.end_ms / 1000) * fps);
  const visible = frame >= startFrame && frame < endFrame;
  const localFrame = Math.max(0, frame - startFrame);
  const scale = spring({fps, frame: localFrame, config: {damping: 12, stiffness: 180, mass: 0.6}});
  const opacity = interpolate(scale, [0, 0.25, 1], [0, 1, 1], {extrapolateRight: 'clamp'});

  if (!visible) return null;
  const fontSize = Math.max(28, Math.min(72, Math.round(props.width / 10)));
  return <div style={{position: 'absolute', ...positions[props.position], opacity, transform: `${positions[props.position].transform ?? ''} scale(${scale})`}}>
    <div style={{backgroundColor: props.color, borderRadius: 24, boxShadow: '0 12px 28px rgba(0,0,0,0.35)', color: '#111', fontFamily: 'Microsoft YaHei, sans-serif', fontSize, fontWeight: 800, padding: '22px 34px', whiteSpace: 'nowrap'}}>
      {props.text}
    </div>
  </div>;
};
