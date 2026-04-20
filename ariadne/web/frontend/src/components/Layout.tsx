/**
 * Layout — Sidebar + main content wrapper with theme + language switcher
 */

import { useState, useEffect } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { setLocale, LOCALES, t, type Locale } from '../i18n';
import { configApi } from '../api/ariadne';

const VERSION = 'v0.6.2';

// Flag image map — PNG files in /assets/flags/, 24x24px
const FLAG_MAP: Record<string, string> = {
  en: '/assets/flags/en.png',
  zh_CN: '/assets/flags/zh_CN.png',
  zh_TW: '/assets/flags/zh_TW.png',
  ja: '/assets/flags/ja.png',
  fr: '/assets/flags/fr.png',
  es: '/assets/flags/es.png',
  ru: '/assets/flags/ru.png',
  ar: '/assets/flags/ar.png',
};

const navItems = [
  { path: '/', label: 'nav.home', icon: '⌂' },
  { path: '/search', label: 'nav.search', icon: '🔍' },
  { path: '/memory', label: 'nav.memory', icon: '💾' },
  { path: '/ingest', label: 'nav.ingest', icon: '📥' },
  { path: '/summarize', label: 'nav.summarize', icon: '📝' },
  { path: '/graph', label: 'nav.graph', icon: '🕸️' },
  { path: '/settings', label: 'nav.settings', icon: '⚙️' },
];

export default function Layout() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('ariadne-theme') as 'light' | 'dark') || 'light';
  });
  const [locale, setLocaleState] = useState<Locale>(() => {
    const saved = localStorage.getItem('ariadne_locale') as Locale | null;
    return (saved && LOCALES.some(l => l.code === saved)) ? saved : 'en';
  });
  const [showLangMenu, setShowLangMenu] = useState(false);

  // Close menu on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest('.lang-switcher')) {
        setShowLangMenu(false);
      }
    }
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  // Apply theme and direction to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.dir = LOCALES.find(l => l.code === locale)?.dir ?? 'ltr';
    localStorage.setItem('ariadne-theme', theme);
  }, [theme, locale]);

  // Listen for locale changes from Settings page or other components
  useEffect(() => {
    function handleLocaleChange() {
      const saved = localStorage.getItem('ariadne_locale') as Locale | null;
      if (saved && LOCALES.some(l => l.code === saved)) {
        setLocaleState(saved);
      }
    }
    window.addEventListener('localechange', handleLocaleChange);
    return () => window.removeEventListener('localechange', handleLocaleChange);
  }, []);

  function toggleTheme() {
    setTheme(t => t === 'light' ? 'dark' : 'light');
  }

  async function handleLanguageChange(code: Locale) {
    setLocale(code);
    setLocaleState(code);
    setShowLangMenu(false);
    // Sync with backend
    try {
      await configApi.setLanguage(code);
    } catch {}
  }

  const currentFlag = FLAG_MAP[locale] ?? '/assets/flags/en.png';

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
          {/* Language switcher with flag */}
          <div className="lang-switcher">
            <button
              className="lang-btn"
              onClick={(e) => { e.stopPropagation(); setShowLangMenu(!showLangMenu); }}
              title={t('settings.language')}
            >
              <img src={currentFlag} alt={locale} className="flag-icon" />
            </button>
            {showLangMenu && (
              <div className="lang-menu">
                {LOCALES.map(l => (
                  <button
                    key={l.code}
                    className={`lang-menu-item ${l.code === locale ? 'active' : ''}`}
                    onClick={() => handleLanguageChange(l.code)}
                  >
                    <img src={FLAG_MAP[l.code] ?? '/assets/flags/en.png'} alt={l.code} className="flag-icon" /> {l.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={theme === 'light' ? '🌙' : '☀️'}
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
