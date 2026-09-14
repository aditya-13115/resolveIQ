import { useState } from 'react'

const EXAMPLES = [
  {
    label: 'Delay Repay claim',
    text: '@GWRHelp my train was 45 minutes late yesterday, how do I claim delay repay?',
  },
  {
    label: 'Running-status check',
    text: '@GWRHelp is the 18:21 WMN to CDF running?',
  },
  {
    label: 'Lost property',
    text: 'Left my bag on the 17:45 Pad to Swansea train. What do I do?',
  },
  {
    label: 'Sarcastic complaint',
    text: 'Love a delayed train 🤔 @GWRHelp',
  },
  {
    label: 'Repeat booking issue',
    text: 'Third time this week the seat reservations have been double booked between Didcot & Paddington. Can you sort this out please.',
  },
  // ── Escalation triggers ───────────────────────────────────────
  {
    label: '· Escalate: bare greeting',
    text: 'Hello, hope you are having a good day!',
  },
  {
    label: '· Escalate: off-topic request',
    text: 'Do you have a marketing email address or phone number we could use?',
  },
  {
    label: '· Escalate: compound complaint',
    text: 'Train was late, toilet was broken, seat was dirty, and I want compensation and to file a formal complaint — this is unacceptable.',
  },
  {
    label: '· Escalate: no coverage (lost item)',
    text: 'I left my suitcase on the 17:45 Paddington to Swansea train. What should I do?',
  },
]

export default function QueryForm({ onSubmit, loading, taxonomy }) {
  const [message, setMessage] = useState(EXAMPLES[0].text)
  const [topK, setTopK] = useState('5')       // keep as string
  const [forceEscalate, setForceEscalate] = useState(false)

  // Digit-only, max 2 chars. Allows the field to be empty while editing.
  const handleTopK = (e) => {
    const v = e.target.value.replace(/[^0-9]/g, '').slice(0, 2)
    setTopK(v)
  }

  const commitTopK = () => {
    const n = parseInt(topK, 10)
    const clamped = Number.isFinite(n) ? Math.min(10, Math.max(1, n)) : 5
    setTopK(String(clamped))
  }

  const submit = (e) => {
    e.preventDefault()
    if (!message.trim() || loading) return
    const n = parseInt(topK, 10)
    const k = Number.isFinite(n) ? Math.min(10, Math.max(1, n)) : 5
    onSubmit(message, { topK: k, forceEscalate })
  }

  return (
    <form onSubmit={submit}>
      <div className="field">
        <label htmlFor="msg">Customer message</label>
        <textarea
          id="msg"
          rows={6}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Paste a customer message…"
        />
      </div>

      <div className="controls">
        <label className="inline">
          <span
            style={{
              fontFamily: 'var(--mono)',
              fontSize: 11,
              letterSpacing: '0.16em',
              textTransform: 'uppercase',
              color: 'var(--ink-3)',
            }}
          >
            Top-k
          </span>
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={2}
            value={topK}
            onChange={handleTopK}
            onBlur={commitTopK}
            onFocus={(e) => e.target.select()}
          />
        </label>

        <label className="inline">
          <input
            type="checkbox"
            checked={forceEscalate}
            onChange={(e) => setForceEscalate(e.target.checked)}
          />
          Force escalate
        </label>
      </div>

      <button type="submit" className="run" disabled={loading || !message.trim()}>
        {loading ? 'Running' : 'Run agent'}
        <span className="arrow">{loading ? '…' : '→'}</span>
      </button>

      <div className="examples">
        <span className="label">Sample messages</span>
        <div>
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              className={`chip ${ex.label.startsWith('·') ? 'chip-alt' : ''}`}
              onClick={() => setMessage(ex.text)}
              title={ex.text}
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      {taxonomy && (
        <details className="taxonomy">
          <summary>Taxonomy · {taxonomy.intents.length} intents</summary>
          <ul>
            {taxonomy.intents.map((it) => (
              <li key={it.name}>
                <code>{it.name}</code>
                {it.description}
              </li>
            ))}
          </ul>
        </details>
      )}
    </form>
  )
}