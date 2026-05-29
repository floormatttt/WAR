export default function Methodology() {
  return (
    <div className="methodology">
      <div className="method-header">
        <h1>Methodology</h1>
        <p className="method-subtitle">
          How we convert PFF pass blocking grades into Wins Above Replacement
        </p>
      </div>

      <div className="pipeline">
        <Step
          number={1}
          title="Pass Block Win Rate (PBWR)"
          status="done"
          description="The foundation metric. For each player-season, PBWR measures what fraction of pass blocking snaps they won — i.e., did not allow a pressure."
        >
          <FormulaBlock>
            {`PBWR = (1 - pressures_allowed / snap_counts_pass_block) × 100`}
          </FormulaBlock>
          <p>
            Calculated separately for <strong>all pass sets</strong> (screens, RPOs, play-actions included)
            and <strong>true pass sets</strong> (pure dropbacks only). Data sourced from PFF's pass blocking
            grades, which track individual matchups on each snap.
          </p>
          <p>
            A snap-count filter of ≥20% of the season maximum is applied to produce filtered leaderboards,
            removing players with too few meaningful reps.
          </p>
        </Step>

        <Connector />

        <Step
          number={2}
          title="Replacement Level"
          status="done"
          description="WAR requires a baseline: the PBWR of a freely available, replacement-level lineman. We define this as the snap-weighted average PBWR of the bottom tier of snap-qualified players each season."
        >
          <FormulaBlock>
            {`replacement_pbwr = weighted_avg(PBWR of bottom-tier snap-qualified players)`}
          </FormulaBlock>
          <p>
            Computed per season from the filtered CSVs. Using a snap-weighted average (rather than
            simple mean) accounts for the fact that replacement players accumulate fewer snaps and
            prevents low-snap outliers from distorting the baseline.
          </p>
        </Step>

        <Connector />

        <Step
          number={3}
          title="EPA per Pressure"
          status="done"
          description="To convert blocking performance into win value, we need to know how much a pressure actually hurts. This is measured as the EPA difference between plays with and without pressure."
        >
          <FormulaBlock>
            {`EPA_per_pressure = mean(EPA | pressure) − mean(EPA | clean pocket)`}
          </FormulaBlock>
          <p>
            Derived from nflfastR / nfl_data_py play-by-play data (2013–2024). A pressure shifts
            EPA by roughly −0.5 to −0.7 per play depending on season and down/distance context.
            We use a single season-level constant rather than situational splits to keep the model
            interpretable.
          </p>
        </Step>

        <Connector />

        <Step
          number={4}
          title="Pass Blocking WAR"
          status="done"
          description="Finally, we combine PBWR above replacement, snap count, EPA per pressure, and EPA per win to arrive at wins above replacement."
        >
          <FormulaBlock>
            {`pass_blocking_WAR =
  (replacement_pbwr − player_pbwr) / 100
  × snap_counts_pass_block
  × EPA_per_pressure
  / EPA_per_win`}
          </FormulaBlock>
          <p>
            <strong>EPA per win</strong> ≈ 13.5 — the standard football analytics constant for how
            many expected points of margin separate a typical win from a typical loss.
          </p>
          <p>
            The sign convention: a player with PBWR <em>above</em> replacement produces positive WAR
            (the formula subtracts player from replacement, so a better player yields a larger
            positive result). WAR values are in <strong>fractional wins</strong>; even elite linemen
            top out around 0.002 per season because pass blocking is one component of one side of
            one phase of football.
          </p>
        </Step>

        <Connector />

        <Step
          number={5}
          title="Run Blocking WAR"
          status="planned"
          description="Run blocking grades from PFF follow the same structural pipeline but require separate pressure/success rate baselines. Not yet implemented."
        >
          <p>
            Will use PFF run blocking CSV (same player/snap/grade structure) and nflfastR rushing
            EPA per blown assignment. Same replacement-level and WAR formula structure as pass blocking.
          </p>
        </Step>

        <Connector />

        <Step
          number={6}
          title="Tracking-Based Credit Attribution"
          status="planned"
          description="PFF grades individual matchups, but film shows a more complex picture: double teams, stunts, line games, and zone responsibilities blur individual accountability."
        >
          <p>
            The planned approach is <strong>SAM 3</strong>: a computer vision / tracking model applied
            to All-22 film that identifies which offensive lineman was responsible for each block on
            each snap — accounting for pre-snap assignments and post-snap adjustments. This replaces
            the PFF-graded responsibility attribution with a more objective, automated measurement.
          </p>
          <p>
            Once SAM 3 is operational, PBWR is recalculated on its output, which feeds back into the
            same WAR pipeline above.
          </p>
        </Step>
      </div>

      <div className="method-footer">
        <h2>Limitations & Caveats</h2>
        <ul className="caveats">
          <li>
            <strong>Single-phase scope:</strong> This is pass blocking WAR only. Total OL value
            includes run blocking, penalties, and scheme fit — none of which are captured here yet.
          </li>
          <li>
            <strong>Team context:</strong> A lineman on a pass-heavy offense accumulates more snaps
            and therefore more opportunity to accumulate WAR. We do not yet adjust for team pass rate.
          </li>
          <li>
            <strong>PFF grading subjectivity:</strong> Pressure attribution is based on PFF human
            grades, which have inter-rater reliability limitations. SAM 3 is intended to address this.
          </li>
          <li>
            <strong>Small WAR magnitudes:</strong> Values look small because an individual lineman
            affects at most 10–15% of all offensive plays per game. This is expected — offensive line
            WAR should be smaller in magnitude than QB WAR by design.
          </li>
        </ul>
      </div>
    </div>
  )
}

function Step({ number, title, status, description, children }) {
  return (
    <div className="step">
      <div className="step-header">
        <span className="step-number">{number}</span>
        <div className="step-title-row">
          <h2 className="step-title">{title}</h2>
          <span className={`status-badge status-${status}`}>
            {status === 'done' ? 'Built' : 'Planned'}
          </span>
        </div>
      </div>
      <p className="step-description">{description}</p>
      <div className="step-body">{children}</div>
    </div>
  )
}

function FormulaBlock({ children }) {
  return <pre className="formula">{children}</pre>
}

function Connector() {
  return <div className="pipeline-connector" />
}
