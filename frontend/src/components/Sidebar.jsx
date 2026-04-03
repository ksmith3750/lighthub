import styles from './Sidebar.module.css'

const NAV_ITEMS = [
  { id: 'devices', label: 'Devices', icon: '◈' },
  { id: 'scenes', label: 'Scenes', icon: '✦' },
  { id: 'schedules', label: 'Schedules', icon: '◷' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
]

const STATUS_DOT = ({ on, total }) => {
  if (total === 0) return <span className={styles.dotEmpty} />
  if (on === 0) return <span className={styles.dotOff} />
  if (on === total) return <span className={styles.dotOn} />
  return <span className={styles.dotMixed} />
}

export default function Sidebar({
  page, onNavigate, selectedRoom, onSelectRoom,
  roomSummary, rooms, roomLabels, devices, onDiscover, discovering
}) {
  const totalOn = devices.filter(d => d.on).length

  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <div className={styles.brandIcon}>
          <svg viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="8" r="5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M7.5 13.5v2M12.5 13.5v2M8.5 15.5h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </div>
        <span className={styles.brandName}>LightHub</span>
        <span className={styles.onCount}>{totalOn} on</span>
      </div>

      <nav className={styles.nav}>
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            className={`${styles.navItem} ${page === item.id ? styles.navActive : ''}`}
            onClick={() => onNavigate(item.id)}
          >
            <span className={styles.navIcon}>{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className={styles.section}>
        <div className={styles.sectionLabel}>Rooms</div>
        <button
          className={`${styles.roomBtn} ${selectedRoom === 'all' ? styles.roomActive : ''}`}
          onClick={() => onSelectRoom('all')}
        >
          <span className={styles.dotMixed} />
          All rooms
          <span className={styles.roomCount}>{devices.length}</span>
        </button>
        {rooms.map(room => {
          const { total, on } = roomSummary[room] || { total: 0, on: 0 }
          return (
            <button
              key={room}
              className={`${styles.roomBtn} ${selectedRoom === room ? styles.roomActive : ''}`}
              onClick={() => onSelectRoom(room)}
            >
              <STATUS_DOT on={on} total={total} />
              {roomLabels[room]}
              <span className={styles.roomCount}>{total}</span>
            </button>
          )
        })}
      </div>

      <div className={styles.footer}>
        <button className={styles.discoverBtn} onClick={onDiscover} disabled={discovering}>
          {discovering ? (
            <><span className={styles.spinner} /> Scanning...</>
          ) : (
            <><span>⊕</span> Discover devices</>
          )}
        </button>
      </div>
    </aside>
  )
}
