import { useState, useCallback } from 'react'
import styles from './DeviceCard.module.css'

const BRAND_COLORS = { kasa: '#4ea8de', hue: '#c084fc', govee: '#4ade80' }
const BRAND_LABELS = { kasa: 'Kasa', hue: 'Hue', govee: 'Govee' }
const TYPE_ICONS = { plug: '⏻', bulb: '◉', strip: '▬', floor: '🕯' }

const PRESET_COLORS = [
  { label: 'Warm', r: 255, g: 180, b: 80 },
  { label: 'Cool', r: 180, g: 210, b: 255 },
  { label: 'Daylight', r: 255, g: 248, b: 220 },
  { label: 'Pink', r: 255, g: 100, b: 180 },
  { label: 'Blue', r: 40, g: 80, b: 255 },
  { label: 'Green', r: 60, g: 220, b: 120 },
  { label: 'Purple', r: 160, g: 60, b: 255 },
  { label: 'Red', r: 255, g: 50, b: 50 },
]

function rgbToHex({ r, g, b }) {
  return '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('')
}

export default function DeviceCard({ device, onCommand, rooms, roomLabels, onAssignRoom, onRename }) {
  const [expanded, setExpanded] = useState(false)
  const [localBrightness, setLocalBrightness] = useState(device.brightness ?? 100)
  const [editingName, setEditingName] = useState(false)
  const [nameInput, setNameInput] = useState(device.name)

  const commitName = useCallback(() => {
    setEditingName(false)
    const trimmed = nameInput.trim()
    if (trimmed && trimmed !== device.name) onRename(device.id, trimmed)
    else setNameInput(device.name)
  }, [nameInput, device.id, device.name, onRename])

  const toggle = useCallback((e) => {
    e.stopPropagation()
    onCommand(device.id, { on: !device.on })
  }, [device, onCommand])

  const setBrightness = useCallback((val) => {
    setLocalBrightness(val)
    onCommand(device.id, { brightness: val })
  }, [device.id, onCommand])

  const setColor = useCallback((color) => {
    onCommand(device.id, { color, on: true })
  }, [device.id, onCommand])

  const brandColor = BRAND_COLORS[device.brand] || '#888'
  const hasColor = device.brand !== 'kasa'
  const hasColorPicker = device.brand === 'govee' || (device.brand === 'hue' && device.type === 'bulb')
  const hasBrightness = device.brand !== 'kasa'
  const currentColor = device.color ? rgbToHex(device.color) : '#ffffff'

  return (
    <div
      className={`${styles.card} ${device.on ? styles.on : styles.off} ${expanded ? styles.expanded : ''}`}
      onClick={() => setExpanded(e => !e)}
    >
      {/* Glow when on */}
      {device.on && (
        <div className={styles.glow} style={{
          background: hasColor
            ? `radial-gradient(ellipse at 50% 0%, ${currentColor}22 0%, transparent 70%)`
            : `radial-gradient(ellipse at 50% 0%, ${brandColor}15 0%, transparent 70%)`
        }} />
      )}

      <div className={styles.header}>
        <div className={styles.iconWrap} style={{
          background: device.on
            ? (hasColor ? currentColor + '30' : brandColor + '22')
            : 'var(--bg-hover)',
          borderColor: device.on ? (hasColor ? currentColor + '60' : brandColor + '40') : 'transparent'
        }}>
          <span style={{
            color: device.on ? (hasColor ? currentColor : brandColor) : 'var(--text-tertiary)',
            fontSize: 18
          }}>{TYPE_ICONS[device.type] || '◉'}</span>
        </div>

        <button
          className={`${styles.toggle} ${device.on ? styles.toggleOn : ''}`}
          onClick={toggle}
          style={{ '--toggle-accent': brandColor }}
        />
      </div>

      <div className={styles.name}>{device.name}</div>
      <div className={styles.meta}>
        <span className={styles.brandTag} style={{ color: brandColor, background: brandColor + '18' }}>
          {BRAND_LABELS[device.brand]}
        </span>
        <span className={styles.status}>
          {device.on
            ? (hasBrightness ? `${localBrightness}%` : 'on')
            : 'off'}
        </span>
      </div>

      {/* Expanded controls */}
      {expanded && (
        <div className={styles.controls} onClick={e => e.stopPropagation()}>
          {hasBrightness && (
            <div className={styles.sliderRow}>
              <span className={styles.sliderLabel}>Brightness</span>
              <div className={styles.sliderWrap}>
                <input
                  type="range" min="1" max="100"
                  value={localBrightness}
                  className={styles.slider}
                  style={{ '--accent': hasColor ? currentColor : brandColor }}
                  onChange={e => setLocalBrightness(+e.target.value)}
                  onMouseUp={e => setBrightness(+e.target.value)}
                  onTouchEnd={e => setBrightness(+e.target.value)}
                />
                <span className={styles.sliderVal}>{localBrightness}%</span>
              </div>
            </div>
          )}

          {hasColorPicker && (
            <div className={styles.colorSection}>
              <span className={styles.sliderLabel}>Color</span>
              <div className={styles.colorGrid}>
                {PRESET_COLORS.map(color => (
                  <button
                    key={color.label}
                    className={styles.colorDot}
                    style={{ background: rgbToHex(color) }}
                    title={color.label}
                    onClick={() => setColor({ r: color.r, g: color.g, b: color.b })}
                  />
                ))}
                <input
                  type="color"
                  className={styles.colorPicker}
                  value={currentColor}
                  onChange={e => {
                    const hex = e.target.value
                    const r = parseInt(hex.slice(1, 3), 16)
                    const g = parseInt(hex.slice(3, 5), 16)
                    const b = parseInt(hex.slice(5, 7), 16)
                    setColor({ r, g, b })
                  }}
                  title="Custom color"
                />
              </div>
            </div>
          )}

          <div className={styles.sliderRow}>
            <span className={styles.sliderLabel}>Label</span>
            {editingName ? (
              <input
                className={styles.nameInput}
                value={nameInput}
                autoFocus
                onChange={e => setNameInput(e.target.value)}
                onBlur={commitName}
                onKeyDown={e => { if (e.key === 'Enter') commitName(); if (e.key === 'Escape') { setEditingName(false); setNameInput(device.name) } }}
                onClick={e => e.stopPropagation()}
              />
            ) : (
              <span
                className={styles.nameEdit}
                onClick={e => { e.stopPropagation(); setEditingName(true) }}
              >{device.name}</span>
            )}
          </div>

          {rooms && (
            <div className={styles.sliderRow}>
              <span className={styles.sliderLabel}>Room</span>
              <select
                className={styles.roomSelect}
                value={device.room || ''}
                onChange={e => onAssignRoom(device.id, e.target.value)}
              >
                <option value="">Unassigned</option>
                {rooms.map(r => (
                  <option key={r} value={r}>{roomLabels[r]}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
