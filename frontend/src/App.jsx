import { useState, useEffect, useCallback } from 'react'
import { api } from './api.js'
import Sidebar from './components/Sidebar.jsx'
import DevicesPage from './pages/DevicesPage.jsx'
import ScenesPage from './pages/ScenesPage.jsx'
import SchedulesPage from './pages/SchedulesPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import styles from './App.module.css'

const ROOMS = ['living', 'bedroom', 'kitchen', 'office', 'outdoor']
const ROOM_LABELS = {
  living: 'Living room', bedroom: 'Bedroom',
  kitchen: 'Kitchen', office: 'Office', outdoor: 'Outdoor'
}

export default function App() {
  const [page, setPage] = useState('devices')
  const [devices, setDevices] = useState([])
  const [scenes, setScenes] = useState({})
  const [schedules, setSchedules] = useState([])
  const [selectedRoom, setSelectedRoom] = useState('all')
  const [loading, setLoading] = useState(true)
  const [discovering, setDiscovering] = useState(false)
  const [notification, setNotification] = useState(null)

  const notify = useCallback((msg, type = 'success') => {
    setNotification({ msg, type })
    setTimeout(() => setNotification(null), 2500)
  }, [])

  const loadAll = useCallback(async () => {
    try {
      const [devData, sceneData, schedData] = await Promise.all([
        api.getDevices(),
        api.getScenes(),
        api.getSchedules(),
      ])
      setDevices(devData.devices || [])
      setScenes(sceneData.scenes || {})
      setSchedules(schedData.schedules || [])
    } catch (e) {
      notify('Could not connect to backend — is it running?', 'error')
    } finally {
      setLoading(false)
    }
  }, [notify])

  useEffect(() => { loadAll() }, [loadAll])

  const handleCommand = useCallback(async (deviceId, cmd) => {
    // Optimistic update
    setDevices(prev => prev.map(d => d.id === deviceId ? { ...d, ...cmd } : d))
    try {
      await api.commandDevice(deviceId, cmd)
    } catch {
      notify('Command failed', 'error')
      loadAll()
    }
  }, [notify, loadAll])

  const handleRoomCommand = useCallback(async (room, cmd) => {
    setDevices(prev => prev.map(d => d.room === room ? { ...d, ...cmd } : d))
    try {
      await api.commandRoom(room, cmd)
    } catch {
      notify('Room command failed', 'error')
    }
  }, [notify])

  const handleDiscover = useCallback(async () => {
    setDiscovering(true)
    try {
      const data = await api.discoverDevices()
      setDevices(data.devices || [])
      notify(`Discovered ${data.discovered} devices`)
    } catch {
      notify('Discovery failed', 'error')
    } finally {
      setDiscovering(false)
    }
  }, [notify])

  const handleActivateScene = useCallback(async (name) => {
    try {
      await api.activateScene(name)
      notify(`Scene "${name}" activated`)
      loadAll()
    } catch {
      notify('Scene activation failed', 'error')
    }
  }, [notify, loadAll])

  // Compute room summaries
  const roomSummary = ROOMS.reduce((acc, room) => {
    const roomDevices = devices.filter(d => d.room === room)
    const onCount = roomDevices.filter(d => d.on).length
    acc[room] = { total: roomDevices.length, on: onCount }
    return acc
  }, {})

  const filteredDevices = selectedRoom === 'all'
    ? devices
    : devices.filter(d => d.room === selectedRoom)

  if (loading) {
    return (
      <div className={styles.loadingScreen}>
        <div className={styles.loadingOrb} />
        <p>Connecting to LightHub...</p>
      </div>
    )
  }

  return (
    <div className={styles.app}>
      <Sidebar
        page={page}
        onNavigate={setPage}
        selectedRoom={selectedRoom}
        onSelectRoom={setSelectedRoom}
        roomSummary={roomSummary}
        rooms={ROOMS}
        roomLabels={ROOM_LABELS}
        devices={devices}
        onDiscover={handleDiscover}
        discovering={discovering}
      />

      <main className={styles.main}>
        {notification && (
          <div className={`${styles.notification} ${styles[notification.type]}`}>
            {notification.msg}
          </div>
        )}

        {page === 'devices' && (
          <DevicesPage
            devices={filteredDevices}
            allDevices={devices}
            selectedRoom={selectedRoom}
            rooms={ROOMS}
            roomLabels={ROOM_LABELS}
            onCommand={handleCommand}
            onRoomCommand={handleRoomCommand}
            onAssignRoom={async (id, room) => {
              await api.assignRoom(id, room)
              loadAll()
            }}
            onRename={async (id, name) => {
              await api.renameDevice(id, name)
              loadAll()
            }}
            scenes={scenes}
            onActivateScene={handleActivateScene}
          />
        )}
        {page === 'scenes' && (
          <ScenesPage
            scenes={scenes}
            devices={devices}
            onActivate={handleActivateScene}
            onCreate={async (scene) => {
              await api.createScene(scene)
              notify(`Scene "${scene.name}" saved`)
              loadAll()
            }}
            onDelete={async (name) => {
              await api.deleteScene(name)
              notify(`Scene deleted`)
              loadAll()
            }}
          />
        )}
        {page === 'schedules' && (
          <SchedulesPage
            schedules={schedules}
            scenes={scenes}
            onCreate={async (s) => {
              await api.createSchedule(s)
              notify('Schedule created')
              loadAll()
            }}
            onToggle={async (s) => {
              await api.updateSchedule(s.id, { ...s, enabled: !s.enabled })
              loadAll()
            }}
            onDelete={async (id) => {
              await api.deleteSchedule(id)
              notify('Schedule deleted')
              loadAll()
            }}
          />
        )}
        {page === 'settings' && (
          <SettingsPage onSave={async (cfg) => {
            await api.updateConfig(cfg)
            notify('Settings saved')
          }} />
        )}
      </main>
    </div>
  )
}
