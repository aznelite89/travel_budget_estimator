import { useEffect, useMemo, useState } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const BUDGET_STYLES = [
  { value: 'budget', label: 'Budget' },
  { value: 'midrange', label: 'Midrange' },
  { value: 'luxury', label: 'Luxury' },
]

async function apiFetch(path, options) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  })
  const contentType = res.headers.get('content-type') || ''
  const data = contentType.includes('application/json') ? await res.json() : await res.text()
  if (!res.ok) {
    const msg = typeof data === 'string' ? data : data?.detail || 'Request failed'
    throw new Error(msg)
  }
  return data
}

function formatCurrency(amount, currency) {
  if (typeof amount !== 'number' || Number.isNaN(amount)) return '-'
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(amount)
  } catch {
    return `${currency} ${amount.toFixed(0)}`
  }
}

function App() {
  const [form, setForm] = useState({
    trip_title: 'My Trip',
    origin: 'Kuala Lumpur',
    destination: 'Tokyo',
    start_date: '2026-03-10',
    end_date: '2026-03-17',
    travelers: 2,
    currency: 'MYR',
    budget_style: 'midrange',
  })

  const [job, setJob] = useState(null)
  const [events, setEvents] = useState([])
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)

  const canSubmit = useMemo(() => {
    return (
      form.trip_title.trim() &&
      form.origin.trim() &&
      form.destination.trim() &&
      form.start_date.trim() &&
      form.end_date.trim() &&
      Number(form.travelers) >= 1 &&
      form.currency.trim()
    )
  }, [form])

  async function submitJob(e) {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    setJob(null)
    setEvents([])
    try {
      const created = await apiFetch('/api/estimate-jobs', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          travelers: Number(form.travelers),
        }),
      })
      setJob(created)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  useEffect(() => {
    if (!job?.job_id) return
    if (job.status === 'done' || job.status === 'error' || job.status === 'cancelled') return

    let cancelled = false
    const source = new EventSource(`${API_BASE_URL}/api/estimate-jobs/${job.job_id}/events`)

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data.replace(/'/g, '"'))
        if (!cancelled) {
          setEvents((prev) => [...prev, payload])
        }
      } catch {
        // ignore malformed events
      }
    }

    source.onerror = () => {
      source.close()
    }

    const pollInterval = setInterval(async () => {
      try {
        const latest = await apiFetch(`/api/estimate-jobs/${job.job_id}`)
        if (!cancelled) setJob(latest)
        if (['done', 'error', 'cancelled'].includes(latest.status)) {
          clearInterval(pollInterval)
          source.close()
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      }
    }, 1500)

    return () => {
      cancelled = true
      clearInterval(pollInterval)
      source.close()
    }
  }, [job?.job_id, job?.status])

  async function cancelJob() {
    if (!job?.job_id) return
    setIsCancelling(true)
    try {
      const updated = await apiFetch(`/api/estimate-jobs/${job.job_id}/cancel`, {
        method: 'POST',
      })
      setJob(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsCancelling(false)
    }
  }

  const result = job?.result
  const totals = result?.totals
  const estimates = result?.estimates
  const currency = result?.meta?.currency || form.currency

  return (
    <>
      <h1>Travel Budget Estimator</h1>

      <p style={{ marginTop: 0, color: '#888' }}>
        Backend: <code>{API_BASE_URL}</code>
      </p>

      <form className="card" onSubmit={submitJob}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <label>
            Trip title
            <input
              value={form.trip_title}
              onChange={(e) => setForm((f) => ({ ...f, trip_title: e.target.value }))}
              placeholder="My Trip"
            />
          </label>

          <label>
            Travelers
            <input
              type="number"
              min={1}
              value={form.travelers}
              onChange={(e) => setForm((f) => ({ ...f, travelers: e.target.value }))}
            />
          </label>

          <label>
            Origin
            <input
              value={form.origin}
              onChange={(e) => setForm((f) => ({ ...f, origin: e.target.value }))}
              placeholder="Kuala Lumpur"
            />
          </label>

          <label>
            Destination
            <input
              value={form.destination}
              onChange={(e) => setForm((f) => ({ ...f, destination: e.target.value }))}
              placeholder="Tokyo"
            />
          </label>

          <label>
            Start date
            <input
              value={form.start_date}
              onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
              placeholder="YYYY-MM-DD"
            />
          </label>

          <label>
            End date
            <input
              value={form.end_date}
              onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
              placeholder="YYYY-MM-DD"
            />
          </label>

          <label>
            Currency
            <input
              value={form.currency}
              onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))}
              placeholder="MYR"
            />
          </label>

          <label>
            Budget style
            <select
              value={form.budget_style}
              onChange={(e) => setForm((f) => ({ ...f, budget_style: e.target.value }))}
            >
              {BUDGET_STYLES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 16 }}>
          <button type="submit" disabled={!canSubmit || isSubmitting}>
            {isSubmitting ? 'Submitting…' : 'Run estimate'}
          </button>
          {job?.job_id && (job.status === 'queued' || job.status === 'running') ? (
            <button type="button" onClick={cancelJob} disabled={isCancelling}>
              {isCancelling ? 'Cancelling…' : 'Cancel job'}
            </button>
          ) : null}
          {job?.job_id ? (
            <span style={{ color: '#888' }}>
              Job: <code>{job.job_id}</code> ({job.status})
            </span>
          ) : null}
        </div>
      </form>

      {error ? (
        <div className="card" style={{ borderColor: '#7a2b2b' }}>
          <strong style={{ color: '#ffb4b4' }}>Error</strong>
          <div style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{error}</div>
        </div>
      ) : null}

      {job?.status === 'running' || job?.status === 'queued' ? (
        <div className="card">
          <strong>Status</strong>
          <div style={{ marginTop: 8 }}>Working… ({job.status})</div>
        </div>
      ) : null}

      {job?.status === 'error' ? (
        <div className="card" style={{ borderColor: '#7a2b2b' }}>
          <strong style={{ color: '#ffb4b4' }}>Job failed</strong>
          <div style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{job.error}</div>
        </div>
      ) : null}

      {events.length > 0 ? (
        <div className="card">
          <strong>Progress</strong>
          <div
            style={{
              marginTop: 8,
              maxHeight: 160,
              overflowY: 'auto',
              fontFamily: 'monospace',
              fontSize: 12,
              lineHeight: 1.4,
            }}
          >
            {events.map((e, idx) => (
              <div key={idx} style={{ marginBottom: 4 }}>
                <span style={{ color: '#888' }}>
                  {e.created_at ? new Date(e.created_at).toLocaleTimeString() : ''}
                </span>{' '}
                <span>[{e.type}]</span> {e.message}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {job?.status === 'done' && result ? (
        <div className="card">
          <strong>Totals</strong>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
            <div>
              <div style={{ color: '#888' }}>Low</div>
              <div style={{ fontSize: 20 }}>{formatCurrency(totals?.low, currency)}</div>
            </div>
            <div>
              <div style={{ color: '#888' }}>High</div>
              <div style={{ fontSize: 20 }}>{formatCurrency(totals?.high, currency)}</div>
            </div>
            <div>
              <div style={{ color: '#888' }}>Base</div>
              <div style={{ fontSize: 28, fontWeight: 700 }}>{formatCurrency(totals?.base, currency)}</div>
            </div>
            <div>
              <div style={{ color: '#888' }}>Per person (base)</div>
              <div style={{ fontSize: 28, fontWeight: 700 }}>
                {formatCurrency(totals?.per_person_base, currency)}
              </div>
            </div>
          </div>

          {estimates ? (
            <>
              <hr style={{ margin: '18px 0', borderColor: '#2a2a2a' }} />
              <strong>Categories (base)</strong>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
                {Object.entries(estimates).map(([key, cat]) => (
                  <div key={key} style={{ padding: 12, border: '1px solid #2a2a2a', borderRadius: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                      <div style={{ textTransform: 'capitalize' }}>{key.replace('_', ' ')}</div>
                      <div style={{ fontWeight: 700 }}>{formatCurrency(cat?.base, currency)}</div>
                    </div>
                    <div style={{ color: '#888', marginTop: 6 }}>
                      Confidence: {typeof cat?.confidence === 'number' ? Math.round(cat.confidence * 100) : '-'}%
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </>
  )
}

export default App
