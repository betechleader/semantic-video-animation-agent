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
  theme: 'book' | 'factory' | 'product' | 'money' | 'learning' | 'people' | 'place' | 'concept' | 'wellbeing' | 'business' | 'technology';
  accent_color: string;
  search_query: string;
  desired_asset_kind: 'external_image' | 'external_video';
  display_mode: 'side_card' | 'full_screen';
  selected_candidate_id?: string | null;
  enabled: boolean;
  start_ms: number;
  end_ms: number;
  width: number;
  height: number;
  data_uri?: string;
  mime_type?: string;
};

export type InformationGraphicProps = {
  variant: 'number_list' | 'comparison' | 'flow';
  headline: string;
  items: string[];
  accent_color: string;
  start_ms: number;
  end_ms: number;
  width: number;
  height: number;
};

export type RendererAnimation =
  | {id: string; type: 'keyword_pop'; template_id: 'keyword_pop_v1'; start_ms: number; end_ms: number; trigger_text: string; parameters: Pick<KeywordPopProps, 'text' | 'color' | 'position'>}
  | {id: string; type: 'quote_card'; template_id: 'quote_card_v1'; start_ms: number; end_ms: number; trigger_text: string; parameters: Pick<QuoteCardProps, 'headline' | 'body' | 'accent_color'>}
  | {id: string; type: 'media_visual'; template_id: 'media_visual_v1'; start_ms: number; end_ms: number; trigger_text: string; parameters: Pick<MediaVisualProps, 'asset_id' | 'title' | 'theme' | 'accent_color' | 'search_query' | 'desired_asset_kind' | 'display_mode' | 'selected_candidate_id' | 'enabled'>}
  | {id: string; type: 'info_graphic'; template_id: 'knowledge_infographic_v1'; start_ms: number; end_ms: number; trigger_text: string; parameters: Pick<InformationGraphicProps, 'variant' | 'headline' | 'items' | 'accent_color'>};

export type RendererMediaAsset = {asset_id: string; data_uri: string; mime_type: string};

export type MediaPlacement = {
  animation_id: string;
  corner: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | null;
  scale: number;
  skipped: boolean;
  reason: 'safe_corner' | 'no_safe_area' | 'full_screen';
};

export type SubtitleWord = {text: string; start_ms: number; end_ms: number; emphasized: boolean};
export type SubtitleCue = {start_ms: number; end_ms: number; words: SubtitleWord[]};

export type AnimationOverlayProps = {
  animations: RendererAnimation[];
  mediaAssets?: RendererMediaAsset[];
  mediaPlacements?: MediaPlacement[];
  subtitleCues?: SubtitleCue[];
  fontDataUri?: string;
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
};
