import React from 'react';
import {AbsoluteFill, Composition} from 'remotion';
import {KeywordPop} from './KeywordPop';
import type {KeywordPopProps} from './types';

const defaults: KeywordPopProps = {text: '结构化输出', color: '#FFD400', position: 'top-right', start_ms: 1000, end_ms: 3000, width: 1080, height: 1920, fps: 30, durationInFrames: 90};

export const RemotionRoot: React.FC = () => <Composition
  id="KeywordPop"
  component={() => <AbsoluteFill style={{backgroundColor: 'transparent'}}><KeywordPop {...defaults} /></AbsoluteFill>}
  width={1080}
  height={1920}
  fps={30}
  durationInFrames={90}
  defaultProps={defaults}
  calculateMetadata={({props}) => ({width: props.width, height: props.height, fps: props.fps, durationInFrames: props.durationInFrames})}
/>;
