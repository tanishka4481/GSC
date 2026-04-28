import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Activity, ShieldAlert, FileText, UploadCloud, ArrowRight } from 'lucide-react';
import DomainRiskBadge from '../components/DomainRiskBadge';
import { apiUrl } from '../lib/api';
import { getOwnerId } from '../lib/auth';

const toRelativeTime = (iso) => {
  if (!iso) return 'Unknown';
  const now = Date.now();
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return 'Unknown';

  const diffMinutes = Math.max(1, Math.floor((now - ts) / (1000 * 60)));
  if (diffMinutes < 60) return `${diffMinutes} min ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} hr ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
};

const Dashboard = () => {
  const [stats, setStats] = useState({ total: 0, flagged: 0, bundles: 0 });
  const [recentScans, setRecentScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDashboardData = async () => {
      setLoading(true);
      setError('');
      const ownerId = getOwnerId();

      try {
        const [assetsRes, alertsRes] = await Promise.all([
          fetch(apiUrl(`/api/v1/assets?owner_id=${encodeURIComponent(ownerId)}`)),
          fetch(apiUrl(`/api/v1/alerts?owner_id=${encodeURIComponent(ownerId)}`)),
        ]);

        const assetsData = await assetsRes.json();
        const alertsData = await alertsRes.json();

        if (!assetsRes.ok) {
          throw new Error(assetsData?.detail || 'Failed to fetch assets');
        }
        if (!alertsRes.ok) {
          throw new Error(alertsData?.detail || 'Failed to fetch alerts');
        }

        const assets = Array.isArray(assetsData) ? assetsData : [];
        const alerts = Array.isArray(alertsData) ? alertsData : [];

        const scanRows = await Promise.all(
          assets.slice(0, 8).map(async (asset) => {
            try {
              const historyRes = await fetch(apiUrl(`/api/v1/scan/${asset.asset_id}/history`));
              const historyData = await historyRes.json();

              const latest = historyRes.ok && Array.isArray(historyData) && historyData.length > 0
                ? historyData[0]
                : null;

              const highestRisk = latest
                ? Math.round((latest.risk_score || 0) * 100)
                : 0;

              return {
                id: latest?.scan_id || asset.asset_id,
                assetId: asset.asset_id,
                asset: asset.filename || asset.asset_id,
                domains: latest?.metrics?.unique_domains || 0,
                highestRisk,
                time: latest?.created_at ? toRelativeTime(latest.created_at) : toRelativeTime(asset.created_at),
              };
            } catch {
              return {
                id: asset.asset_id,
                assetId: asset.asset_id,
                asset: asset.filename || asset.asset_id,
                domains: 0,
                highestRisk: 0,
                time: toRelativeTime(asset.created_at),
              };
            }
          })
        );

        setRecentScans(scanRows);
        setStats({
          total: assets.length,
          flagged: alerts.filter((alert) => !alert.acknowledged).length,
          bundles: assets.filter((asset) => Boolean(asset.ipfs_cid)).length,
        });
      } catch (e) {
        setError(e.message || 'Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '55% 45%', minHeight: 'calc(100vh - var(--header-height))', width: '100%', margin: 0 }}>
      {/* LEFT SIDE - BROWN */}
      <div style={{ padding: '60px', display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
        {/* Crisp mustard-tinted decorative circle */}
        <div style={{
          position: 'absolute',
          width: '700px', 
          height: '700px',
          borderRadius: '50%',
          background: 'rgba(201, 146, 42, 0.05)',
          border: '1px solid rgba(201, 146, 42, 0.15)',
          top: '50%',
          right: '-250px',
          transform: 'translateY(-50%)',
          pointerEvents: 'none'
        }}></div>
        
        <div style={{ marginBottom: '60px', position: 'relative', zIndex: 1 }}>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.62rem', letterSpacing: '0.22em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '28px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ color: 'var(--gold)' }}>//</span> ASSET INTELLIGENCE
          </p>
          <h1 style={{ fontFamily: 'var(--font-head)', fontSize: 'clamp(2.8rem, 4vw, 3.8rem)', fontWeight: 900, lineHeight: 1.05, margin: 0, color: 'var(--text-primary)' }}>
            Your content.<br />
            <span style={{ color: 'var(--gold)' }}>Protected.</span><br />
            Enforced.
          </h1>
          <p style={{ color: 'var(--text-secondary)', marginTop: '24px', marginBottom: '36px', fontSize: '0.9rem', maxWidth: '380px', lineHeight: 1.7 }}>
            Bitcoin-anchored fingerprinting for publishers. Court-ready evidence in 48 hours.
          </p>
          <Link to="/register" className="btn btn-primary" style={{ alignSelf: 'flex-start', padding: '14px 28px' }}>
            REGISTER ASSET <ArrowRight size={16} />
          </Link>
        </div>

        <h2 style={{ fontSize: '1.2rem', marginBottom: '16px', color: 'var(--text-primary)' }}>Recent Scan Activity</h2>
        {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Asset Name</th>
                <th>Domains Detected</th>
                <th>Highest Risk</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '18px' }}>
                    Loading dashboard data...
                  </td>
                </tr>
              ) : recentScans.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '18px' }}>
                    No assets found for this owner yet.
                  </td>
                </tr>
              ) : (
                recentScans.map((scan) => (
                  <tr key={scan.id}>
                    <td style={{ fontWeight: 500 }}>{scan.asset}</td>
                    <td>{scan.domains} matches</td>
                    <td><DomainRiskBadge riskScore={scan.highestRisk} /></td>
                    <td>
                      <Link to={`/asset/${scan.assetId}`} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.85rem', fontWeight: 600 }}>
                        View <ArrowRight size={14} />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* RIGHT SIDE - CREAM */}
      <div style={{ background: 'var(--brown-card)', padding: '60px 40px', position: 'relative' }}>
        {/* We need to override context manually here since we removed the global override */}
        <div style={{ '--text-primary': 'var(--text-dark)', '--text-secondary': 'var(--text-dark2)', '--text-muted': '#665947', color: 'var(--text-primary)' }}>
          <div className="dashboard-grid">
            <div className="glass-card">
              <p style={{ margin: '0 0 12px 0', color: 'var(--text-muted)', fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: '0.65rem', letterSpacing: '0.15em', textTransform: 'uppercase' }}>Total Assets</p>
              <h2 style={{ margin: 0, fontSize: '3rem', fontFamily: 'var(--font-head)', color: 'var(--text-primary)' }}>{stats.total}</h2>
              <p style={{ margin: '8px 0 0 0', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Registered & fingerprinted</p>
            </div>
            
            <div className="glass-card" style={{ borderLeft: '3px solid var(--danger)' }}>
              <p style={{ margin: '0 0 12px 0', color: 'var(--danger)', fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: '0.65rem', letterSpacing: '0.15em', textTransform: 'uppercase' }}>Active Alerts</p>
              <h2 style={{ margin: 0, fontSize: '3rem', fontFamily: 'var(--font-head)', color: 'var(--danger)' }}>{stats.flagged}</h2>
              <p style={{ margin: '8px 0 0 0', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Unauthorized copies detected</p>
            </div>

            <div className="glass-card" style={{ background: 'var(--brown-base)', borderColor: 'var(--border-gold)' }}>
              <p style={{ margin: '0 0 12px 0', color: 'var(--gold)', fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: '0.65rem', letterSpacing: '0.15em', textTransform: 'uppercase' }}>Evidence Bundles</p>
              <h2 style={{ margin: 0, fontSize: '3rem', fontFamily: 'var(--font-head)', color: 'var(--text-cream)' }}>{stats.bundles}</h2>
              <p style={{ margin: '8px 0 0 0', color: 'var(--text-warm)', fontSize: '0.85rem' }}>Immutable reports generated</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
