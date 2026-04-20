/**
 * Layout — Sidebar + main content wrapper with theme + language switcher
 */

import { useState, useEffect } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { initI18n, setLocale, getLocale, LOCALES, t, type Locale } from '../i18n';
import { configApi } from '../api/ariadne';

const VERSION = 'v0.6.1';

const navItems = [
  { path: '/', label: 'nav.home', icon: '⌂' },
  { path: '/search', label: 'nav.search', icon: '🔍' },
  { path: '/memory', label: 'nav.memory', icon: '💾' },
  { path: '/ingest', label: 'nav.ingest', icon: '📥' },
  { path: '/graph', label: 'nav.graph', icon: '🕸️' },
  { path: '/settings', label: 'nav.settings', icon: '⚙️' },
];

export default function Layout() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('ariadne-theme') as 'light' | 'dark') || 'light';
  });
  const [locale, setLocaleState] = useState<Locale>(getLocale());
  const [showLangMenu, setShowLangMenu] = useState(false);

  // Initialize i18n on mount
  useEffect(() => {
    const saved = localStorage.getItem('ariadne_locale') as Locale | null;
    if (saved && LOCALES.some(l => l.code === saved)) {
      setLocale(saved as Locale);
      setLocaleState(saved as Locale);
    } else {
      initI18n();
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.dir = LOCALES.find(l => l.code === locale)?.dir ?? 'ltr';
    localStorage.setItem('ariadne-theme', theme);
  }, [theme, locale]);

  // Listen for locale changes
  useEffect(() => {
    function handleLocaleChange(e: CustomEvent<{ locale: Locale }>) {
      setLocaleState(e.detail.locale);
      setShowLangMenu(false);
    }
    window.addEventListener('localechange', handleLocaleChange as EventListener);
    return () => window.removeEventListener('localechange', handleLocaleChange as EventListener);
  }, []);

  function toggleTheme() {
    setTheme(t => t === 'light' ? 'dark' : 'light');
  }

  function handleLanguageChange(code: Locale) {
    setLocale(code);
    setLocaleState(code);
    setShowLangMenu(false);
    // Sync with backend
    configApi.setLanguage(code).catch(() => {});
  }

  const currentLocaleInfo = LOCALES.find(l => l.code === locale) ?? LOCALES[0];

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <span className="logo-icon">🧵</span>
          <span className="logo-text">Ariadne</span>
        </div>
        <nav className="sidebar-nav">
          {navItems.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              end={item.path === '/'}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{t(item.label)}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          {/* Language switcher */}
          <div className="lang-switcher" style={{ position: 'relative' }}>
            <button
              className="lang-btn"
              onClick={() => setShowLangMenu(!showLangMenu)}
              title="Change language"
            >
              🌐 {currentLocaleInfo.code.toUpperCase().replace('_', '')}
            </button>
            {showLangMenu && (
              <div className="lang-menu">
                {LOCALES.map(l => (
                  <button
                    key={l.code}
                    className={`lang-menu-item ${l.code === locale ? 'active' : ''}`}
                    onClick={() => handleLanguageChange(l.code)}
                  >
                    {l.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          >
            {theme === 'light' ? '🌙' : '☀️'}
          </button>
          <span className="version">{VERSION}</span>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
