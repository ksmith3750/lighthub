import styles from './SenatorsModeCard.module.css'

export default function SenatorsModeCard({ status, onActivate, onDeactivate, loading }) {
  const active = status?.active ?? false
  const hasGame = active && status?.game_id != null
  const noGame = active && status?.game_id == null
  const logo = status?.team_logo

  return (
    <div className={`${styles.card} ${active ? styles.cardActive : ''}`}>
      <div className={styles.top}>
        {logo
          ? <img src={logo} alt="Ottawa Senators" className={styles.logo} />
          : <div className={styles.logoBadge}>OTT</div>
        }
        <div className={styles.info}>
          <div className={styles.name}>Ottawa Senators Mode</div>
          {hasGame && (
            <div className={styles.score}>
              OTT {status.senators_score} — {status.opponent_name?.split(' ').pop() ?? 'OPP'} {status.opponent_score}
            </div>
          )}
          {noGame && <div className={styles.noGame}>No game today</div>}
          {!active && <div className={styles.inactive}>Sets all lights to Senators red</div>}
        </div>
      </div>

      <button
        className={`${styles.toggleBtn} ${active ? styles.toggleBtnActive : ''}`}
        onClick={active ? onDeactivate : onActivate}
        disabled={loading}
      >
        {loading ? '...' : active ? 'Deactivate' : 'Activate'}
      </button>
    </div>
  )
}
