import type { LineageNode, LineageEdge } from '../types'

export const FOLDER_VIEW_THRESHOLD = 100

export interface FolderMeta {
  id: string
  name: string
  folder: string
  modelCount: number
  sourceCount: number
  totalCount: number
  nodeIds: string[]
}

export interface AggregationResult {
  folderNodes: LineageNode[]
  folderEdges: LineageEdge[]
  folderMetas: Map<string, FolderMeta>
  nodeToFolder: Map<string, string>
}

export function aggregateByFolder(
  nodes: LineageNode[],
  edges: LineageEdge[],
): AggregationResult {
  // Group nodes by folder. Sources without a folder use their source_name prefix.
  const folderGroups = new Map<string, LineageNode[]>()
  for (const node of nodes) {
    let folder = node.folder
    if (!folder && node.resource_type === 'source') {
      // Derive folder from source unique_id: "source.project.source_name.table" → "sources/source_name"
      const parts = node.id.split('.')
      folder = parts.length >= 3 ? `sources/${parts[2]}` : 'sources'
    }
    folder = folder || '_ungrouped'
    const group = folderGroups.get(folder)
    if (group) {
      group.push(node)
    } else {
      folderGroups.set(folder, [node])
    }
  }

  // Create folder metadata
  const folderMetas = new Map<string, FolderMeta>()
  const nodeToFolder = new Map<string, string>()

  for (const [folder, group] of folderGroups) {
    const id = `folder:${folder}`
    const modelCount = group.filter(n => n.resource_type === 'model').length
    const sourceCount = group.filter(n => n.resource_type === 'source').length

    folderMetas.set(id, {
      id,
      name: folder.split('/').pop() ?? folder,
      folder,
      modelCount,
      sourceCount,
      totalCount: group.length,
      nodeIds: group.map(n => n.id),
    })

    for (const node of group) {
      nodeToFolder.set(node.id, id)
    }
  }

  // Compute meta-edges (deduplicated cross-folder edges)
  const edgeSet = new Set<string>()
  const folderEdges: LineageEdge[] = []

  for (const edge of edges) {
    const srcFolder = nodeToFolder.get(edge.source)
    const tgtFolder = nodeToFolder.get(edge.target)
    if (srcFolder && tgtFolder && srcFolder !== tgtFolder) {
      const key = `${srcFolder}__${tgtFolder}`
      if (!edgeSet.has(key)) {
        edgeSet.add(key)
        folderEdges.push({ source: srcFolder, target: tgtFolder })
      }
    }
  }

  // Create pseudo LineageNode entries for each folder
  const folderNodes: LineageNode[] = [...folderMetas.values()].map((meta) => ({
    id: meta.id,
    name: meta.name,
    resource_type: (meta.modelCount >= meta.sourceCount ? 'model' : 'source') as LineageNode['resource_type'],
    materialization: '',
    schema: '',
    test_status: 'none' as const,
    has_description: false,
    folder: meta.folder,
    tags: [],
  }))

  return { folderNodes, folderEdges, folderMetas, nodeToFolder }
}

export interface MixedGraphResult {
  nodes: LineageNode[]
  edges: LineageEdge[]
  folderData: Record<string, { modelCount: number; sourceCount: number }>
}

export function buildMixedGraph(
  originalNodes: LineageNode[],
  originalEdges: LineageEdge[],
  folderMetas: Map<string, FolderMeta>,
  nodeToFolder: Map<string, string>,
  expandedFolders: Set<string>,
): MixedGraphResult {
  const nodes: LineageNode[] = []
  const folderData: Record<string, { modelCount: number; sourceCount: number }> = {}
  const expandedNodeIds = new Set<string>()

  // Build a lookup for original nodes
  const nodeById = new Map<string, LineageNode>()
  for (const n of originalNodes) {
    nodeById.set(n.id, n)
  }

  for (const [folderId, meta] of folderMetas) {
    if (expandedFolders.has(folderId)) {
      // Expanded: include individual nodes
      for (const nodeId of meta.nodeIds) {
        const node = nodeById.get(nodeId)
        if (node) {
          nodes.push(node)
          expandedNodeIds.add(nodeId)
        }
      }
    } else {
      // Collapsed: include folder super-node
      nodes.push({
        id: folderId,
        name: meta.name,
        resource_type: (meta.modelCount >= meta.sourceCount ? 'model' : 'source') as LineageNode['resource_type'],
        materialization: '',
        schema: '',
        test_status: 'none',
        has_description: false,
        folder: meta.folder,
        tags: [],
      })
      folderData[folderId] = {
        modelCount: meta.modelCount,
        sourceCount: meta.sourceCount,
      }
    }
  }

  // Build edges for mixed graph (collapsed folders → redirect to folder id)
  const edgeSet = new Set<string>()
  const edges: LineageEdge[] = []

  for (const edge of originalEdges) {
    const srcExpanded = expandedNodeIds.has(edge.source)
    const tgtExpanded = expandedNodeIds.has(edge.target)
    const srcFolder = nodeToFolder.get(edge.source)
    const tgtFolder = nodeToFolder.get(edge.target)

    const source = srcExpanded ? edge.source : (srcFolder ?? edge.source)
    const target = tgtExpanded ? edge.target : (tgtFolder ?? edge.target)

    // Skip intra-folder edges when folder is collapsed
    if (source === target) continue

    const key = `${source}__${target}`
    if (!edgeSet.has(key)) {
      edgeSet.add(key)
      edges.push({ source, target })
    }
  }

  return { nodes, edges, folderData }
}

export function shouldUseFolderView(nodeCount: number): boolean {
  return nodeCount > FOLDER_VIEW_THRESHOLD
}
