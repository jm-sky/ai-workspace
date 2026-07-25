export type KnowledgeDocumentStatus = 'pending' | 'ready' | 'failed'

export interface IKnowledgeDocument {
  id: string
  title: string
  sourceType: string
  sourceRef?: string | null
  metadata?: Record<string, unknown> | null
  chunkCount: number
  status: KnowledgeDocumentStatus
  error?: string | null
  createdAt: string
  updatedAt: string
}

export interface IKnowledgeChunk {
  id: string
  chunkIndex: number
  content: string
  tokenEstimate?: number | null
}

export interface IKnowledgeDocumentDetail extends IKnowledgeDocument {
  chunks: IKnowledgeChunk[]
}

export interface IKnowledgeListResponse {
  documents: IKnowledgeDocument[]
  total: number
}

export interface IKnowledgeCreateRequest {
  title: string
  content: string
}
