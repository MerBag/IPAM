import { MoreHorizontal, Pencil, Plus, Search, Trash2, type LucideIcon } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useApiData } from '../hooks/useApiData'
import { queryString, request, unwrapList } from '../lib/api'
import type { Id } from '../types'
import { Button, Card, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Pagination, Select, SkeletonRows, TableContainer, Textarea } from './ui'

export type ResourceField<T> = {
  key: keyof T & string
  label: string
  type?: 'text' | 'email' | 'textarea' | 'select'
  placeholder?: string
  required?: boolean
  hint?: string
  options?: { label: string; value: string }[]
  fullWidth?: boolean
  defaultValue?: string
}

export type ResourceColumn<T> = {
  key: string
  label: string
  render: (record: T) => ReactNode
}

type Identifiable = { id: Id; name?: string }

function ResourceDialog<T extends Identifiable>({ noun, endpoint, fields, record, onClose, onChanged }: { noun: string; endpoint: string; fields: ResourceField<T>[]; record?: T; onClose: () => void; onChanged: () => void }) {
  const initial = Object.fromEntries(fields.map((field) => [field.key, String(record?.[field.key] ?? field.defaultValue ?? '')])) as Record<string, string>
  const [values, setValues] = useState(initial)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const { notify } = useToast()
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = Object.fromEntries(fields.map((field) => [field.key, values[field.key]?.trim() || null]))
      await request(record ? `${endpoint}/${record.id}` : endpoint, { method: record ? 'PATCH' : 'POST', body: payload })
      notify(`${record ? 'Updated' : 'Created'} ${values.name || noun.toLowerCase()}.`)
      onChanged()
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : `Unable to save ${noun.toLowerCase()}.`)
    } finally {
      setSaving(false)
    }
  }
  return (
    <Modal title={`${record ? 'Edit' : 'Add'} ${noun.toLowerCase()}`} description={`Keep the ${noun.toLowerCase()} inventory connected to address assignments.`} onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        {error && <div className="form-alert" role="alert">{error}</div>}
        <div className="form-grid">
          {fields.map((field) => (
            <div className={field.fullWidth || field.type === 'textarea' ? 'form-grid__full' : ''} key={field.key}>
              <Field label={field.label} hint={field.hint} required={field.required}>
                {field.type === 'textarea' ? <Textarea rows={3} value={values[field.key] || ''} onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} placeholder={field.placeholder} required={field.required} /> : field.type === 'select' ? <Select value={values[field.key] || ''} onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} required={field.required}><option value="">Select {field.label.toLowerCase()}</option>{field.options?.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</Select> : <Input autoFocus={field.key === fields[0]?.key} type={field.type === 'email' ? 'email' : 'text'} value={values[field.key] || ''} onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} placeholder={field.placeholder} required={field.required} />}
              </Field>
            </div>
          ))}
        </div>
        <div className="modal__actions"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? 'Saving…' : record ? 'Save changes' : `Add ${noun.toLowerCase()}`}</Button></div>
      </form>
    </Modal>
  )
}

function DeleteDialog<T extends Identifiable>({ noun, endpoint, record, onClose, onChanged }: { noun: string; endpoint: string; record: T; onClose: () => void; onChanged: () => void }) {
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  const { notify } = useToast()
  const remove = async () => {
    setDeleting(true)
    setError('')
    try {
      await request(`${endpoint}/${record.id}`, { method: 'DELETE' })
      notify(`${record.name || noun} was deleted.`)
      onChanged()
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : `Unable to delete ${noun.toLowerCase()}.`)
    } finally {
      setDeleting(false)
    }
  }
  return (
    <Modal title={`Delete ${record.name || noun.toLowerCase()}?`} description="This action is subject to server-side relationship and audit protections." onClose={onClose} size="small">
      <div className="form-stack">
        {error && <div className="form-alert" role="alert">{error}</div>}
        <div className="danger-callout"><Trash2 size={20} /><div><strong>This cannot be undone from this screen.</strong><p>Addresses and historical allocations will not be silently removed.</p></div></div>
        <div className="modal__actions"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="danger" onClick={remove} disabled={deleting}>{deleting ? 'Deleting…' : 'Delete'}</Button></div>
      </div>
    </Modal>
  )
}

