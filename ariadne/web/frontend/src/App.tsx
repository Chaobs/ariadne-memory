/**
 * Ariadne Web UI — Main App Component with React Router
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Search from './pages/Search';
import Memory from './pages/Memory';
import Ingest from './pages/Ingest';
import Graph from './pages/Graph';
import Settings from './pages/Settings';

export default function App() {
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