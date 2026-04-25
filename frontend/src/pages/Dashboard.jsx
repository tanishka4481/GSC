import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Activity, ShieldAlert, FileText, UploadCloud, ArrowRight } from 'lucide-react';
import DomainRiskBadge from '../components/DomainRiskBadge';

const OWNER_ID = 'demo-user';

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

      try {
        const [assetsRes, alertsRes] = await Promise.all([
          fetch(`/api/v1/assets?owner_id=${encodeURIComponent(OWNER_ID)}`),
          fetch(`/api/v1/alerts?owner_id=${encodeURIComponent(OWNER_ID)}`),
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
              const historyRes = await fetch(`/api/v1/scan/${asset.asset_id}/history`);
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
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '2rem', marginBottom: '8px', color: 'var(--text-primary)' }}>Dashboard</h1>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Overview of your registered assets and propagation alerts.</p>
        </div>
        <Link to="/register" className="btn btn-primary">
          <UploadCloud size={18} /> Register New Asset
        </Link>
      </div>

      <div className="dashboard-grid">
        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ background: 'rgba(99, 102, 241, 0.1)', padding: '16px', borderRadius: '16px' }}>
            <FileText size={32} color="var(--accent-primary)" />
          </div>
          <div>
            <p style={{ margin: '0 0 4px 0', color: 'var(--text-secondary)', fontWeight: 500 }}>Total Assets</p>
            <h2 style={{ margin: 0, fontSize: '2rem', color: 'var(--text-primary)' }}>{stats.total}</h2>
          </div>
        </div>
        
        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '20px', borderColor: 'rgba(239, 68, 68, 0.2)' }}>
          <div style={{ background: 'rgba(239, 68, 68, 0.1)', padding: '16px', borderRadius: '16px' }}>
            <Activity size={32} color="var(--danger)" />
          </div>
          <div>
            <p style={{ margin: '0 0 4px 0', color: 'var(--danger)', fontWeight: 500 }}>Active Alerts</p>
            <h2 style={{ margin: 0, fontSize: '2rem', color: 'var(--text-primary)' }}>{stats.flagged}</h2>
          </div>
        </div>

        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '16px', borderRadius: '16px' }}>
            <ShieldAlert size={32} color="var(--success)" />
          </div>
          <div>
            <p style={{ margin: '0 0 4px 0', color: 'var(--success)', fontWeight: 500 }}>Evidence Bundles</p>
            <h2 style={{ margin: 0, fontSize: '2rem', color: 'var(--text-primary)' }}>{stats.bundles}</h2>
          </div>
        </div>
      </div>

      <h2 style={{ fontSize: '1.4rem', marginBottom: '16px', color: 'var(--text-primary)' }}>Recent Scan Activity</h2>
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      <div className="table-container glass-panel">
        <table>
          <thead>
            <tr>
              <th>Asset Name</th>
              <th>Domains Detected</th>
              <th>Highest Risk</th>
              <th>Last Scan</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '18px' }}>
                  Loading dashboard data...
                </td>
              </tr>
            ) : recentScans.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '18px' }}>
                  No assets found for this owner yet.
                </td>
              </tr>
            ) : (
              recentScans.map((scan) => (
                <tr key={scan.id}>
                  <td style={{ fontWeight: 500 }}>{scan.asset}</td>
                  <td>{scan.domains} matches</td>
                  <td><DomainRiskBadge riskScore={scan.highestRisk} /></td>
                  <td style={{ color: 'var(--text-secondary)' }}>{scan.time}</td>
                  <td>
                    <Link to={`/asset/${scan.assetId}`} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.85rem', fontWeight: 600 }}>
                      View Report <ArrowRight size={14} />
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Dashboard;
