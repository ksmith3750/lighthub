import { useState, useEffect } from 'react'
import { api } from '../api.js'
import styles from './SettingsPage.module.css'

export default function SettingsPage({ onSave }) {
  const [hueBridgeIp, setHueBridgeIp] = useState('')
  const [goveeKey, setGoveeKey] = useState('')
  const [status, setStatus] = useState(null)
  const [health, setHealth] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.getConfig().then(cfg => {
      setHueBridgeIp(cfg.hue_bridge_ip || '')
    })
    api.health().then(setHealth)
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave({ hue_bridge_ip: hueBridgeIp, govee_api_key: goveeKey || undefined })
      setStatus({ type: 'success', msg: 'Settings saved successfully.' })
      setGoveeKey('')
    } catch {
      setStatus({ type: 'error', msg: 'Failed to save settings.' })
    } finally {
      setSaving(false)
      setTimeout(() => setStatus(null), 3000)
    }
  }

  return (
    <div className={styles.page}>
      <div>
        <h1 className={styles.title}>Settings</h1>
        <p className={styles.sub}>Configure your smart home integrations</p>
      </div>

      {health && (
        <div className={styles.healthCard}>
          <div className={styles.healthTitle}>Backend status</div>
          <div className={styles.healthGrid}>
            <div className={styles.healthItem}>
              <span className={`${styles.healthDot} ${health.kasa_lib ? styles.dotGreen : styles.dotRed}`} />
              <span>python-kasa {health.kasa_lib ? 'installed' : 'missing'}</span>
            </div>
            <div className={styles.healthItem}>
              <span className={`${styles.healthDot} ${health.hue_lib ? styles.dotGreen : styles.dotRed}`} />
              <span>phue {health.hue_lib ? 'installed' : 'missing'}</span>
            </div>
            <div className={styles.healthItem}>
              <span className={`${styles.healthDot} ${health.govee_lib ? styles.dotGreen : styles.dotRed}`} />
              <span>httpx {health.govee_lib ? 'installed' : 'missing'}</span>
            </div>
            <div className={styles.healthItem}>
              <span className={styles.healthDot} style={{background:'var(--govee-color)'}} />
              <span>{health.devices_loaded} devices loaded</span>
            </div>
          </div>
          {(!health.kasa_lib || !health.hue_lib || !health.govee_lib) && (
            <code className={styles.installHint}>pip install -r requirements.txt</code>
          )}
        </div>
      )}

      <div className={styles.section}>
        <div className={styles.sectionTitle}>
          <span className={styles.brandDot} style={{background:'var(--hue-color)'}} />
          Philips Hue
        </div>
        <p className={styles.sectionDesc}>
          Enter your Hue Bridge IP address. Find it in the Hue app under Settings → My Hue system, or check your router's connected devices. The first time you connect, press the link button on top of the bridge.
        </p>
        <div className={styles.field}>
          <label className={styles.label}>Bridge IP address</label>
          <input
            className={styles.input}
            placeholder="e.g. 192.168.1.42"
            value={hueBridgeIp}
            onChange={e => setHueBridgeIp(e.target.value)}
          />
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionTitle}>
          <span className={styles.brandDot} style={{background:'var(--govee-color)'}} />
          Govee
        </div>
        <p className={styles.sectionDesc}>
          Get your free API key from the Govee Home app: Settings → About us → Apply for API key. It arrives by email within a few minutes.
        </p>
        <div className={styles.field}>
          <label className={styles.label}>API key</label>
          <input
            className={styles.input}
            type="password"
            placeholder="Paste your Govee API key..."
            value={goveeKey}
            onChange={e => setGoveeKey(e.target.value)}
          />
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionTitle}>
          <span className={styles.brandDot} style={{background:'var(--kasa-color)'}} />
          Kasa (TP-Link)
        </div>
        <p className={styles.sectionDesc}>
          Kasa devices are auto-discovered on your local network — no configuration needed. Make sure your Mac is on the same Wi-Fi network as your plugs. Run device discovery from the sidebar to scan.
        </p>
      </div>

      {status && (
        <div className={`${styles.status} ${styles[status.type]}`}>{status.msg}</div>
      )}

      <button className={styles.saveBtn} onClick={handleSave} disabled={saving}>
        {saving ? 'Saving...' : 'Save settings'}
      </button>
    </div>
  )
}
