import React from 'react';
import {AbsoluteFill} from 'remotion';
import {KeywordPop} from './KeywordPop';
import {QuoteCard} from './QuoteCard';
import {MediaVisual} from './MediaVisual';
import type {AnimationOverlayProps} from './types';

export const AnimationOverlay: React.FC<AnimationOverlayProps> = (props) => <AbsoluteFill style={{backgroundColor: 'transparent'}}>
  {props.animations.map((animation) => {
    if (animation.type === 'keyword_pop') {
      return <KeywordPop key={animation.id} {...animation.parameters} start_ms={animation.start_ms} end_ms={animation.end_ms} width={props.width} height={props.height} fps={props.fps} durationInFrames={props.durationInFrames} />;
    }
    if (animation.type === 'quote_card') {
      return <QuoteCard key={animation.id} {...animation.parameters} start_ms={animation.start_ms} end_ms={animation.end_ms} width={props.width} height={props.height} />;
    }
    const asset = props.mediaAssets?.find((candidate) => candidate.asset_id === animation.parameters.asset_id);
    const placement = props.mediaPlacements?.find((candidate) => candidate.animation_id === animation.id);
    return <MediaVisual key={animation.id} {...animation.parameters} data_uri={asset?.data_uri} placement={placement} start_ms={animation.start_ms} end_ms={animation.end_ms} width={props.width} height={props.height} />;
  })}
</AbsoluteFill>;
