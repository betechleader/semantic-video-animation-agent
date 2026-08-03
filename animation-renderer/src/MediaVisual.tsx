import React from 'react';
import {Img, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {MediaPlacement, MediaVisualProps} from './types';

type PositionedMediaVisualProps = MediaVisualProps & {placement?: MediaPlacement};

export const MediaVisual: React.FC<PositionedMediaVisualProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const startFrame = Math.round((props.start_ms / 1000) * fps);
  const endFrame = Math.round((props.end_ms / 1000) * fps);
  if (frame < startFrame || frame >= endFrame || props.placement?.skipped) return null;
  const localFrame = Math.max(0, frame - startFrame);
  const progress = spring({fps, frame: localFrame, config: {damping: 17, stiffness: 140, mass: 0.8}});
  const opacity = interpolate(progress, [0, 0.2, 1], [0, 1, 1], {extrapolateRight: 'clamp'});
  const scale = interpolate(progress, [0, 1], [0.92, 1], {extrapolateRight: 'clamp'});
  const size = Math.max(96, Math.min(168, Math.round(props.width * 0.27)));
  const placement = props.placement ?? {corner: 'top-left', scale: 1};
  const corner = placement.corner ?? 'top-left';
  const isRight = corner.endsWith('right');
  const isBottom = corner.startsWith('bottom');
  const positionedScale = scale * placement.scale;
  return <div style={{position: 'absolute', left: isRight ? undefined : '5%', right: isRight ? '5%' : undefined, top: isBottom ? undefined : '5%', bottom: isBottom ? '5%' : undefined, width: size, height: Math.round(size * 1.2), opacity, transform: `scale(${positionedScale})`, transformOrigin: `${isBottom ? 'bottom' : 'top'} ${isRight ? 'right' : 'left'}`}}>
    {props.data_uri ? <Img src={props.data_uri} style={{width: '100%', height: '100%', objectFit: 'contain', filter: 'drop-shadow(0 16px 24px rgba(0,0,0,0.35))'}} /> : null}
  </div>;
};
