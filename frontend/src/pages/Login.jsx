import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const Login = ({ user, onLogin }) => {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (user) {
      navigate('/');
    }
  }, [user, navigate]);

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!name.trim() || !email.trim() || !password.trim()) {
      setError('Enter any name, email, and password to continue.');
      return;
    }

    onLogin({
      name: name.trim(),
      email: email.trim(),
      ownerId: email.trim().toLowerCase(),
    });
  };

  return (
    <div style={{ maxWidth: '560px', margin: '64px auto', padding: '0 20px' }}>
      <div className="glass-panel" style={{ padding: '32px', background: 'var(--bg-glass)', color: 'var(--text-primary)' }}>
        <p style={{ color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.12em', fontSize: '0.78rem', marginTop: 0 }}>Demo Login</p>
        <h1 style={{ color: 'var(--text-primary)', marginTop: 0, marginBottom: '8px' }}>Sign in locally</h1>
        <p style={{ color: 'var(--text-secondary)', marginTop: 0, marginBottom: '24px' }}>
          This is a dummy login only. Any non-empty details will sign you in on this machine.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '14px' }}>
          <label style={{ display: 'grid', gap: '6px', color: 'var(--text-secondary)' }}>
            Name
            <input className="form-control" value={name} onChange={(e) => setName(e.target.value)} placeholder="Demo Publisher" />
          </label>
          <label style={{ display: 'grid', gap: '6px', color: 'var(--text-secondary)' }}>
            Email
            <input className="form-control" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="demo@publisher.local" />
          </label>
          <label style={{ display: 'grid', gap: '6px', color: 'var(--text-secondary)' }}>
            Password
            <input className="form-control" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Anything works" />
          </label>

          {error && <div style={{ color: 'var(--danger)' }}>{error}</div>}

          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center' }}>
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/')}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Sign In
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;