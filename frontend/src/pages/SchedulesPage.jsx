import { useState } from 'react'
import styles from './SchedulesPage.module.css'

const DAYS = ['mon','tue','wed','thu','fri','sat','sun']
const DAY_LABELS = { mon:'M', tue:'T', wed:'W', thu:'T', fri:'F', sat:'S', sun:'S' }
const DAY_FULL = { mon:'Mon', tue:'Tue', wed:'Wed', thu:'Thu', fri:'Fri', sat:'Sat', sun:'Sun' }

function formatTime(t) {
  if (t === 'sunset') return '🌇 Sunset'
  if (t === 'sunrise') return '🌅 Sunrise'
  const [h, m] = t.split(':').map(Number)
  const ampm = h >= 12 ? 'pm' : 'am'
  const h12 = h % 12 || 12
  return `${h12}:${m.toString().padStart(2,'0')} ${ampm}`
}

export default function SchedulesPage({ schedules, scenes, onCreate, onToggle, onDelete }) {
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({
    name: '', time: '07:00', days: ['mon','tue','wed','thu','fri'],
    scene_name: '', enabled: true
  })

  const toggleDay = (day) => {
    setForm(f => ({
      ...f,
      days: f.days.includes(day) ? f.days.filter(d => d !== day) : [...f.days, day]
    }))
  }

  const handleCreate = async () => {
    if (!form.name.trim() || !form.scene_name || form.days.length === 0) return
    await onCreate({ ...form })
    setCreating(false)
    setForm({ name: '', time: '07:00', days: ['mon','tue','wed','thu','fri'], scene_name: '', enabled: true })
  }

  const sceneNames = Object.keys(scenes)

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Schedules</h1>
          <p className={styles.sub}>Automate your lights with time-based triggers</p>
        </div>
        <button className={styles.createBtn} onClick={() => setCreating(true)}>+ Add schedule</button>
      </div>

      {creating && (
        <div className={styles.formPanel}>
          <div className={styles.formTitle}>New schedule</div>

          <div className={styles.field}>
            <label className={styles.fieldLabel}>Name</label>
            <input
              className={styles.input}
              placeholder="e.g. Morning routine"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              autoFocus
            />
          </div>

          <div className={styles.fieldRow}>
            <div className={styles.field}>
              <label className={styles.fieldLabel}>Time</label>
              <select
                className={styles.select}
                value={form.time.startsWith('s') ? form.time : 'custom'}
                onChange={e => {
                  if (e.target.value !== 'custom') setForm(f => ({ ...f, time: e.target.value }))
                }}
              >
                <option value="sunrise">Sunrise</option>
                <option value="sunset">Sunset</option>
                <option value="custom">Custom time</option>
              </select>
              {!form.time.startsWith('sun') && (
                <input
                  type="time"
                  className={styles.input}
                  value={form.time}
                  onChange={e => setForm(f => ({ ...f, time: e.target.value }))}
                  style={{ marginTop: 6 }}
                />
              )}
            </div>

            <div className={styles.field}>
              <label className={styles.fieldLabel}>Scene</label>
              <select
                className={styles.select}
                value={form.scene_name}
                onChange={e => setForm(f => ({ ...f, scene_name: e.target.value }))}
              >
                <option value="">Select a scene...</option>
                {sceneNames.map(name => (
                  <option key={name} value={name}>{scenes[name].icon} {name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className={styles.field}>
            <label className={styles.fieldLabel}>Days</label>
            <div className={styles.dayPicker}>
              {DAYS.map(day => (
                <button
                  key={day}
                  className={`${styles.dayBtn} ${form.days.includes(day) ? styles.dayActive : ''}`}
                  onClick={() => toggleDay(day)}
                >{DAY_LABELS[day]}</button>
              ))}
              <button
                className={styles.dayShortcut}
                onClick={() => setForm(f => ({ ...f, days: DAYS.slice(0,5) }))}
              >Weekdays</button>
              <button
                className={styles.dayShortcut}
                onClick={() => setForm(f => ({ ...f, days: [...DAYS] }))}
              >Every day</button>
            </div>
          </div>

          <div className={styles.formActions}>
            <button className={styles.cancelBtn} onClick={() => setCreating(false)}>Cancel</button>
            <button
              className={styles.saveBtn}
              onClick={handleCreate}
              disabled={!form.name.trim() || !form.scene_name || form.days.length === 0}
            >Save schedule</button>
          </div>
        </div>
      )}

      <div className={styles.list}>
        {schedules.length === 0 && !creating && (
          <div className={styles.empty}>
            <p>No schedules yet.</p>
            <p className={styles.emptyHint}>Add one to automate your lighting throughout the day.</p>
          </div>
        )}

        {schedules.map(schedule => {
          const scene = scenes[schedule.scene_name]
          return (
            <div key={schedule.id} className={`${styles.scheduleRow} ${!schedule.enabled ? styles.disabled : ''}`}>
              <div className={styles.schedTime}>
                <span className={styles.timeText}>{formatTime(schedule.time)}</span>
              </div>

              <div className={styles.schedInfo}>
                <div className={styles.schedName}>{schedule.name}</div>
                <div className={styles.schedMeta}>
                  {scene && <span className={styles.sceneTag}>{scene.icon} {schedule.scene_name}</span>}
                  <span className={styles.daysTag}>
                    {schedule.days.includes('everyday') || schedule.days.length === 7
                      ? 'Every day'
                      : schedule.days.map(d => DAY_FULL[d]).join(' · ')}
                  </span>
                </div>
              </div>

              <div className={styles.schedActions}>
                <button
                  className={`${styles.toggle} ${schedule.enabled ? styles.toggleOn : ''}`}
                  onClick={() => onToggle(schedule)}
                />
                <button className={styles.deleteBtn} onClick={() => onDelete(schedule.id)}>✕</button>
              </div>
            </div>
          )
        })}
      </div>

      <div className={styles.hint}>
        <div className={styles.hintTitle}>⚙ Running the scheduler</div>
        <p className={styles.hintText}>
          Start the scheduler daemon alongside the API server to enable time-based automation:
        </p>
        <code className={styles.hintCode}>python scheduler.py</code>
      </div>
    </div>
  )
}
