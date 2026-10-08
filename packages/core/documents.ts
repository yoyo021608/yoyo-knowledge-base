import { ApiError } from "./auth";
import { reportUnauthorized } from "./auth-events";
import { buildApiUrl } from "./client";

export type SourceType = "note" | "markdown" | "web" | "file";
export type SearchMode = "keyword" | "full_text" | "vector" | "hybrid";

export interface DocumentSummary {
  id: string;
  topicId: string | null;
  title: string;
  status: "active" | "archived";
  isFavorite: boolean;
  currentVersion: number;
  currentVersionId: string;
  indexStatus: string;
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export interface SourceSnapshot {
  versionId: string;
  content: string;
  sourceType: SourceType;
  sourceUrl: string | null;
  title: string;
  capturedAt: string;
}

export interface DocumentVersion {
  id: string;
  documentId: string;
  version: number;
  titleSnapshot: string;
  contentSnapshot: string;
  indexStatus: string;
  indexError: string | null;
  source: SourceSnapshot;
  createdAt: string;
}

export interface DocumentDetail {
  document: DocumentSummary;
  version: DocumentVersion;
}

export interface DocumentInput {
  title?: string;
  content?: string;
  sourceType: Exclude<SourceType, "file">;
  sourceUrl?: string;
  sourceTitle?: string;
  topicId?: string;
  tags?: string[];
}

export interface DocumentUpdateInput {
  title: string;
  content: string;
  topicId?: string;
  tags?: string[];
  sourceUrl?: string;
}

export interface ImportResult {
  documentId: string;
  versionId: string;
  indexStatus: string;
}

export interface StoredFilePayload {
  name: string;
  contentBase64: string;
  contentType: string;
}

export interface ExportDownload {
  content: Uint8Array;
  mediaType: string;
}

export interface ImportJob {
  id: string;
  status: string;
  totalCount: number;
  successCount: number;
  failureCount: number;
}

export interface ImportItem {
  id: string;
  inputIndex: number;
  status: string;
  documentId: string | null;
  errorMessage: string | null;
}

export interface BatchJobResult {
  job: ImportJob;
  items: ImportItem[];
}

export interface Topic {
  id: string;
  name: string;
  description: string;
}

export interface Tag {
  id: string;
  name: string;
}

export interface DocumentRelation {
  id: string;
  sourceDocumentId: string;
  targetDocumentId: string;
  relationType: string;
  createdAt: string;
}

export interface SearchHit {
  documentId: string;
  versionId: string;
  title: string;
  contentSnippet: string;
  chunkId: string;
  sourceUrl: string | null;
  score: number;
}

/** 当前版本中能够定位回片段的知识点。 */
export interface KnowledgePoint {
  id: string;
  chunkId: string;
  position: number;
  content: string;
  entityIds: string[];
}

/** 多个知识点可以共同引用的明确实体。 */
export interface KnowledgeEntity {
  id: string;
  name: string;
  entityType: string;
}

/** 带知识点证据位置的实体关系。 */
export interface KnowledgeRelation {
  id: string;
  pointId: string;
  sourceEntityId: string;
  targetEntityId: string;
  relationType: string;
}

/** 文档当前版本的知识结构响应。 */
export interface DocumentKnowledge {
  documentId: string;
  versionId: string;
  points: KnowledgePoint[];
  entities: KnowledgeEntity[];
  relations: KnowledgeRelation[];
}

/** 文档列表支持的组合筛选条件。 */
export interface DocumentListFilters {
  keyword?: string;
  topicId?: string;
  tag?: string;
  sourceType?: SourceType;
  indexStatus?: string;
  status?: "active" | "archived";
  isFavorite?: boolean;
}

interface ErrorWireResponse {
  detail?: string;
}

type JsonBody = Record<string, unknown> | unknown[];

/** documents 的统一认证请求入口，视图不直接了解 HTTP 错误格式。 */
async function request<T>(
  baseUrl: string,
  accessToken: string,
  path: string,
  method = "GET",
  body?: JsonBody,
): Promise<T> {
  const response = await fetch(buildApiUrl(baseUrl, path), {
    method,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    if (response.status === 401) reportUnauthorized();
    let message = `请求失败：HTTP ${response.status}`;
    try {
      const error = (await response.json()) as ErrorWireResponse;
      if (typeof error.detail === "string") message = error.detail;
    } catch {
      // 非 JSON 错误继续使用状态码提示。
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function documentOf(raw: Record<string, unknown>): DocumentSummary {
  return {
    id: String(raw.id),
    topicId: (raw.topic_id as string | null) ?? null,
    title: String(raw.title),
    status: raw.status as DocumentSummary["status"],
    isFavorite: Boolean(raw.is_favorite),
    currentVersion: Number(raw.current_version),
    currentVersionId: String(raw.current_version_id),
    indexStatus: String(raw.index_status),
    tags: raw.tags as string[],
    createdAt: String(raw.created_at),
    updatedAt: String(raw.updated_at),
  };
}

function sourceOf(raw: Record<string, unknown>): SourceSnapshot {
  return {
    versionId: String(raw.version_id),
    content: String(raw.content),
    sourceType: raw.source_type as SourceType,
    sourceUrl: (raw.source_url as string | null) ?? null,
    title: String(raw.title),
    capturedAt: String(raw.captured_at),
  };
}

function versionOf(raw: Record<string, unknown>): DocumentVersion {
  return {
    id: String(raw.id),
    documentId: String(raw.document_id),
    version: Number(raw.version),
    titleSnapshot: String(raw.title_snapshot),
    contentSnapshot: String(raw.content_snapshot),
    indexStatus: String(raw.index_status),
    indexError: (raw.index_error as string | null) ?? null,
    source: sourceOf(raw.source as Record<string, unknown>),
    createdAt: String(raw.created_at),
  };
}

function inputBody(input: DocumentInput): Record<string, unknown> {
  return {
    title: input.title || null,
    content: input.content || null,
    source_type: input.sourceType,
    source_url: input.sourceUrl || null,
    source_title: input.sourceTitle || null,
    topic_id: input.topicId || null,
    tags: input.tags ?? [],
  };
}

export async function importDocument(
  baseUrl: string,
  accessToken: string,
  input: DocumentInput,
): Promise<ImportResult> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    "/api/documents/import",
    "POST",
    inputBody(input),
  );
  return {
    documentId: String(raw.document_id),
    versionId: String(raw.version_id),
    indexStatus: String(raw.index_status),
  };
}

export async function importDocumentFile(
  baseUrl: string,
  accessToken: string,
  file: StoredFilePayload,
  options: { title?: string; topicId?: string; tags?: string[] } = {},
): Promise<ImportResult> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    "/api/documents/import-file",
    "POST",
    {
      name: file.name,
      content_base64: file.contentBase64,
      content_type: file.contentType,
      title: options.title || null,
      topic_id: options.topicId || null,
      tags: options.tags ?? [],
    },
  );
  return {
    documentId: String(raw.document_id),
    versionId: String(raw.version_id),
    indexStatus: String(raw.index_status),
  };
}

function batchOf(raw: Record<string, unknown>): BatchJobResult {
  const job = raw.job as Record<string, unknown>;
  return {
    job: {
      id: String(job.id),
      status: String(job.status),
      totalCount: Number(job.total_count),
      successCount: Number(job.success_count),
      failureCount: Number(job.failure_count),
    },
    items: (raw.items as Record<string, unknown>[]).map((item) => ({
      id: String(item.id),
      inputIndex: Number(item.input_index),
      status: String(item.status),
      documentId: (item.document_id as string | null) ?? null,
      errorMessage: (item.error_message as string | null) ?? null,
    })),
  };
}

export async function createBatchImport(
  baseUrl: string,
  accessToken: string,
  inputs: DocumentInput[],
): Promise<BatchJobResult> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    "/api/document-import-jobs",
    "POST",
    { items: inputs.map(inputBody) },
  );
  return batchOf(raw);
}

