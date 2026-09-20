export const theme = {
  colors: { ink: '#1c1d23', inkMuted: '#62646f', page: '#f4f5f7', surface: '#ffffff', surfaceAlt: '#eceef2', border: '#d8dbe2', borderStrong: '#b8bbc6', brand: '#5654A2', brandDeep: '#3e3d78', brandSoft: '#e9e8f8', gold: '#b37b12', success: '#18794e', successSoft: '#e2f3e9', warning: '#9b5b00', warningSoft: '#fff1d6', danger: '#b42318', dangerSoft: '#fde8e7', editor: '#20242b', editorPanel: '#272b33', editorPanelAlt: '#242830', editorNode: '#2a2f38', editorBorder: '#57606d', editorInk: '#f1f3f8', editorMuted: '#9aa1af', relation: '#c99735', relationInk: '#f2d48c' },
  space: { 1: '0.25rem', 2: '0.5rem', 3: '0.75rem', 4: '1rem', 5: '1.25rem', 6: '1.5rem', 8: '2rem', 10: '2.5rem', 12: '3rem' },
  radius: { sm: '6px', md: '10px', lg: '16px', pill: '999px' },
  shadow: { subtle: '0 1px 2px rgb(25 27 36 / 7%)', raised: '0 14px 35px rgb(25 27 36 / 12%)' },
} as const
export type ThemeMode = 'light' | 'dark' | 'system'
export const localeLabels = { en: 'English', ja: '日本語', 'zh-CN': '简体中文', ko: '한국어', es: 'Español', 'pt-BR': 'Português' } as const
