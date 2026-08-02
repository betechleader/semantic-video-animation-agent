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

export type QuoteCardProps = {
  headline: string;
  body: string;
  accent_color: string;
  start_ms: number;
  end_ms: number;
  width: number;
  height: number;
};

export type RendererAnimation =
  | {id: string; type: 'keyword_pop'; template_id: 'keyword_pop_v1'; start_ms: number; end_ms: number; trigger_text: string; parameters: Pick<KeywordPopProps, 'text' | 'color' | 'position'>}
  | {id: string; type: 'quote_card'; template_id: 'quote_card_v1'; start_ms: number; end_ms: number; trigger_text: string; parameters: Pick<QuoteCardProps, 'headline' | 'body' | 'accent_color'>};

export type AnimationOverlayProps = {
  animations: RendererAnimation[];
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
};
