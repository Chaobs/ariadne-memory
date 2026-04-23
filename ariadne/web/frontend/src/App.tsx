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
import Summarize from './pages/Summarize';
import Graph from './pages/Graph';
import Settings from './pages/Settings';
import Wiki from './pages/Wiki';
import { initI18n } from './i18n';

// Initialize i18n at app startup
initI18n();

// Force re-render on locale change using a version counter
let localeVersion = 0;
window.addEventListener('localechange', () => { localeVersion++; });

export default function App() {
  // This state change forces React to re-render all components when locale changes
  const [, forceRender] = useState(0);

  useEffect(() => {
    function handle() {
      localeVersion++;
      forceRender(n => n + 1);
    }
    window.addEventListener('localechange', handle);
    return () => window.removeEventListener('localechange', handle);
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="search" element={<Search />} />
          <Route path="memory" element={<Memory />} />
          <Route path="ingest" element={<Ingest />} />
          <Route path="summarize" element={<Summarize />} />
          <Route path="wiki" element={<Wiki />} />
          <Route path="graph" element={<Graph />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
