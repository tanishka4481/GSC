import React, { useState } from 'react';
import { Bell, Search, User, LogOut, CheckCircle2, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const Topbar = ({ user, onLogout }) => {
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <header className="topbar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', width: '100%', maxWidth: '600px' }}>
        <div style={{ display: 'flex', alignItems: 'center', width: '100%', position: 'relative' }}>
          <Search size={20} color="var(--text-muted)" style={{ position: 'absolute', marginLeft: '16px' }} />
          <input 
            type="text" 
            placeholder="Search registered assets, CIDs, or flagged domains..." 
            className="form-control"
            style={{ paddingLeft: '48px', borderRadius: '24px', width: '100%' }}
          />
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            onClick={() => setNotificationsOpen((value) => !value)}
            aria-label="Toggle notifications"
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', position: 'relative', padding: 0 }}
          >
            <Bell size={20} color="var(--text-secondary)" />
            <span style={{ position: 'absolute', top: '-4px', right: '-4px', width: '8px', height: '8px', background: 'var(--danger)', borderRadius: '50%' }}></span>
          </button>
          {notificationsOpen && (
            <div className="glass-panel" style={{ position: 'absolute', right: 0, top: '32px', width: '320px', padding: '16px', zIndex: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <strong style={{ color: 'var(--text-primary)' }}>Notifications</strong>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Demo feed</span>
              </div>
              <div style={{ display: 'grid', gap: '10px' }}>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                  <CheckCircle2 size={18} color="var(--success)" style={{ marginTop: '2px' }} />
                  <div>
                    <div style={{ color: 'var(--text-primary)', fontSize: '0.92rem' }}>Latest scan completed</div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>3 matches flagged in the last run.</div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                  <AlertCircle size={18} color="var(--warning)" style={{ marginTop: '2px' }} />
                  <div>
                    <div style={{ color: 'var(--text-primary)', fontSize: '0.92rem' }}>Review queued</div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>A PDF used fallback fingerprinting during registration.</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{user?.name || 'Demo Publisher'}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{user?.email || 'Guest session'}</div>
          </div>
          <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <User size={20} color="white" />
          </div>
          {onLogout ? (
            <button
              type="button"
              onClick={onLogout}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: 'transparent',
                border: '1px solid var(--border-light)',
                color: 'var(--text-secondary)',
                borderRadius: '999px',
                padding: '8px 12px',
                cursor: 'pointer',
              }}
            >
              <LogOut size={16} />
              Logout
            </button>
          ) : (
            <button
              type="button"
              onClick={() => navigate('/login')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: 'transparent',
                border: '1px solid var(--border-light)',
                color: 'var(--text-secondary)',
                borderRadius: '999px',
                padding: '8px 12px',
                cursor: 'pointer',
              }}
            >
              Sign In
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

export default Topbar;
