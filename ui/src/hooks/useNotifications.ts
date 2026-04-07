// ui/src/hooks/useNotifications.ts
import { useCallback } from 'react'

function canNotify(): boolean {
  return typeof Notification !== 'undefined' && Notification.permission === 'granted'
}

function isHidden(): boolean {
  return typeof document !== 'undefined' && document.visibilityState === 'hidden'
}

export function useNotifications() {
  const requestPermission = useCallback(async () => {
    if (typeof Notification === 'undefined') return
    if (Notification.permission === 'default') {
      await Notification.requestPermission()
    }
  }, [])

  const notify = useCallback((title: string, body?: string) => {
    if (!canNotify() || !isHidden()) return
    new Notification(title, {
      body,
      icon: '/favicon.ico',
      tag: title,
    })
  }, [])

  return { requestPermission, notify }
}
