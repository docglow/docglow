import { Markdown } from '../Markdown'

interface ColumnDescriptionProps {
  description: string
  isGenerated?: boolean
}

/** Column description cell: rendered as Markdown, like model descriptions. */
export function ColumnDescription({ description, isGenerated = false }: ColumnDescriptionProps) {
  return (
    <div className="text-sm column-description">
      <Markdown content={description} />
      {isGenerated && (
        <span className="text-[9px] text-[var(--text-muted)] opacity-60 font-medium uppercase">auto</span>
      )}
    </div>
  )
}
