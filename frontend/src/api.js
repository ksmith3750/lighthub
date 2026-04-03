const BASE = '/api'

async function req(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}`)
  return res.json()
}

export const api = {
  // Devices
  getDevices: () => req('GET', '/devices'),
  discoverDevices: () => req('POST', '/devices/discover'),
  commandDevice: (id, cmd) => req('POST', `/devices/${id}/command`, cmd),
  commandRoom: (room, cmd) => req('POST', `/rooms/${room}/command`, cmd),
  assignRoom: (id, room) => req('PUT', `/devices/${id}/room`, { room }),
  renameDevice: (id, name) => req('PUT', `/devices/${id}/name`, { name }),

  // Scenes
  getScenes: () => req('GET', '/scenes'),
  activateScene: (name) => req('POST', `/scenes/${encodeURIComponent(name)}/activate`),
  createScene: (scene) => req('POST', '/scenes', scene),
  deleteScene: (name) => req('DELETE', `/scenes/${encodeURIComponent(name)}`),

  // Schedules
  getSchedules: () => req('GET', '/schedules'),
  createSchedule: (s) => req('POST', '/schedules', s),
  updateSchedule: (id, s) => req('PUT', `/schedules/${id}`, s),
  deleteSchedule: (id) => req('DELETE', `/schedules/${id}`),

  // Config
  getConfig: () => req('GET', '/config'),
  updateConfig: (c) => req('PUT', '/config', c),
  health: () => req('GET', '/health'),
}
