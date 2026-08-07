import React from 'react';
import {Img, OffthreadVideo, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {MediaPlacement, MediaVisualProps} from './types';

type PositionedMediaVisualProps = MediaVisualProps & {placement?: MediaPlacement};

export const MediaVisual: React.FC<PositionedMediaVisualProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const startFrame = Math.round((props.start_ms / 1000) * fps);
  const endFrame = Math.round((props.end_ms / 1000) * fps);
  if (!props.enabled || frame < startFrame || frame >= endFrame || props.placement?.skipped) return null;
  const localFrame = Math.max(0, frame - startFrame);
  const progress = spring({fps, frame: localFrame, config: {damping: 17, stiffness: 140, mass: 0.8}});
  const opacity = interpolate(progress, [0, 0.2, 1], [0, 1, 1], {extrapolateRight: 'clamp'});
  const scale = interpolate(progress, [0, 1], [0.92, 1], {extrapolateRight: 'clamp'});
  const isFullScreen = props.display_mode === 'full_screen' || props.placement?.reason === 'full_screen';
  const media = props.data_uri
    ? props.mime_type?.startsWith('video/')
      ? <OffthreadVideo src={props.data_uri} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      : <Img src={props.data_uri} style={{width: '100%', height: '100%', objectFit: isFullScreen ? 'contain' : 'cover'}} />
    : null;
  if (isFullScreen) {
    return <div style={{position: 'absolute', inset: 0, opacity, transform: `scale(${scale})`, transformOrigin: 'center', overflow: 'hidden', zIndex: 7, background: '#111827'}}>
      {media}
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(0,0,0,.06) 40%, rgba(0,0,0,.76) 100%)'}} />
      <div style={{position: 'absolute', top: '5%', left: '6%', color: '#fff', fontFamily: 'KnowledgeChinese, Microsoft YaHei, sans-serif', fontSize: Math.max(18, Math.round(props.width / 28)), fontWeight: 800, textShadow: '0 3px 9px rgba(0,0,0,.75)', borderLeft: `6px solid ${props.accent_color}`, paddingLeft: 10}}>{props.title}</div>
    </div>;
  }
  const size = Math.max(112, Math.min(300, Math.round(props.width * 0.34)));
  const placement = props.placement ?? {corner: 'top-left', scale: 1};
  const corner = placement.corner ?? 'top-left';
  const isRight = corner.endsWith('right');
  const isBottom = corner.startsWith('bottom');
  const positionedScale = scale * placement.scale;
  return <div style={{position: 'absolute', left: isRight ? undefined : '5%', right: isRight ? '5%' : undefined, top: isBottom ? undefined : '5%', bottom: isBottom ? '5%' : undefined, width: size, height: Math.round(size * 1.28), opacity, transform: `scale(${positionedScale})`, transformOrigin: `${isBottom ? 'bottom' : 'top'} ${isRight ? 'right' : 'left'}`, overflow: 'hidden', borderRadius: Math.max(14, Math.round(size / 13)), boxShadow: '0 16px 30px rgba(0,0,0,0.42)', border: '2px solid rgba(255,255,255,.75)', background: '#172033', zIndex: 8}}>
    {media}
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, padding: '14% 9% 8%', background: 'linear-gradient(transparent, rgba(0,0,0,.80))', color: '#fff', fontFamily: 'KnowledgeChinese, Microsoft YaHei, sans-serif', fontSize: Math.max(15, Math.round(size / 12)), fontWeight: 800, lineHeight: 1.2}}>{props.title}</div>
  </div>;
};
