import { useEffect, useState } from 'react'
import type { ThemeMode } from './types'

export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>(() => (typeof localStorage === 'undefined' ? 'system' : (localStorage.getItem('schemasprint-theme') as ThemeMode | null) ?? 'system'))
  useEffect(() => { const root = document.documentElement; const systemDark = typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches; root.dataset.theme = mode === 'dark' || (mode === 'system' && systemDark) ? 'dark' : 'light'; if (typeof localStorage !== 'undefined') localStorage.setItem('schemasprint-theme', mode) }, [mode])
  return { mode, setMode }
}
