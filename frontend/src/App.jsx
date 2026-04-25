import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Register from './pages/Register';
import AssetDetail from './pages/AssetDetail';
import EvidenceViewer from './pages/EvidenceViewer';
import AssetScans from './pages/AssetScans';
import EvidenceBundles from './pages/EvidenceBundles';
import './index.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="register" element={<Register />} />
          <Route path="scans" element={<AssetScans />} />
          <Route path="bundles" element={<EvidenceBundles />} />
          <Route path="asset/:id" element={<AssetDetail />} />
          <Route path="evidence/:id" element={<EvidenceViewer />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
