import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {InformationGraphicProps} from './types';

export const KnowledgeInfographic: React.FC<InformationGraphicProps> = (props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const startFrame = Math.round((props.start_ms / 1000) * fps);
  const endFrame = Math.round((props.end_ms / 1000) * fps);
  if (frame < startFrame || frame >= endFrame) return null;
  const localFrame = frame - startFrame;
  const enter = spring({fps, frame: localFrame, config: {damping: 18, stiffness: 150, mass: 0.8}});
  const opacity = interpolate(enter, [0, .2, 1], [0, 1, 1], {extrapolateRight: 'clamp'});
  const y = interpolate(enter, [0, 1], [-36, 0], {extrapolateRight: 'clamp'});
  const titleSize = Math.max(28, Math.min(52, Math.round(props.width / 12)));
  const bodySize = Math.max(21, Math.min(35, Math.round(props.width / 17)));
  const commonCard: React.CSSProperties = {background: 'rgba(10, 17, 30, .88)', border: '1px solid rgba(255,255,255,.2)', boxShadow: '0 18px 42px rgba(0,0,0,.38)', borderRadius: 22, padding: '16px 18px', color: '#fff'};
  const content = props.variant === 'number_list'
    ? <div style={{display: 'grid', gap: 10}}>{props.items.map((item, index) => <div key={item} style={{...commonCard, display: 'flex', alignItems: 'center', gap: 14}}><span style={{color: props.accent_color, fontSize: bodySize * 1.4, fontWeight: 900, minWidth: '1.2em'}}>0{index + 1}</span><span>{item}</span></div>)}</div>
    : props.variant === 'comparison'
      ? <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10}}>{props.items.slice(0, 2).map((item, index) => <div key={item} style={{...commonCard, borderTop: `7px solid ${index === 0 ? '#94A3B8' : props.accent_color}`, minHeight: 86, display: 'grid', placeItems: 'center', textAlign: 'center'}}><span style={{fontSize: bodySize}}>{item}</span></div>)}</div>
      : <div style={{display: 'flex', alignItems: 'stretch', gap: 7}}>{props.items.map((item, index) => <React.Fragment key={item}><div style={{...commonCard, flex: 1, display: 'grid', placeItems: 'center', textAlign: 'center', minHeight: 90}}><span style={{color: props.accent_color, fontSize: bodySize * .8, fontWeight: 900}}>{index + 1}</span><span style={{fontSize: bodySize}}>{item}</span></div>{index < props.items.length - 1 ? <div style={{alignSelf: 'center', color: props.accent_color, fontSize: bodySize * 1.2}}>→</div> : null}</React.Fragment>)}</div>;
  return <div style={{position: 'absolute', left: '7%', right: '7%', top: '9%', opacity, transform: `translateY(${y}px)`, zIndex: 12}}>
    <div style={{color: '#fff', fontFamily: 'KnowledgeChinese, Microsoft YaHei, PingFang SC, sans-serif', fontSize: titleSize, fontWeight: 900, lineHeight: 1.15, marginBottom: 12, textShadow: '-1px -1px 0 rgba(0,0,0,.55), 1px 1px 0 rgba(0,0,0,.55), 0 4px 12px rgba(0,0,0,.6)'}}><span style={{color: props.accent_color}}>● </span>{props.headline}</div>
    {content}
  </div>;
};
