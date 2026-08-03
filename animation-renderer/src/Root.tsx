import React from 'react';
import {AbsoluteFill, Composition} from 'remotion';
import {AnimationOverlay} from './AnimationOverlay';
import {KeywordPop} from './KeywordPop';
import {QuoteCard} from './QuoteCard';
import {MediaVisual} from './MediaVisual';
import type {AnimationOverlayProps, KeywordPopProps, QuoteCardProps, MediaVisualProps} from './types';

const keywordDefaults: KeywordPopProps = {text: 'Structured output', color: '#FFD400', position: 'top-right', start_ms: 1000, end_ms: 2500, width: 1080, height: 1920, fps: 30, durationInFrames: 120};
const quoteDefaults: QuoteCardProps = {headline: 'Key takeaway', body: 'Structured output makes video planning reliable.', accent_color: '#6EE7B7', start_ms: 2500, end_ms: 4000, width: 1080, height: 1920};
const mediaDefaults: MediaVisualProps = {asset_id: 'media_demo', title: 'Book topic', theme: 'book', accent_color: '#A78BFA', start_ms: 1000, end_ms: 3000, width: 1080, height: 1920};
const overlayDefaults: AnimationOverlayProps = {animations: [
  {id: 'animation_001', type: 'keyword_pop', template_id: 'keyword_pop_v1', start_ms: 1000, end_ms: 2500, trigger_text: keywordDefaults.text, parameters: {text: keywordDefaults.text, color: keywordDefaults.color, position: keywordDefaults.position}},
  {id: 'animation_002', type: 'quote_card', template_id: 'quote_card_v1', start_ms: 2500, end_ms: 4000, trigger_text: quoteDefaults.headline, parameters: {headline: quoteDefaults.headline, body: quoteDefaults.body, accent_color: quoteDefaults.accent_color}},
], width: 1080, height: 1920, fps: 30, durationInFrames: 120};

export const RemotionRoot: React.FC = () => <>
  <Composition id="KeywordPop" component={() => <AbsoluteFill style={{backgroundColor: 'transparent'}}><KeywordPop {...keywordDefaults} /></AbsoluteFill>} width={1080} height={1920} fps={30} durationInFrames={120} defaultProps={keywordDefaults} calculateMetadata={({props}) => ({width: props.width, height: props.height, fps: props.fps, durationInFrames: props.durationInFrames})} />
  <Composition id="QuoteCard" component={QuoteCard} width={1080} height={1920} fps={30} durationInFrames={120} defaultProps={quoteDefaults} />
  <Composition id="MediaVisual" component={MediaVisual} width={1080} height={1920} fps={30} durationInFrames={120} defaultProps={mediaDefaults} />
  <Composition id="AnimationOverlay" component={AnimationOverlay} width={1080} height={1920} fps={30} durationInFrames={120} defaultProps={overlayDefaults} calculateMetadata={({props}) => ({width: props.width, height: props.height, fps: props.fps, durationInFrames: props.durationInFrames})} />
</>;
