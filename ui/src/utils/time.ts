export function elapsedLabel(isoString: string): string {
  const ms = Date.now() - new Date(isoString.replace(' ', 'T')).getTime()
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  return `${Math.floor(m / 60)}h ${m % 60}m`
}
