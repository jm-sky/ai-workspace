export type WikiPageStatus = 'active' | 'deprecated'

export type WikiFolder = 'raw' | 'inbox' | 'entities' | 'concepts' | 'summaries' | 'meta'

export interface IWikiPage {
  id: string
  folder: WikiFolder
  slug: string
  title: string
  bodyMd: string
  frontmatter?: Record<string, unknown> | null
  sourceUrl?: string | null
  status: WikiPageStatus
  immutable: boolean
  documentId?: string | null
  createdAt: string
  updatedAt: string
}

export interface IWikiLink {
  id: string
  fromPageId: string
  toPageId?: string | null
  toSlug: string
  linkText?: string | null
  fromSlug?: string | null
  fromTitle?: string | null
  fromFolder?: string | null
  toTitle?: string | null
  toFolder?: string | null
}

export interface IWikiPageDetail extends IWikiPage {
  outgoingLinks: IWikiLink[]
  incomingLinks: IWikiLink[]
}

export interface IWikiPageListResponse {
  pages: IWikiPage[]
  total: number
}

export interface IWikiPageCreateRequest {
  folder: WikiFolder
  slug?: string | null
  title: string
  body_md: string
  frontmatter?: Record<string, unknown> | null
  source_url?: string | null
}

export interface IWikiIngestRequest {
  content: string
  source_url?: string | null
  title?: string | null
}

export interface IWikiIngestResponse {
  rawPageId: string
  summaryPageId: string
  rippledPages: string[]
  truncated: boolean
}

export interface IWikiGraphNode {
  id: string
  slug: string
  title: string
  folder: WikiFolder
  status: WikiPageStatus
}

export interface IWikiGraphEdge {
  fromId: string
  toId?: string | null
  toSlug: string
}

export interface IWikiGraphResponse {
  nodes: IWikiGraphNode[]
  edges: IWikiGraphEdge[]
}

export interface IWikiLintIssue {
  type: string
  pageId?: string | null
  slug?: string | null
  detail: string
}

export interface IWikiLintResponse {
  issues: IWikiLintIssue[]
  fixesApplied: number
}
