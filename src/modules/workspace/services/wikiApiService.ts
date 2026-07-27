import { apiClient } from '@/shared/services/apiClient'
import type {
  IWikiGraphResponse,
  IWikiIngestRequest,
  IWikiIngestResponse,
  IWikiLintResponse,
  IWikiPage,
  IWikiPageCreateRequest,
  IWikiPageDetail,
  IWikiPageListResponse,
} from '@/modules/workspace/types/wiki'

export async function listWikiPages(params?: {
  folder?: string
  status?: string
  q?: string
  limit?: number
  offset?: number
}): Promise<IWikiPageListResponse> {
  const response = await apiClient.get<IWikiPageListResponse>('/wiki/pages', { params })
  return response.data
}

export async function getWikiPage(pageId: string): Promise<IWikiPageDetail> {
  const response = await apiClient.get<IWikiPageDetail>(`/wiki/pages/${pageId}`)
  return response.data
}

export async function createWikiPage(
  request: IWikiPageCreateRequest,
): Promise<IWikiPage> {
  const response = await apiClient.post<IWikiPage>('/wiki/pages', request)
  return response.data
}

export async function updateWikiPage(
  pageId: string,
  data: { title?: string; body_md?: string; status?: string },
): Promise<IWikiPage> {
  const response = await apiClient.patch<IWikiPage>(`/wiki/pages/${pageId}`, data)
  return response.data
}

export async function deleteWikiPage(pageId: string): Promise<void> {
  await apiClient.delete(`/wiki/pages/${pageId}`)
}

export async function deprecateWikiPage(pageId: string): Promise<IWikiPage> {
  const response = await apiClient.post<IWikiPage>(`/wiki/pages/${pageId}/deprecate`)
  return response.data
}

export async function ingestWiki(
  request: IWikiIngestRequest,
): Promise<IWikiIngestResponse> {
  const response = await apiClient.post<IWikiIngestResponse>('/wiki/ingest', request)
  return response.data
}

export async function getWikiGraph(params?: {
  folder?: string
}): Promise<IWikiGraphResponse> {
  const response = await apiClient.get<IWikiGraphResponse>('/wiki/graph', { params })
  return response.data
}

export async function lintWiki(): Promise<IWikiLintResponse> {
  const response = await apiClient.post<IWikiLintResponse>('/wiki/lint')
  return response.data
}
