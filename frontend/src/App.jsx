import { useEffect, useState } from 'react'
import { classify, getTaxonomy } from './api'
import QueryForm from './components/QueryForm'
import ResultPanel from './components/ResultPanel'

export default function App() {
  const [taxonomy, setTaxonomy] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getTaxonomy().then(setTaxonomy).catch(() => {})
  }, [])

  const onSubmit = async (message, opts) => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setResult(await classify(message, opts))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="masthead">
        <div className="brand">
          <h1>
            Resolve<em>IQ</em>
          </h1>
          <span className="issue">Issue 01 · {new Date().getFullYear()}</span>
        </div>
        <div className="meta">
          Brand <b>GWRHelp</b>
          <br />
          Taxonomy <b>v1 · 11 intents</b>
          <br />
          Corpus <b>50 precedents</b>
        </div>
        <p className="tagline">
          A selective, evidence-grounded support agent. Classifies intent,
          retrieves historical precedent, drafts a reply, and decides whether
          to auto-handle or escalate.
        </p>
      </header>

      <main className="board">
        <section className="col-left">
          <h2 className="rubric">Query</h2>
          <QueryForm
            onSubmit={onSubmit}
            loading={loading}
            taxonomy={taxonomy}
          />
        </section>

        <section className="col-right result">
          <h2 className="rubric">Analysis</h2>
          {error && <div className="error">{error}</div>}
          {result && <ResultPanel result={result} />}
          {!result && !error && (
            <div className="placeholder">
              Enter a customer message and press Run. The classifier will
              assign an intent, the retriever will surface the top-k
              historical precedents from the corpus, and the agent will
              generate a reply or decide to escalate.
            </div>
          )}
        </section>
      </main>

      <footer className="colophon">
        <div className="metrics">
          Frozen test metrics &mdash; op macro F1 <b>0.624</b> ·
          recall@5 <b>0.532</b> · safe automation coverage <b>0.295</b> ·
          unsafe automation rate <b>0.597</b>
        </div>
        <div className="sig">
          Not a production service · 2026
        </div>
      </footer>
    </div>
  )
}