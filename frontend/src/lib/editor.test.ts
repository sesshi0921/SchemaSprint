import { describe, expect, it } from 'vitest'
import { analyze, parseSource, serializeSource } from './editor'

describe('editor canonical model', () => {
  it('parses DDL without accepting an invalid source', () => {
    const result = parseSource('ddl', 'CREATE TABLE users (id uuid PRIMARY KEY, email text NOT NULL);')
    expect(result.schema?.tables).toHaveLength(1)
    expect(result.schema?.tables[0].columns[0].primaryKey).toBe(true)
    expect(result.diagnostics.some((item) => item.severity === 'error')).toBe(false)
  })
  it('maps DDL foreign keys to the canonical relationship model', () => {
    const result = parseSource('ddl', 'CREATE TABLE users (id uuid PRIMARY KEY); CREATE TABLE orders (user_id uuid, FOREIGN KEY (user_id) REFERENCES users (id));')
    expect(result.schema?.relationships).toHaveLength(1)
  })
  it('preserves diagnostic facts for an empty schema', () => {
    const result = parseSource('ddl', '')
    expect(result.schema?.tables).toHaveLength(0)
    expect(result.diagnostics[0].severity).toBe('info')
  })
  it('flags duplicate names as errors', () => {
    const result = parseSource('dbml', 'Table users { id uuid }\nTable users { id uuid }')
    expect(analyze(result.schema!).some((item) => item.severity === 'error')).toBe(true)
  })
  it('keeps an invalid source out of the canonical model', () => {
    const result = parseSource('mermaid', 'not a diagram')
    expect(result.schema).toBeUndefined()
    expect(result.diagnostics.some((item) => item.severity === 'error')).toBe(true)
  })
  it('round-trips relationships through DBML', () => {
    const result = parseSource('dbml', 'Table users {\n  id uuid [pk]\n}\nTable orders {\n  user_id uuid\n}\nRef: orders.user_id > users.id')
    expect(result.schema?.relationships).toHaveLength(1)
    expect(serializeSource('dbml', result.schema!)).toContain('Ref: orders.user_id > users.id')
  })
  it('parses Mermaid entities and relation lines', () => {
    const result = parseSource('mermaid', 'erDiagram\n  USERS {\n    uuid id PK\n  }\n  ORDERS {\n    uuid user_id\n  }\n  USERS ||--o{ ORDERS : contains')
    expect(result.schema?.tables).toHaveLength(2)
    expect(result.schema?.relationships).toHaveLength(1)
    expect(result.schema?.relationships[0].toCardinality).toBe('0..*')
  })
  it('parses DBML flags and table-level DDL primary keys without loss', () => {
    const dbml = parseSource('dbml', 'Table users {\n id uuid [pk, not null]\n}')
    expect(dbml.schema?.tables[0].columns[0].primaryKey).toBe(true)
    const ddl = parseSource('ddl', 'CREATE TABLE users (id uuid, email text, PRIMARY KEY (id));')
    expect(ddl.schema?.tables[0].columns[0].primaryKey).toBe(true)
  })
})