export async function retryBatchImport(
  baseUrl: string,
  accessToken: string,
  jobId: string,
): Promise<BatchJobResult> {
  return batchOf(
    await request<Record<string, unknown>>(
      baseUrl,
      accessToken,
      `/api/document-import-jobs/${encodeURIComponent(jobId)}/retry`,
      "POST",
    ),
  );
}

export async function listDocuments(
  baseUrl: string,
  accessToken: string,
  filters: DocumentListFilters = {},
): Promise<DocumentSummary[]> {
  const parts: string[] = [];
  if (filters.keyword) parts.push(`keyword=${encodeURIComponent(filters.keyword)}`);
  if (filters.topicId) parts.push(`topic_id=${encodeURIComponent(filters.topicId)}`);
  if (filters.tag) parts.push(`tag=${encodeURIComponent(filters.tag)}`);
  if (filters.sourceType) parts.push(`source_type=${encodeURIComponent(filters.sourceType)}`);
  if (filters.indexStatus) parts.push(`index_status=${encodeURIComponent(filters.indexStatus)}`);
  if (filters.status) parts.push(`status=${encodeURIComponent(filters.status)}`);
  if (filters.isFavorite !== undefined) parts.push(`is_favorite=${filters.isFavorite}`);
  const suffix = parts.length ? `?${parts.join("&")}` : "";
  const raw = await request<Record<string, unknown>[]>(
    baseUrl,
    accessToken,
    `/api/documents${suffix}`,
  );
  return raw.map(documentOf);
}

