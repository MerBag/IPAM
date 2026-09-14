export type Theme = 'light' | 'dark'

const THEME_STORAGE_KEY = 'merbag.theme'
const DARK_THEME_COLOR = '#102029'
const LIGHT_THEME_COLOR = '#ffffff'

function isTheme(value: string | null): value is Theme {
  return value === 'light' || value === 'dark'
}

export function getPreferredTheme(): Theme {
  try {
    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY)
    if (isTheme(storedTheme)) return storedTheme
  } catch {
    // Storage may be unavailable in hardened browser contexts.
  }

  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function getActiveTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

export function applyTheme(theme: Theme, persist = true) {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
  document.querySelector('meta[name="theme-color"]')?.setAttribute(
    'content',
    theme === 'dark' ? DARK_THEME_COLOR : LIGHT_THEME_COLOR,
  )

  if (persist) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch {
      // The selected theme still applies for the current page.
    }
  }
}

export function initializeTheme() {
  applyTheme(getPreferredTheme(), false)
}
