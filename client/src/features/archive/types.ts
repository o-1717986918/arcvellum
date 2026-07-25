export type ArchiveRecord = Record<string, unknown>;

export interface ArchiveAssetItem extends ArchiveRecord {
  asset_id: string;
  asset_type: string;
  title: string;
  revision?: string;
  editor_kind?: string;
  supports_archive?: boolean;
  supports_promotion?: boolean;
}

export interface ArchiveAssetGroup extends ArchiveRecord {
  asset_type: string;
  items: ArchiveAssetItem[];
  count?: number;
}

export interface ArchiveAssetDetail extends ArchiveAssetItem {
  content: string;
  revision: string;
  media_type?: string;
  source_path?: string;
  schema_id?: string;
  writable_fields?: string[];
  reference_fields?: string[];
}

export interface ArchiveCandidate extends ArchiveRecord {
  candidate_id: string;
  asset_type?: string;
  title?: string;
  current_step?: string;
  content?: string;
  can_promote?: boolean;
  promoted?: boolean;
  preview_digest?: string;
  promotion_blockers?: string[];
  steps?: Array<Record<string, unknown>>;
  impact?: Record<string, unknown>;
  review?: Record<string, unknown>;
  approval?: Record<string, unknown>;
  receipt?: Record<string, unknown>;
}

export interface RecycleEntry extends ArchiveRecord {
  entry_id: string;
  asset_id: string;
  asset_type?: string;
  title?: string;
  status?: string;
  reason?: string;
}
