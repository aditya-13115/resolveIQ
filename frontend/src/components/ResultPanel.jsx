function Badge({ escalated }) {
  return (
    <span className={`badge ${escalated ? 'escalate' : 'auto'}`}>
      {escalated ? 'Escalate' : 'Auto-handle'}
    </span>
  )
}

function Stage({ idx, name, value, status }) {
  return (
    <div className={`stage ${status}`}>
      <span className="dot" />
      <div className="idx">{idx}</div>
      <div className="name">{name}</div>
      <div className="value">{value}</div>
    </div>
  )
}

function Bar({ value, kind = 'green' }) {
  const pct = Math.max(0, Math.min(1, value)) * 100
  return (
    <div className={`bar ${kind}`}>
      <span style={{ width: `${pct}%` }} />
    </div>
  )
}

function Metric({ label, value, bar }) {
  return (
    <div className="metric">
      <div className="label">
        <span>{label}</span>
        <b>{value}</b>
      </div>
      {bar != null && <Bar value={bar} />}
    </div>
  )
}

function Precedent({ p, rank, used }) {
  const scorePct = Math.min(1, p.score / 0.3) // 0.3 is roughly max observed
  return (
    <li className={`precedent ${used ? 'used' : ''}`}>
      <div className="rank">{String(rank).padStart(2, '0')}</div>
      <div>
        <div className="head">
          <code className="intent">{p.intent}</code>
          <span className="score">
            score {p.score.toFixed(3)}
            <span className="score-bar">
              <span style={{ width: `${scorePct * 100}%` }} />
            </span>
          </span>
          {used && <span className="used-tag">Cited</span>}
        </div>
        <p className="text">
          <span className="who">Customer</span>
          {p.customer_text}
        </p>
        <p className="text">
          <span className="who">Reply</span>
          {p.response_text}
        </p>
      </div>
    </li>
  )
}

export default function ResultPanel({ result }) {
  const conf = result.confidence ?? 0
  const cal = result.confidence_calibrated ?? 0

  // Pipeline stages
  const classifyStatus = result.intent === 'other' || result.intent === 'ambiguous'
    ? 'warn'
    : 'ok'
  const retrieveStatus = result.corpus_coverage ? 'ok' : 'warn'
  const escalateStatus = result.escalated ? 'warn' : 'ok'
  const generateStatus = result.escalated
    ? 'skip'
    : result.api_status === 'ok' ? 'ok' : 'fail'

  return (
    <div>
      <div className="result-head">
        <div>
          <h3 className="intent">
            <code>{result.intent}</code>
            {result.alternative_intent && (
              <span className="alt">
                alternative &ldquo;{result.alternative_intent}&rdquo; at{' '}
                {(result.alternative_confidence ?? 0).toFixed(3)}
              </span>
            )}
          </h3>
        </div>
        <Badge escalated={result.escalated} />
      </div>

      <div className="pipeline">
        <Stage
          idx="01"
          name="Classify"
          value={result.intent}
          status={classifyStatus}
        />
        <Stage
          idx="02"
          name="Retrieve"
          value={`${result.retrieved.length} precedent${result.retrieved.length === 1 ? '' : 's'}`}
          status={retrieveStatus}
        />
        <Stage
          idx="03"
          name="Route"
          value={result.escalated ? `escalate · ${result.escalation_reason}` : 'auto-handle'}
          status={escalateStatus}
        />
        <Stage
          idx="04"
          name="Generate"
          value={result.escalated ? 'skipped' : (result.api_status ?? 'ok')}
          status={generateStatus}
        />
      </div>

      <div className="metrics">
        <Metric label="Raw confidence" value={conf.toFixed(3)} bar={conf} />
        <Metric
          label="Calibrated confidence"
          value={cal.toFixed(3)}
          bar={cal}
        />
      </div>

      <div className={`reply-block ${result.escalated ? 'escalated' : ''}`}>
        <div className="head">
          {result.escalated ? 'Escalated' : 'Generated reply'}
        </div>
        <p className="body">
          {result.escalated
            ? `Routed to a human agent. Reason: ${result.escalation_reason}.`
            : (result.reply || '—')}
        </p>
        {!result.escalated && (
          <div className="foot">
            {result.used_precedent_ranks?.length > 0 ? (
              <span>Cited precedents {result.used_precedent_ranks.join(', ')}</span>
            ) : (
              <span>No precedents cited</span>
            )}
            {result.api_status && result.api_status !== 'ok' && (
              <span className="warn">api · {result.api_status}</span>
            )}
          </div>
        )}
      </div>

      <h2 className="rubric" style={{ marginTop: 32 }}>
        Retrieved precedent · {result.retrieved.length}
      </h2>
      <ol className="precedents">
        {result.retrieved.map((p, i) => (
          <Precedent
            key={p.root_id ?? i}
            p={p}
            rank={i + 1}
            used={(result.used_precedent_ranks ?? []).includes(i + 1)}
          />
        ))}
      </ol>
    </div>
  )
}