export async function getDocument(
  baseUrl: string,
  accessToken: string,
  documentId: string,
): Promise<DocumentDetail> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}`,
  );
  return {
    document: documentOf(raw.document as Record<string, unknown>),
    version: versionOf(raw.version as Record<string, unknown>),
  };
}

export async function listDocumentVersions(
  baseUrl: string,
  accessToken: string,
  documentId: string,
): Promise<DocumentVersion[]> {
  const raw = await request<Record<string, unknown>[]>(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}/versions`,
  );
  return raw.map(versionOf);
}

export async function getDocumentVersion(
  baseUrl: string,
  accessToken: string,
  documentId: string,
  versionId: string,
): Promise<DocumentVersion> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}/versions/${encodeURIComponent(versionId)}`,
  );
  return versionOf(raw);
}

export async function getDocumentKnowledge(
  baseUrl: string,
  accessToken: string,
  documentId: string,
): Promise<DocumentKnowledge> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}/knowledge`,
  );
  return {
    documentId: String(raw.document_id),
    versionId: String(raw.version_id),
    points: (raw.points as Record<string, unknown>[]).map((point) => ({
      id: String(point.id),
      chunkId: String(point.chunk_id),
      position: Number(point.position),
      content: String(point.content),
      entityIds: point.entity_ids as string[],
    })),
    entities: (raw.entities as Record<string, unknown>[]).map((entity) => ({
      id: String(entity.id),
      name: String(entity.name),
      entityType: String(entity.entity_type),
    })),
    relations: (raw.relations as Record<string, unknown>[]).map((relation) => ({
      id: String(relation.id),
      pointId: String(relation.point_id),
      sourceEntityId: String(relation.source_entity_id),
      targetEntityId: String(relation.target_entity_id),
      relationType: String(relation.relation_type),
    })),
  };
}

export async function updateDocument(
  baseUrl: string,
  accessToken: string,
  documentId: string,
  input: DocumentUpdateInput,
): Promise<DocumentVersion> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}`,
    "PUT",
    {
      title: input.title,
      content: input.content,
      topic_id: input.topicId || null,
      tags: input.tags ?? [],
      source_url: input.sourceUrl || null,
    },
  );
  return versionOf(raw);
}

export function archiveDocument(
  baseUrl: string,
  accessToken: string,
  documentId: string,
): Promise<void> {
  return request(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}/archive`,
    "POST",
  );
}

export function restoreDocument(
  baseUrl: string,
  accessToken: string,
  documentId: string,
): Promise<void> {
  return request(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}/restore`,
    "POST",
  );
}

export async function retryDocumentIndex(
  baseUrl: string,
  accessToken: string,
  documentId: string,
): Promise<string> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}/index/retry`,
    "POST",
  );
  return String(raw.status);
}

export function deleteDocument(
  baseUrl: string,
  accessToken: string,
  documentId: string,
): Promise<void> {
  return request(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}`,
    "DELETE",
  );
}

export function setDocumentFavorite(
  baseUrl: string,
  accessToken: string,
  documentId: string,
  favorite: boolean,
): Promise<void> {
  return request(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}/favorite`,
    "PUT",
    { favorite },
  );
}

export async function searchDocuments(
  baseUrl: string,
  accessToken: string,
  text: string,
  mode: SearchMode,
): Promise<SearchHit[]> {
  const raw = await request<Record<string, unknown>[]>(
    baseUrl,
    accessToken,
    "/api/documents/search",
    "POST",
    { text, mode, limit: 12 },
  );
  return raw.map((hit) => ({
    documentId: String(hit.document_id),
    versionId: String(hit.version_id),
    title: String(hit.title),
    contentSnippet: String(hit.content_snippet),
    chunkId: String(hit.chunk_id),
    sourceUrl: (hit.source_url as string | null) ?? null,
    score: Number(hit.score),
  }));
}

