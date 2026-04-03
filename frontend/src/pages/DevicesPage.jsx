import { useState } from 'react'
import DeviceCard from '../components/DeviceCard.jsx'
import styles from './DevicesPage.module.css'

export default function DevicesPage({
  devices, allDevices, selectedRoom, rooms, roomLabels,
  onCommand, onRoomCommand, onAssignRoom, onRename, scenes, onActivateScene
}) {
  const [filter, setFilter] = useState('all') // all | kasa | hue | govee

  const filtered = filter === 'all'
    ? devices
    : devices.filter(d => d.brand === filter)

  // Group by room for "all rooms" view, or flat for single room
  const grouped = selectedRoom === 'all'
    ? rooms.reduce((acc, room) => {
        const roomDevices = filtered.filter(d => d.room === room)
        if (roomDevices.length > 0) acc[room] = roomDevices
        return acc
      }, {
        ...(filtered.some(d => !d.room) ? { unassigned: filtered.filter(d => !d.room) } : {})
      })
    : { [selectedRoom]: filtered }

  const sceneList = Object.entries(scenes).slice(0, 6)

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>
            {selectedRoom === 'all' ? 'All devices' : roomLabels[selectedRoom]}
          </h1>
          <p className={styles.sub}>
            {devices.filter(d => d.on).length} of {devices.length} on
          </p>
        </div>
        <div className={styles.headerActions}>
          {selectedRoom !== 'all' && (
            <>
              <button
                className={styles.actionBtn}
                onClick={() => onRoomCommand(selectedRoom, { on: true })}
              >All on</button>
              <button
                className={styles.actionBtn}
                onClick={() => onRoomCommand(selectedRoom, { on: false })}
              >All off</button>
            </>
          )}
        </div>
      </div>

      {/* Quick scenes */}
      {sceneList.length > 0 && (
        <div className={styles.scenesRow}>
          {sceneList.map(([name, scene]) => (
            <button
              key={name}
              className={styles.sceneChip}
              onClick={() => onActivateScene(name)}
            >
              {scene.icon} {name}
            </button>
          ))}
        </div>
      )}

      {/* Brand filter */}
      <div className={styles.filterRow}>
        {['all', 'kasa', 'hue', 'govee'].map(f => (
          <button
            key={f}
            className={`${styles.filterBtn} ${filter === f ? styles.filterActive : ''}`}
            onClick={() => setFilter(f)}
          >
            {f === 'all' ? 'All brands' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Device groups */}
      {Object.entries(grouped).map(([room, roomDevices]) => (
        <div key={room} className={styles.group}>
          <div className={styles.groupHeader}>
            <span className={styles.groupLabel}>
              {room === 'unassigned' ? 'Unassigned' : roomLabels[room] || room}
            </span>
            <span className={styles.groupMeta}>
              {roomDevices.filter(d => d.on).length}/{roomDevices.length} on
            </span>
            <div className={styles.groupActions}>
              {room !== 'unassigned' && (
                <>
                  <button className={styles.miniBtn}
                    onClick={() => onRoomCommand(room, { on: true })}>On</button>
                  <button className={styles.miniBtn}
                    onClick={() => onRoomCommand(room, { on: false })}>Off</button>
                </>
              )}
            </div>
          </div>
          <div className={styles.grid}>
            {roomDevices.map(device => (
              <DeviceCard
                key={device.id}
                device={device}
                onCommand={onCommand}
                rooms={rooms}
                roomLabels={roomLabels}
                onAssignRoom={onAssignRoom}
                onRename={onRename}
              />
            ))}
          </div>
        </div>
      ))}

      {filtered.length === 0 && (
        <div className={styles.empty}>
          <p>No devices found.</p>
          <p className={styles.emptyHint}>Try running device discovery from the sidebar.</p>
        </div>
      )}
    </div>
  )
}
