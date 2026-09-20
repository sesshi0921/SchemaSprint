import { useEffect, useMemo, useState } from 'react'
import type { Locale } from './types'

export const supportedLocales: Locale[] = ['en', 'ja', 'zh-CN', 'ko', 'es', 'pt-BR']
const messages: Record<Locale, Record<string, string>> = {
  en: { today: 'Today', library: 'Problem library', dashboard: 'Dashboard', notices: 'Notices', settings: 'Settings', signIn: 'Sign in', signOut: 'Sign out', retry: 'Try again', loading: 'Loading…', save: 'Save draft', submit: 'Submit', saved: 'Saved locally', saving: 'Saving…', savedServer: 'Saved to server', saveFailed: 'Could not save. Your local copy is preserved.', onboarding: 'Finish setup', language: 'Language', openWorkspace: 'Open workspace' },
  ja: { today: '今日', library: '問題一覧', dashboard: 'ダッシュボード', notices: '通知', settings: '設定', signIn: 'ログイン', signOut: 'ログアウト', retry: '再試行', loading: '読み込み中…', save: '下書きを保存', submit: '提出', saved: '端末に保存済み', saving: '保存中…', savedServer: 'サーバーに保存済み', saveFailed: '保存できませんでした。ローカルコピーは保持されています。', onboarding: '初期設定を完了', language: '言語', openWorkspace: 'ワークスペースを開く' },
  'zh-CN': { today: '今日', library: '题目库', dashboard: '仪表盘', notices: '通知', settings: '设置', signIn: '登录', signOut: '退出登录', retry: '重试', loading: '加载中…', save: '保存草稿', submit: '提交', saved: '已保存到本机', saving: '保存中…', savedServer: '已保存到服务器', saveFailed: '保存失败，本地副本仍保留。', onboarding: '完成设置', language: '语言', openWorkspace: '打开工作区' },
  ko: { today: '오늘', library: '문제 목록', dashboard: '대시보드', notices: '알림', settings: '설정', signIn: '로그인', signOut: '로그아웃', retry: '다시 시도', loading: '불러오는 중…', save: '초안 저장', submit: '제출', saved: '기기에 저장됨', saving: '저장 중…', savedServer: '서버에 저장됨', saveFailed: '저장하지 못했습니다. 로컬 사본은 유지됩니다.', onboarding: '설정 완료', language: '언어', openWorkspace: '워크스페이스 열기' },
  es: { today: 'Hoy', library: 'Biblioteca', dashboard: 'Panel', notices: 'Avisos', settings: 'Ajustes', signIn: 'Iniciar sesión', signOut: 'Cerrar sesión', retry: 'Reintentar', loading: 'Cargando…', save: 'Guardar borrador', submit: 'Enviar', saved: 'Guardado localmente', saving: 'Guardando…', savedServer: 'Guardado en el servidor', saveFailed: 'No se pudo guardar. La copia local se conserva.', onboarding: 'Completar configuración', language: 'Idioma', openWorkspace: 'Abrir espacio de trabajo' },
  'pt-BR': { today: 'Hoje', library: 'Biblioteca', dashboard: 'Painel', notices: 'Avisos', settings: 'Configurações', signIn: 'Entrar', signOut: 'Sair', retry: 'Tentar novamente', loading: 'Carregando…', save: 'Salvar rascunho', submit: 'Enviar', saved: 'Salvo localmente', saving: 'Salvando…', savedServer: 'Salvo no servidor', saveFailed: 'Não foi possível salvar. A cópia local foi preservada.', onboarding: 'Concluir configuração', language: 'Idioma', openWorkspace: 'Abrir espaço de trabalho' },
}
export function initialLocale(): Locale { const value = typeof localStorage === 'undefined' ? null : localStorage.getItem('schemasprint-locale'); return supportedLocales.includes(value as Locale) ? value as Locale : 'en' }
export function t(locale: Locale, key: string, fallback?: string) { return messages[locale]?.[key] ?? messages.en[key] ?? fallback ?? key }
export function useLocale(preferred?: Locale | null) {
  const [locale, setLocale] = useState<Locale>(() => preferred ?? initialLocale())
  useEffect(() => { if (preferred) setLocale(preferred) }, [preferred])
  useEffect(() => { if (typeof localStorage !== 'undefined') localStorage.setItem('schemasprint-locale', locale); document.documentElement.lang = locale }, [locale])
  return useMemo(() => ({ locale, setLocale }), [locale])
}