export function ResourcePage<T extends Identifiable>({ endpoint, noun, nounPlural, eyebrow, description, icon: Icon, fields, columns }: { endpoint: string; noun: string; nounPlural: string; eyebrow: string; description: string; icon: LucideIcon; fields: ResourceField<T>[]; columns: ResourceColumn<T>[] }) {
  const [params, setParams] = useSearchParams()
  const search = params.get('search') || ''
  const page = Math.max(1, Number(params.get('page') || 1))
  const pageSize = 50
  const skip = (page - 1) * pageSize
  const listPath = `${endpoint}${queryString({ q: search, skip, limit: pageSize + 1 })}`
  const { data, loading, error, reload } = useApiData<unknown>(listPath, [])
  const [editing, setEditing] = useState<T | 'new' | null>(null)
  const [deleting, setDeleting] = useState<T | null>(null)
  const [activeMenu, setActiveMenu] = useState<Id | null>(null)
  const { user } = useAuth()
  const readOnly = user?.role === 'read_only'
  const batch = unwrapList<T>(data)
  const hasNext = batch.length > pageSize
  const records = batch.slice(0, pageSize)
  const visibleTotal = skip + records.length
  const changePage = (nextPage: number) => {
    const next = new URLSearchParams(params)
    nextPage > 1 ? next.set('page', String(nextPage)) : next.delete('page')
    setParams(next)
  }
  return (
    <div className="page">
      <PageHeader eyebrow={eyebrow} title={nounPlural} description={description} actions={!readOnly && <Button onClick={() => setEditing('new')}><Plus size={16} /> Add {noun.toLowerCase()}</Button>} />
      {error && <ErrorState message={error} onRetry={reload} />}
      <Card>
        <div className="table-toolbar"><div className="search-input"><Search size={16} /><Input value={search} onChange={(event) => setParams(event.target.value ? { search: event.target.value } : {})} placeholder={`Search ${nounPlural.toLowerCase()}…`} /></div><span className="record-count">{records.length ? `${skip + 1}–${skip + records.length}` : '0'} shown</span></div>
        <TableContainer>
          <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}{!readOnly && <th><span className="sr-only">Actions</span></th>}</tr></thead>
          {loading ? <SkeletonRows rows={6} columns={columns.length + (readOnly ? 0 : 1)} /> : (
            <tbody>
              {records.map((record) => (
                <tr key={record.id}>{columns.map((column) => <td key={column.key}>{column.render(record)}</td>)}{!readOnly && <td className="actions-cell"><button type="button" className="icon-button" aria-label={`Actions for ${record.name || noun}`} onClick={() => setActiveMenu((current) => current === record.id ? null : record.id)}><MoreHorizontal size={18} /></button>{activeMenu === record.id && <div className="row-menu"><button type="button" onClick={() => { setEditing(record); setActiveMenu(null) }}><Pencil size={15} /> Edit</button><button type="button" className="row-menu__danger" onClick={() => { setDeleting(record); setActiveMenu(null) }}><Trash2 size={15} /> Delete</button></div>}</td>}</tr>
              ))}
            </tbody>
          )}
        </TableContainer>
        {!loading && records.length === 0 && <EmptyState icon={Icon} title={search ? `No matching ${nounPlural.toLowerCase()}` : `No ${nounPlural.toLowerCase()} yet`} description={search ? 'Try a different search term.' : `Add the first ${noun.toLowerCase()} to begin building this inventory.`} action={!search && !readOnly && <Button size="small" onClick={() => setEditing('new')}><Plus size={14} /> Add {noun.toLowerCase()}</Button>} />}
        {!loading && (page > 1 || hasNext) && <Pagination page={page} pages={hasNext ? page + 1 : page} total={visibleTotal} pageSize={pageSize} hasNext={hasNext} totalExact={false} onPageChange={changePage} />}
      </Card>
      {editing && <ResourceDialog<T> noun={noun} endpoint={endpoint} fields={fields} record={editing === 'new' ? undefined : editing} onClose={() => setEditing(null)} onChanged={reload} />}
      {deleting && <DeleteDialog noun={noun} endpoint={endpoint} record={deleting} onClose={() => setDeleting(null)} onChanged={reload} />}
    </div>
  )
}
