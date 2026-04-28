import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Register from './pages/Register';
import AssetDetail from './pages/AssetDetail';
import EvidenceViewer from './pages/EvidenceViewer';
import AssetScans from './pages/AssetScans';
import EvidenceBundles from './pages/EvidenceBundles';
import Login from './pages/Login';
import { AUTH_STORAGE_KEY, getCurrentUser } from './lib/auth';
import './index.css';

function AppShell() {
  const navigate = useNavigate();
  const [user, setUser] = useState(() => getCurrentUser());

  useEffect(() => {
    if (user) {
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    }
  }, [user]);

  const handleLogin = (nextUser) => {
    const normalizedUser = {
      ...nextUser,
      ownerId: nextUser.ownerId || nextUser.email.toLowerCase(),
    };
    setUser(normalizedUser);
    navigate('/');
  };

  const handleLogout = () => {
    setUser(null);
    navigate('/login');
  };

  return (
    <Routes>
      <Route path="/login" element={<Login user={user} onLogin={handleLogin} />} />
      <Route path="/" element={<Layout user={user} onLogout={handleLogout} />}>
        <Route index element={<Dashboard />} />
        <Route path="register" element={<Register />} />
        <Route path="scans" element={<AssetScans />} />
        <Route path="bundles" element={<EvidenceBundles />} />
        <Route path="asset/:id" element={<AssetDetail />} />
        <Route path="evidence/:id" element={<EvidenceViewer />} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}

export default App;
