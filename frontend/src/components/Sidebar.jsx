import React from 'react';
import { NavLink } from 'react-router-dom';
import { Shield, Home, Upload, FileText, Layers } from 'lucide-react';

const Sidebar = () => {
  return (
    <aside className="sidebar">
      <div style={{ padding: '24px', borderBottom: '1px solid var(--border-light)', display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{ background: 'var(--accent-primary)', padding: '8px', borderRadius: '8px', display: 'flex' }}>
          <Shield size={24} color="white" />
        </div>
        <h2 style={{ fontSize: '1.2rem', margin: 0, color: 'white' }}>PROVCHAIN</h2>
      </div>
      
      <nav style={{ padding: '24px 16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <NavLink 
          to="/" 
          style={({isActive}) => ({
            display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px', 
            borderRadius: 'var(--border-radius-sm)',
            color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
            background: isActive ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
            border: isActive ? '1px solid var(--border-light)' : '1px solid transparent',
          })}
        >
          <Home size={20} />
          <span style={{ fontWeight: 500 }}>Dashboard</span>
        </NavLink>
        
        <NavLink 
          to="/register" 
          style={({isActive}) => ({
            display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px', 
            borderRadius: 'var(--border-radius-sm)',
            color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
            background: isActive ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
            border: isActive ? '1px solid var(--border-light)' : '1px solid transparent',
          })}
        >
          <Upload size={20} />
          <span style={{ fontWeight: 500 }}>Register Asset</span>
        </NavLink>

        <p style={{ color: 'var(--text-secondary)', margin: '14px 12px 2px', fontSize: '0.82rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Evidence Management
        </p>

        <NavLink
          to="/scans"
          style={({isActive}) => ({
            display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px',
            borderRadius: 'var(--border-radius-sm)',
            color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
            background: isActive ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
            border: isActive ? '1px solid var(--border-light)' : '1px solid transparent',
          })}
        >
          <Layers size={20} />
          <span style={{ fontWeight: 500 }}>Asset Scans</span>
        </NavLink>

        <NavLink
          to="/bundles"
          style={({isActive}) => ({
            display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px',
            borderRadius: 'var(--border-radius-sm)',
            color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
            background: isActive ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
            border: isActive ? '1px solid var(--border-light)' : '1px solid transparent',
          })}
        >
          <FileText size={20} />
          <span style={{ fontWeight: 500 }}>Evidence Bundles</span>
        </NavLink>
      </nav>
      
      <div style={{ marginTop: 'auto', padding: '24px' }}>
        <div className="glass-panel" style={{ padding: '16px', textAlign: 'center' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
            Anchored on Bitcoin via OpenTimestamps.
          </p>
          <div className="badge badge-success">Trust Layer Active</div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
