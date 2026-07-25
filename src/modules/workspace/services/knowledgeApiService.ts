import { apiClient } from '@/shared/services/apiClient'
import type {
  IKnowledgeCreateRequest,
  IKnowledgeDocument,
  IKnowledgeDocumentDetail,
  IKnowledgeListResponse,
} from '@/modules/workspace/types/knowledge'

export async function listKnowledgeDocuments(params?: {
  limit?: number
  offset?: number
}): Promise<IKnowledgeListResponse> {
  const response = await apiClient.get<IKnowledgeListResponse>('/rag/documents', { params })
  return response.data
}

export async function getKnowledgeDocument(documentId: string): Promise<IKnowledgeDocumentDetail> {
  const response = await apiClient.get<IKnowledgeDocumentDetail>(`/rag/documents/${documentId}`)
  return response.data
}

export async function createKnowledgeDocument(
  request: IKnowledgeCreateRequest,
): Promise<IKnowledgeDocument> {
  const response = await apiClient.post<IKnowledgeDocument>('/rag/documents', request)
  return response.data
}

export async function deleteKnowledgeDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/rag/documents/${documentId}`)
}
