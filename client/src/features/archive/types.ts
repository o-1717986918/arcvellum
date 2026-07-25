export type ArchiveRecord = Record<string, unknown>;

export type ArchiveFieldKind =
  | "text"
  | "markdown"
  | "number"
  | "choice"
  | "string-list"
  | "object"
  | "table";

export interface ArchiveFieldDefinition extends ArchiveRecord {
  name: string;
  label: string;
  kind: ArchiveFieldKind;
  section: string;
  required: boolean;
  help_text?: string;
  options?: string[];
}

export interface ArchiveStructuredField extends ArchiveFieldDefinition {
  defined: boolean;
  value: unknown;
}

export interface ArchiveStructuredDocument extends ArchiveRecord {
  asset_id: string;
  editor_kind: string;
  document_format: "yaml" | "json";
  source_revision: string;
  fields: ArchiveStructuredField[];
}

export interface ArchiveAssetItem extends ArchiveRecord {
  asset_id: string;
  asset_type: string;
  title: string;
  revision?: string;
  editor_kind?: string;
  supports_archive?: boolean;
  supports_create?: boolean;
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
  field_definitions?: ArchiveFieldDefinition[];
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

export interface ArchiveCreationOption extends ArchiveRecord {
  asset_type: string;
  schema_id?: string;
  editor_kind?: string;
  id_field?: string;
  fixed_id?: string;
  writable_fields?: string[];
  field_definitions?: ArchiveFieldDefinition[];
  template: string;
  available: boolean;
  unavailable_reason?: string;
}

export interface ArchiveCreationPayload {
  asset_type: string;
  local_id: string;
  content: string;
  semantic_review: "waived";
  reason: string;
  expected_impacts: string[];
}

export interface ArchiveCreationPreview extends ArchiveRecord {
  preview_digest: string;
  committable: boolean;
  asset?: ArchiveRecord;
  validation?: ArchiveRecord;
  impact?: ArchiveRecord;
}

export interface ArchiveHistory extends ArchiveRecord {
  revisions?: ArchiveRecord[];
  transactions?: ArchiveRecord[];
}
