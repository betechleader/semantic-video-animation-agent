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

export type MediaVisualProps = {
  asset_id: string;
  title: string;
  theme: 'book' | 'learning' | 'wellbeing' | 'business' | 'technology';
  accent_color: string;
  start_ms: number;
  end_ms: number;
  width: number;
  height: number;
  data_uri?: string;
};

export type RendererAnimation =
  | {id: string; type: 'keyword_pop'; template_id: 'keyword_pop_v1'; start_ms: number; end_ms: number; trigger_text: string; parameters: Pick<KeywordPopProps, 'text' | 'color' | 'position'>}
  | {id: string; type: 'quote_card'; template_id: 'quote_card_v1'; start_ms: number; end_ms: number; trigger_text: string; parameters: Pick<QuoteCardProps, 'headline' | 'body' | 'accent_color'>}
  | {id: string; type: 'media_visual'; template_id: 'media_visual_v1'; start_ms: number; end_ms: number; trigger_text: string; parameters: Pick<MediaVisualProps, 'asset_id' | 'title' | 'theme' | 'accent_color'>};

export type RendererMediaAsset = {asset_id: string; data_uri: string};

export type MediaPlacement = {
  animation_id: string;
  corner: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | null;
  scale: number;
  skipped: boolean;
  reason: 'safe_corner' | 'no_safe_area';
};

export type AnimationOverlayProps = {
  animations: RendererAnimation[];
  mediaAssets?: RendererMediaAsset[];
  mediaPlacements?: MediaPlacement[];
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
};
