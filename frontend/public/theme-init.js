(() => {
  const isTheme = (value) => value === 'light' || value === 'dark'

  try {
    const storedTheme = localStorage.getItem('merbag.theme')
    const theme = isTheme(storedTheme)
      ? storedTheme
      : window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'

    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      'content',
      theme === 'dark' ? '#102029' : '#ffffff',
    )
  } catch {
    document.documentElement.dataset.theme = 'light'
  }
})()
