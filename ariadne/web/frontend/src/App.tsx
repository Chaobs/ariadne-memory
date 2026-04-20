/**
 * Ariadne Web UI — Main App Component with React Router + i18n
 */

import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Search from './pages/Search';
import Memory from './pages/Memory';
import Ingest from './pages/Ingest';
import Graph from './pages/Graph';
import Settings from './pages/Settings';
import { initI18n } from './i18n';

// Initialize i18n at app startup
initI18n();

// Force re-render on locale change
function useLocale() {
  const [locale, setLocale] = useState(() => localStorage.getItem('ariadne_locale') || 'en');
  useEffect(() => {
    function handle() {
      setLocale(localStorage.getItem('ariadne_locale') || 'en');
    }
    window.addEventListener('localechange', handle);
    return () => window.removeEventListener('localechange', handle);
  }, []);
  return locale;
}

export default function App() {
  // This state change forces React to re-render all components when locale changes
  useLocale();

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="search" element={<Search />} />
          <Route path="memory" element={<Memory />} />
          <Route path="ingest" element={<Ingest />} />
          <Route path="graph" element={<Graph />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
