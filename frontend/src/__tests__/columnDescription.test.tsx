// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ColumnDescription } from '../components/models/ColumnDescription'

/* No @testing-library/react in this repo, so render to static markup. */

describe('ColumnDescription', () => {
  it('renders a Markdown bullet list as a list', () => {
    const html = renderToStaticMarkup(
      <ColumnDescription description={'Part type:\n\n- `A`: assembly\n- `B`: bought'} />,
    )
    expect(html).toContain('<ul>')
    expect(html).toContain('<li><code>A</code>: assembly</li>')
    expect(html).not.toContain('- `A`')
  })

  it('renders inline Markdown such as bold and links', () => {
    const html = renderToStaticMarkup(
      <ColumnDescription description="**Primary** key, see [docs](https://example.com)" />,
    )
    expect(html).toContain('<strong>Primary</strong>')
    expect(html).toContain('href="https://example.com"')
  })

  it('sanitizes HTML in descriptions', () => {
    const html = renderToStaticMarkup(
      <ColumnDescription description={'ok <img src=x onerror="alert(1)">'} />,
    )
    expect(html).not.toContain('onerror')
  })

  it('shows the auto badge only for generated descriptions', () => {
    expect(renderToStaticMarkup(<ColumnDescription description="x" isGenerated />)).toContain('auto')
    expect(renderToStaticMarkup(<ColumnDescription description="x" />)).not.toContain('>auto<')
  })
})
