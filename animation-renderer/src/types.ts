export type KeywordPosition = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | 'center';

export type KeywordPopProps = {
  text: string;
  color: string;
  position: KeywordPosition;
  start_ms: number;
  end_ms: number;
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
};