export async function listTopics(
  baseUrl: string,
  accessToken: string,
): Promise<Topic[]> {
  const raw = await request<Record<string, unknown>[]>(baseUrl, accessToken, "/api/topics");
  return raw.map((topic) => ({
    id: String(topic.id),
    name: String(topic.name),
    description: String(topic.description),
  }));
}

export async function createTopic(
  baseUrl: string,
  accessToken: string,
  name: string,
  description: string,
): Promise<Topic> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    "/api/topics",
    "POST",
    { name, description },
  );
  return { id: String(raw.id), name: String(raw.name), description: String(raw.description) };
}

export async function updateTopic(
  baseUrl: string,
  accessToken: string,
  topicId: string,
  name: string,
  description: string,
): Promise<Topic> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/topics/${encodeURIComponent(topicId)}`,
    "PUT",
    { name, description },
  );
  return { id: String(raw.id), name: String(raw.name), description: String(raw.description) };
}

export function deleteTopic(
  baseUrl: string,
  accessToken: string,
  topicId: string,
): Promise<void> {
  return request(baseUrl, accessToken, `/api/topics/${encodeURIComponent(topicId)}`, "DELETE");
}

export async function listTags(
  baseUrl: string,
  accessToken: string,
): Promise<Tag[]> {
  const raw = await request<Record<string, unknown>[]>(baseUrl, accessToken, "/api/tags");
  return raw.map((tag) => ({ id: String(tag.id), name: String(tag.name) }));
}

export async function createTag(
  baseUrl: string,
  accessToken: string,
  name: string,
): Promise<Tag> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    "/api/tags",
    "POST",
    { name },
  );
  return { id: String(raw.id), name: String(raw.name) };
}

export async function renameTag(
  baseUrl: string,
  accessToken: string,
  tagId: string,
  name: string,
): Promise<Tag> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/tags/${encodeURIComponent(tagId)}`,
    "PUT",
    { name },
  );
  return { id: String(raw.id), name: String(raw.name) };
}

export function deleteTag(
  baseUrl: string,
  accessToken: string,
  tagId: string,
): Promise<void> {
  return request(baseUrl, accessToken, `/api/tags/${encodeURIComponent(tagId)}`, "DELETE");
}

export async function listDocumentRelations(
  baseUrl: string,
  accessToken: string,
  documentId: string,
): Promise<DocumentRelation[]> {
  const raw = await request<Record<string, unknown>[]>(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}/relations`,
  );
  return raw.map((relation) => ({
    id: String(relation.id),
    sourceDocumentId: String(relation.source_document_id),
    targetDocumentId: String(relation.target_document_id),
    relationType: String(relation.relation_type),
    createdAt: String(relation.created_at),
  }));
}

export async function createDocumentRelation(
  baseUrl: string,
  accessToken: string,
  documentId: string,
  targetDocumentId: string,
  relationType: string,
): Promise<DocumentRelation> {
  const raw = await request<Record<string, unknown>>(
    baseUrl,
    accessToken,
    `/api/documents/${encodeURIComponent(documentId)}/relations`,
    "POST",
    { target_document_id: targetDocumentId, relation_type: relationType },
  );
  return {
    id: String(raw.id),
    sourceDocumentId: String(raw.source_document_id),
    targetDocumentId: String(raw.target_document_id),
    relationType: String(raw.relation_type),
    createdAt: String(raw.created_at),
  };
}

export function deleteDocumentRelation(
  baseUrl: string,
  accessToken: string,
  relationId: string,
): Promise<void> {
  return request(
    baseUrl,
    accessToken,
    `/api/document-relations/${encodeURIComponent(relationId)}`,
    "DELETE",
  );
}

export async function downloadDocuments(
  baseUrl: string,
  accessToken: string,
  format: "markdown" | "json",
  filters: { topicId?: string; tag?: string; documentIds?: string[] } = {},
): Promise<ExportDownload> {
  const query = new URLSearchParams({ format });
  if (filters.topicId) query.set("topic_id", filters.topicId);
  if (filters.tag) query.set("tag", filters.tag);
  for (const documentId of filters.documentIds ?? []) query.append("document_id", documentId);
  const response = await fetch(buildApiUrl(baseUrl, `/api/documents/export?${query.toString()}`), {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    if (response.status === 401) reportUnauthorized();
    throw new ApiError(`导出失败：HTTP ${response.status}`, response.status);
  }
  return {
    content: new Uint8Array(await response.arrayBuffer()),
    mediaType: response.headers.get("Content-Type") ?? "application/octet-stream",
  };
}
