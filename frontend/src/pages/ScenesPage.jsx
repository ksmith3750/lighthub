import { useState } from 'react'
import styles from './ScenesPage.module.css'

const ICONS = ['💡','🌅','🎬','🍽️','💤','🎉','📚','🌙','🏠','🌈','🔆','🌒','⚡','🎵','🌿']

export default function ScenesPage({ scenes, devices, onActivate, onCreate, onDelete }) {
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [newIcon, setNewIcon] = useState('💡')
  const [activating, setActivating] = useState(null)

  const handleActivate = async (name) => {
    setActivating(name)
    await onActivate(name)
    setTimeout(() => setActivating(null), 1000)
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    // Capture current device states as the scene
    const deviceStates = {}
    devices.forEach(d => {
      deviceStates[d.id] = {
        on: d.on,
        ...(d.brightness != null ? { brightness: d.brightness } : {}),
        ...(d.color ? { color: d.color } : {}),
        ...(d.color_temp ? { color_temp: d.color_temp } : {}),
      }
    })
    await onCreate({ name: newName.trim(), icon: newIcon, devices: deviceStates })
    setCreating(false)
    setNewName('')
    setNewIcon('💡')
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Scenes</h1>
          <p className={styles.sub}>Activate a saved lighting mood instantly</p>
        </div>
        <button className={styles.createBtn} onClick={() => setCreating(true)}>
          + New scene
        </button>
      </div>

      {creating && (
        <div className={styles.createPanel}>
          <div className={styles.createTitle}>Create scene from current state</div>
          <p className={styles.createHint}>
            Set your lights to the desired state on the Devices page, then name and save the scene here.
          </p>
          <div className={styles.createRow}>
            <div className={styles.iconPicker}>
              {ICONS.map(ic => (
                <button
                  key={ic}
                  className={`${styles.iconOpt} ${newIcon === ic ? styles.iconSelected : ''}`}
                  onClick={() => setNewIcon(ic)}
                >{ic}</button>
              ))}
            </div>
            <input
              className={styles.nameInput}
              placeholder="Scene name..."
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              autoFocus
            />
          </div>
          <div className={styles.createActions}>
            <button className={styles.cancelBtn} onClick={() => setCreating(false)}>Cancel</button>
            <button className={styles.saveBtn} onClick={handleCreate} disabled={!newName.trim()}>
              Save scene
            </button>
          </div>
        </div>
      )}

      <div className={styles.grid}>
        {Object.entries(scenes).map(([name, scene]) => {
          const deviceCount = Object.keys(scene.devices || {}).length
          const onCount = Object.values(scene.devices || {}).filter(d => d.on !== false).length
          const isActivating = activating === name

          return (
            <div key={name} className={`${styles.card} ${isActivating ? styles.cardActivating : ''}`}>
              <div className={styles.cardIcon}>{scene.icon}</div>
              <div className={styles.cardName}>{name}</div>
              <div className={styles.cardMeta}>
                {onCount} lights on · {deviceCount} devices
              </div>

              {scene.devices && (
                <div className={styles.devicePreview}>
                  {Object.entries(scene.devices).slice(0, 5).map(([id, cmd]) => (
                    <div
                      key={id}
                      className={styles.previewDot}
                      style={{
                        background: cmd.on === false
                          ? 'var(--bg-hover)'
                          : cmd.color
                            ? `rgb(${cmd.color.r},${cmd.color.g},${cmd.color.b})`
                            : '#f5a623',
                        opacity: cmd.on === false ? 0.3 : 1
                      }}
                    />
                  ))}
                  {deviceCount > 5 && (
                    <span className={styles.previewMore}>+{deviceCount - 5}</span>
                  )}
                </div>
              )}

              <div className={styles.cardActions}>
                <button
                  className={styles.activateBtn}
                  onClick={() => handleActivate(name)}
                  disabled={isActivating}
                >
                  {isActivating ? '✓ Activated' : 'Activate'}
                </button>
                <button
                  className={styles.deleteBtn}
                  onClick={() => onDelete(name)}
                  title="Delete scene"
                >✕</button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
