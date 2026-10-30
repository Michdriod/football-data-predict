import { useEffect, useState } from 'react'

const percent = (value, digits = 0) => `${(value * 100).toFixed(digits)}%`

const formatKickoff = (iso) =>
  new Date(iso).toLocaleString(undefined, {
    weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
  })

const formatDate = (date) =>
  new Date(date).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

function useApi(path) {
  const [state, setState] = useState({ loading: true })

  useEffect(() => {
    fetch(path)
      .then((response) => {
        if (!response.ok) throw new Error()
        return response.json()
      })
      .then((data) => setState({ data }))
      .catch(() => setState({ failed: true }))
  }, [path])

  return state
}

function Notice({ children }) {
  return (
    <p className="notice" role="status">
      <span aria-hidden="true">⚠</span> {children}
    </p>
  )
}

function PickCard({ pick }) {
  const winsPerLoss = pick.price > 1 ? Math.round(1 / (pick.price - 1)) : null

  return (
    <article className="card pick">
      <div>
        <p className="meta">{formatKickoff(pick.kickoff)}</p>
        <h3>{pick.home_team} vs {pick.away_team}</h3>
        <p className="pick-label">{pick.pick}</p>
      </div>
      <div className="pick-chance">
        <strong>{percent(pick.probability)}</strong>
        <span>chance</span>
      </div>
      {pick.price && (
        <p className="price">
          Pays {pick.price.toFixed(2)}{pick.price_is_calculated ? ' (estimated)' : ''}.
          {winsPerLoss ? ` One miss cancels about ${winsPerLoss} correct picks.` : ''}
        </p>
      )}
    </article>
  )
}

function MatchCard({ match }) {
  const { home, away } = match.injuries
  const news = [...home, ...away]

  return (
    <article className="card match">
      <p className="meta">{formatKickoff(match.kickoff)}</p>
      <h3>{match.home_team} vs {match.away_team}</h3>
      <ul className="markets">
        {match.markets.map((market) => (
          <li key={market.target} className={market.is_top_pick ? 'top' : ''}>
            <span>
              {market.label}
              {market.is_top_pick && <small> <span aria-hidden="true">★</span> Top pick</small>}
            </span>
            <strong>{percent(market.probability)}</strong>
          </li>
        ))}
      </ul>
      {news.length > 0 && (
        <div className="injuries">
          <p>Injury news (not included in the chances above)</p>
          <ul>
            {news.map((item) => (
              <li key={item.player}>{item.player}: {item.news}</li>
            ))}
          </ul>
        </div>
      )}
    </article>
  )
}

function Week() {
  const { loading, failed, data } = useApi('/api/week')

  if (loading) return <p className="meta">Checking this week's matches…</p>
  if (failed) return <Notice>Picks could not be loaded. Check that the app server is running.</Notice>

  return (
    <>
      {data.data_is_stale && (
        <Notice>Results are only up to {formatDate(data.data_through)}, so these chances may be out of date.</Notice>
      )}
      {data.odds_refresh_failed && (
        <Notice>Fixtures could not be refreshed. Showing the last saved list.</Notice>
      )}

      {data.picks.length > 0 ? (
        <div className="stack">
          {data.picks.map((pick) => (
            <PickCard key={`${pick.home_team}-${pick.away_team}`} pick={pick} />
          ))}
        </div>
      ) : (
        <div className="card empty">
          <h3>No top picks this week</h3>
          <p>
            None of the {data.matches_checked} upcoming matches reached {percent(data.threshold)}.
            That is the app doing its job: it does not lower the bar to fill the page.
          </p>
        </div>
      )}

      <p className="meta">
        {data.matches_checked} matches checked · Results up to {formatDate(data.data_through)}
      </p>

      {data.matches.length > 0 && (
        <section aria-labelledby="matches-heading">
          <h2 id="matches-heading">All matches</h2>
          <div className="stack">
            {data.matches.map((match) => (
              <MatchCard key={`${match.home_team}-${match.away_team}`} match={match} />
            ))}
          </div>
          <p className="meta">
            "Goal in the first half" is a weak prediction: it happens about 7 times in 10 and
            the model can barely tell these matches apart.
          </p>
        </section>
      )}
    </>
  )
}

function Stat({ value, label }) {
  return (
    <div className="card stat">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  )
}

function TrackRecord() {
  const { loading, failed, data } = useApi('/api/track-record')

  if (loading) return <p className="meta">Loading track record…</p>
  if (failed) return <Notice>The track record could not be loaded.</Notice>

  const { tested, live } = data

  return (
    <>
      <h3 className="subhead">Picks shown by this app</h3>
      {live.settled > 0 ? (
        <>
          <div className="stats">
            <Stat value={`${live.correct} of ${live.settled}`} label="correct so far" />
            <Stat value={live.issued - live.settled} label="still to play" />
          </div>
          <ul className="results">
            {live.recent.map((result) => (
              <li key={`${result.match_date}-${result.match}`}>
                <span className={result.won ? 'status won' : 'status lost'}>
                  <span aria-hidden="true">{result.won ? '✓' : '✕'}</span> {result.won ? 'Correct' : 'Wrong'}
                </span>
                <span>
                  {result.pick}
                  <small>{result.match} · {result.score}</small>
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="meta">
          No finished picks yet. {live.issued > 0 ? `${live.issued} waiting to be played. ` : ''}
          Each pick is saved when first shown, so this record can't be changed afterwards.
        </p>
      )}

      {tested && (
        <>
          <h3 className="subhead">Historical test</h3>
          <div className="stats">
            <Stat value={percent(tested.hit_rate, 1)} label={`correct, ${tested.correct} of ${tested.picks} picks`} />
            <Stat value={tested.typical_price.toFixed(2)} label="typical payout per 1 staked" />
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th scope="col">Season</th><th scope="col">Picks</th><th scope="col">Correct</th></tr>
              </thead>
              <tbody>
                {tested.seasons.map((season) => (
                  <tr key={season.season}>
                    <td>{season.season}</td>
                    <td>{season.picks}</td>
                    <td>{percent(season.hit_rate, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="meta">
            Each match was predicted using only earlier matches. Past results don't guarantee future ones.
            The 2026-27 season is still in progress.
          </p>
        </>
      )}
    </>
  )
}

export default function App() {
  return (
    <main>
      <header>
        <h1>Premier League Picks</h1>
        <p>Top picks are 85%+. Every match's chances are listed below them.</p>
      </header>

      <section aria-labelledby="picks-heading">
        <h2 id="picks-heading">Top picks, next 7 days</h2>
        <Week />
      </section>

      <section aria-labelledby="record-heading">
        <h2 id="record-heading">Track record</h2>
        <TrackRecord />
      </section>

      <footer>
        <strong>Sure doesn't mean profitable.</strong> Top picks are mostly strong favourites
        that pay very little, and testing found no proven way to profit from them.
        This is information, not betting advice.
      </footer>
    </main>
  )
}
