import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, ArrowRight } from 'lucide-react';
import { apiUrl } from '../lib/api';
import { getOwnerId } from '../lib/auth';

const AssetScans = () => {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchAssets = async () => {
      setLoading(true);
      setError('');
      const ownerId = getOwnerId();

      try {
        const response = await fetch(apiUrl(`/api/v1/assets?owner_id=${encodeURIComponent(ownerId)}`));
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data?.detail || 'Failed to fetch assets');
        }

        setAssets(Array.isArray(data) ? data : []);
      } catch (e) {
        setError(e.message || 'Failed to fetch assets');
      } finally {
        setLoading(false);
      }
    };

    fetchAssets();
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '26px' }}>
        <div>
          <h1 style={{ fontSize: '2rem', marginBottom: '8px', color: 'var(--text-primary)' }}>Asset Scans</h1>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Open any registered asset and run a manual propagation scan.</p>
        </div>
      </div>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      <div className="table-container glass-panel">
        <table>
          <thead>
            <tr>
              <th>Asset Name</th>
              <th>Asset ID</th>
              <th>Registered</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '18px' }}>Loading assets...</td>
              </tr>
            ) : assets.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '18px' }}>No assets registered yet.</td>
              </tr>
            ) : (
              assets.map((asset) => (
                <tr key={asset.asset_id}>
                  <td style={{ fontWeight: 500 }}>{asset.filename || 'Unnamed Asset'}</td>
                  <td style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>{asset.asset_id}</td>
                  <td>{asset.created_at ? new Date(asset.created_at).toLocaleDateString() : '-'}</td>
                  <td>
                    <Link to={`/asset/${asset.asset_id}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
                      Open Scan View <ArrowRight size={14} />
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: '16px', color: 'var(--text-secondary)', fontSize: '0.9rem', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <Search size={16} />
        Run scans from each asset page using the Trigger Manual Scan button.
      </div>
    </div>
  );
};

export default AssetScans;
