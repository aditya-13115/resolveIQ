const BASE = '/api'

export async function classify(message, { topK = 5, forceEscalate = false } = {}) {
  const r = await fetch(`${BASE}/classify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      top_k: topK,
      force_escalate: forceEscalate,
    }),
  })
  if (!r.ok) {
    const detail = await r.text()
    throw new Error(`API ${r.status}: ${detail}`)
  }
  return r.json()
}

export async function getTaxonomy() {
  const r = await fetch(`${BASE}/taxonomy`)
  if (!r.ok) throw new Error(`API ${r.status}`)
  return r.json()
}