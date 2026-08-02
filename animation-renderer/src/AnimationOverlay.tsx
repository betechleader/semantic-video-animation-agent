import React from 'react';
import {AbsoluteFill} from 'remotion';
import {KeywordPop} from './KeywordPop';
import {QuoteCard} from './QuoteCard';
import type {AnimationOverlayProps} from './types';

export const AnimationOverlay: React.FC<AnimationOverlayProps> = (props) => <AbsoluteFill style={{backgroundColor: 'transparent'}}>
  {props.animations.map((animation) => {
    if (animation.type === 'keyword_pop') {
      return <KeywordPop key={animation.id} {...animation.parameters} start_ms={animation.start_ms} end_ms={animation.end_ms} width={props.width} height={props.height} fps={props.fps} durationInFrames={props.durationInFrames} />;
    }
    return <QuoteCard key={animation.id} {...animation.parameters} start_ms={animation.start_ms} end_ms={animation.end_ms} width={props.width} height={props.height} />;
  })}
</AbsoluteFill>;
