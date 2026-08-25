import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {SubtitleCue} from './types';

export const DynamicSubtitles: React.FC<{cues?: SubtitleCue[]; width: number}> = ({cues = [], width}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const nowMs = Math.round((frame / fps) * 1000);
  const cue = cues.find((candidate) => nowMs >= candidate.start_ms && nowMs < candidate.end_ms);
  if (!cue) return null;
  const localFrame = Math.max(0, frame - Math.round((cue.start_ms / 1000) * fps));
  const enter = spring({fps, frame: localFrame, config: {damping: 18, stiffness: 170, mass: 0.65}});
  const opacity = interpolate(enter, [0, 0.16, 1], [0, 1, 1], {extrapolateRight: 'clamp'});
  const translateY = interpolate(enter, [0, 1], [20, 0], {extrapolateRight: 'clamp'});
  const fontSize = Math.max(31, Math.min(72, Math.round(width / 11.5)));
  return <div style={{position: 'absolute', left: '7%', right: '7%', bottom: '6.2%', color: '#fff', fontFamily: 'KnowledgeChinese, Microsoft YaHei, PingFang SC, sans-serif', fontSize, fontWeight: 800, lineHeight: 1.26, textAlign: 'center', opacity, transform: `translateY(${translateY}px)`, textShadow: '-2px -2px 0 rgba(0,0,0,.92), 2px -2px 0 rgba(0,0,0,.92), -2px 2px 0 rgba(0,0,0,.92), 2px 2px 0 rgba(0,0,0,.92), 0 5px 11px rgba(0,0,0,0.78)', letterSpacing: '0.02em', zIndex: 20}}>
    {cue.words.map((word, index) => {
      const active = nowMs >= word.start_ms && nowMs < word.end_ms;
      const wordFrame = Math.max(0, frame - Math.round((word.start_ms / 1000) * fps));
      const pop = word.emphasized ? spring({fps, frame: wordFrame, config: {damping: 10, stiffness: 220, mass: 0.45}}) : 1;
      const emphasis = word.emphasized || active;
      return <span key={`${word.start_ms}-${index}`} style={{display: 'inline-block', margin: '0 .025em', color: word.emphasized ? '#FFD400' : '#FFFFFF', transform: `scale(${emphasis ? 0.96 + pop * 0.12 : 1})`, filter: word.emphasized ? 'drop-shadow(0 2px 0 #402600)' : undefined}}>{word.text}</span>;
    })}
  </div>;
};
