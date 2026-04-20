/**
 * Layout — Sidebar + main content wrapper with theme support
 */

import { useState, useEffect } from 'react';
import { Outlet, NavLink } from 'react-router-dom';

const navItems = [
  { path: '/', label: 'Home', icon: '⌂' },
  { path: '/search', label: 'Search', icon: '🔍' },
  { path: '/memory', label: 'Memory Systems', icon: '💾' },
  { path: '/ingest', label: 'Ingest', icon: '📥' },
  { path: '/graph', label: 'Knowledge Graph', icon: '🕸️' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
];

export default function Layout() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('ariadne-theme') as 'light' | 'dark') || 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('ariadne-theme', theme);
  }, [theme]);

  function toggleTheme() {
    setTheme(t => t === 'light' ? 'dark' : 'light');
  }

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
              <span className="nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="theme-toggle-btn" onClick={toggleTheme} title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}>
            {theme === 'light' ? '🌙' : '☀️'}
          </button>
          <span className="version">v0.6.0</span>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
