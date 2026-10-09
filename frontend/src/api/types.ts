export interface MatchEvidence {
  subject_match?: number;
  attribute_match?: number;
  bound_attribute_match?: number;
  clothing_match?: number;
  object_match?: number;
  action_match?: number;
  relationship_match?: number;
  scene_match?: number;
  CLIP?: number;
  SBERT?: number;
  BM25?: number;
  OCR?: number;
  metadata?: number;
  coordination?: number;
  contradiction?: number;
  final_score?: number;
  clip_similarity?: number;
  sbert_similarity?: number;
  bm25_score?: number;
  coordination_score?: number;
  contradiction_penalty?: number;
  vlm_score?: number;
}

export interface DocumentUnderstanding {
  document_type?: string;
  description?: string;
  extracted_title?: string;
  detected_dates?: string[];
  prizes_amounts?: string[];
  primary_objects?: string[];
  visual_concepts?: string[];
  activities?: string[];
  people_entities?: string[];
  relationships?: string[];
  confidence?: number;
}

export interface SearchResultItem {
  file_id: number;
  filename: string;
  path: string;
  extension: string;
  size_bytes: number;
  category: string;
  file_type?: string;
  created_at: string | number;
  modified_at: string | number;
  relevance_score: number;
  ai_badge?: string;
  ai_explanation?: string;
  match_evidence?: MatchEvidence;
  snippet?: string;
  extracted_text?: string;
  ocr_text?: string;
  privacy_state?: 'NORMAL' | 'PROTECTED' | 'HIDDEN';
  is_locked?: boolean;
  is_protected?: boolean;
  is_hidden?: boolean;
  blur_preview?: boolean;
  category_v4?: string;
  document_type?: string;
  capture_date?: string;
  date_source?: string;
}

export interface QueryPlanInfo {
  is_visual?: boolean;
  is_academic?: boolean;
  raw_query?: string;
  category_filter?: string | null;
  active_roles?: string[];
  subjects?: string[];
  attributes?: string[];
  clothing?: string[];
  objects?: string[];
  actions?: string[];
  scene?: string[];
  relationships?: string[];
}

export interface SearchResponse {
  query: string;
  category: string;
  total_results: number;
  unfiltered_count: number;
  elapsed_ms: number;
  summary: string;
  query_plan?: QueryPlanInfo;
  results: SearchResultItem[];
}

export interface SearchRequest {
  query: string;
  category?: string;
  formats?: string[];
  sort_by?: 'relevance' | 'date_desc' | 'date_asc' | 'size_desc' | 'size_asc' | 'name';
  limit?: number;
  save_history?: boolean;
  privacy_token?: string | null;
  privacy_scope?: 'NORMAL' | 'PRIVATE';
}

export interface FolderItem {
  id: number;
  path: string;
  added_at: string;
  last_scanned_at?: string;
  file_count: number;
}

export interface IndexingStatus {
  is_scanning: boolean;
  current_folder: string;
  current_file: string;
  current_count: number;
  total_count: number;
  failures: number;
  last_error?: string;
}

export interface SystemStatus {
  status: string;
  database_path: string;
  total_files: number;
  folder_count: number;
  category_counts?: Record<string, number>;
  ai_models: {
    dense_sbert: string;
    vision_clip: string;
    vlm_qwen: string;
  };
  indexing: IndexingStatus;
}

export interface SearchHistoryItem {
  id: number;
  query: string;
  result_count: number;
  latency_ms: number;
  summary: string;
  created_at: string;
}

export interface SavedSearchItem {
  id: number;
  query: string;
  name: string;
  created_at: string;
}

export interface Person {
  id: number;
  name: string;
  is_cluster: boolean;
  cluster_label?: string;
  notes?: string;
  avatar_file_id?: number;
  primary_face_detection_id?: number | null;
  aliases?: string[];
  file_count?: number;
  created_at: string;
  updated_at: string;
}

export interface PersonFileLink {
  id: number;
  file_id: number;
  person_id: number;
  link_type: 'face' | 'ocr' | 'filename' | 'entity';
  confidence: number;
  is_confirmed: boolean;
  notes?: string;
  path: string;
  filename: string;
  extension: string;
  size_bytes: number;
  privacy_state?: string;
  capture_date?: string;
  created_at: string;
}

export interface PersonDetails extends Person {
  files: PersonFileLink[];
  photo_count: number;
  doc_count: number;
}

export interface PrivacyStatus {
  is_configured: boolean;
  is_unlocked: boolean;
}

export interface PrivacySettings {
  protect_banking?: string;
  protect_ids?: string;
  protect_personal_info?: string;
  protect_confidential?: string;
  protected_files_visibility?: 'show' | 'hide';
  hide_protected_filename?: 'true' | 'false';
  protected_image_preview?: 'blur' | 'hide';
  protected_metadata_mode?: 'limited' | 'hide';
  face_indexing_enabled?: 'true' | 'false';
  multilingual_search_enabled?: 'true' | 'false';
  voice_search_enabled?: 'true' | 'false';
  [key: string]: string | undefined;
}

export interface StorageCategoryItem {
  name: string;
  count: number;
  bytes: number;
  color: string;
}

export interface StorageFolderItem {
  path: string;
  name: string;
  count: number;
  bytes: number;
}

export interface LargestFileItem {
  id: number;
  filename: string;
  path: string;
  size_bytes: number;
  extension: string;
  file_type?: string;
  is_protected?: boolean;
}

export interface StorageAnalytics {
  total_files: number;
  total_bytes: number;
  protected_files: number;
  protected_bytes: number;
  duplicate_files: number;
  duplicate_bytes: number;
  categories: StorageCategoryItem[];
  folders: StorageFolderItem[];
  largest_files: LargestFileItem[];
}

export interface FaceReviewItem {
  id: number;
  file_id: number;
  filename: string;
  path: string;
  box: [number, number, number, number];
  confidence: number | null;
  face_quality: number | null;
  person_id: number | null;
  person_name: string | null;
  is_cluster: boolean;
  match_confidence: number | null;
  is_confirmed: boolean;
  created_at: string;
  suggested_person_id?: number | null;
  suggested_person_name?: string | null;
  suggested_similarity?: number | null;
}

export interface FileFaceDetection {
  id: number;
  file_id: number;
  box_x: number;
  box_y: number;
  box_w: number;
  box_h: number;
  confidence: number;
  match_confidence: number | null;
  face_quality: number | null;
  landmarks_json?: string | null;
  person_id: number | null;
  person_name?: string | null;
  norm_x?: number | null;
  norm_y?: number | null;
  norm_w?: number | null;
  norm_h?: number | null;
  is_cluster?: boolean;
  link_confirmed?: boolean;
  created_at?: string;
  suggested_person_id?: number | null;
  suggested_person_name?: string | null;
  suggested_similarity?: number | null;
}

