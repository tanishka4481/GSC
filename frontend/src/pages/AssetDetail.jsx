import React, { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Search, ShieldAlert, ArrowRight, Clock } from 'lucide-react';
import DomainRiskBadge from '../components/DomainRiskBadge';
import PropagationChart from '../components/PropagationChart';

const confidenceRank = {
  HIGH_CONFIDENCE: 4,
  PROBABLE_MATCH: 3,
  POSSIBLE_MATCH: 2,
  NO_MATCH: 1,
};

const riskToScore = {
  HIGH: 85,
  MEDIUM: 55,
  LOW: 25,
};

const toPlatformName = (domain) => {
  if (!domain) return 'Unknown';
  const parts = String(domain).split('.').filter(Boolean);
  if (parts.length === 0) return 'Unknown';
  if (parts.length === 1) return parts[0];
  return parts[parts.length - 2];
};

const formatDate = (iso) => {
  if (!iso) return 'Unknown';
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return 'Unknown';
  return parsed.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

const formatDateTime = (iso) => {
  if (!iso) return '-';
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return '-';
  return parsed.toLocaleString();
};

const AssetDetail = () => {
  const { id } = useParams();
  const [asset, setAsset] = useState(null);
  const [assetLoading, setAssetLoading] = useState(true);
  const [assetError, setAssetError] = useState('');

  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState('');
  const [scanResults, setScanResults] = useState(null);
  const [latestScan, setLatestScan] = useState(null);

  useEffect(() => {
    const fetchAsset = async () => {
      if (!id) {
        setAssetError('Missing asset ID in route.');
        setAssetLoading(false);
        return;
      }

      setAssetLoading(true);
      setAssetError('');

      try {
        const response = await fetch(`/api/v1/assets/${id}`);
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data?.detail || 'Failed to load asset details');
        }

        setAsset(data);
      } catch (error) {
        setAssetError(error.message || 'Failed to load asset details');
      } finally {
        setAssetLoading(false);
      }
    };

    fetchAsset();
  }, [id]);

  useEffect(() => {
    const fetchLatestScan = async () => {
      if (!id) return;

      try {
        const response = await fetch(`/api/v1/scan/${id}/history`);
        const data = await response.json();

        if (response.ok && Array.isArray(data) && data.length > 0) {
          setLatestScan(data[0]);
        }
      } catch {
        // Best-effort only.
      }
    };

    fetchLatestScan();
  }, [id]);

  const chartData = useMemo(() => {
    const hits = scanResults?.hits || [];
    if (hits.length === 0) return [];

    const counts = hits.reduce((acc, hit) => {
      const key = toPlatformName(hit.domain);
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});

    return Object.entries(counts).map(([name, count]) => ({
      name,
      value: Math.round((count / hits.length) * 100),
    }));
  }, [scanResults]);

  const bestHit = useMemo(() => {
    const hits = scanResults?.hits || [];
    if (hits.length === 0) return null;

    return [...hits].sort((a, b) => {
      const aRank = confidenceRank[a?.decision?.confidence] || 0;
      const bRank = confidenceRank[b?.decision?.confidence] || 0;
      if (aRank !== bRank) return bRank - aRank;
      return (b?.decision?.embedding_score || 0) - (a?.decision?.embedding_score || 0);
    })[0];
  }, [scanResults]);

  const pageRiskBadge = scanResults?.risk_score >= 0.7
    ? 'High Risk'
    : scanResults?.risk_score >= 0.4
      ? 'Moderate Risk'
      : 'Low Risk';

  const handleManualScan = async () => {
    if (!id) return;

    setScanning(true);
    setScanError('');

    try {
      const response = await fetch(`/api/v1/scan/${id}`, {
        method: 'POST',
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.detail || 'Scan failed');
      }

      setScanResults(data);

      const historyResponse = await fetch(`/api/v1/scan/${id}/history`);
      const historyData = await historyResponse.json();
      if (historyResponse.ok && Array.isArray(historyData) && historyData.length > 0) {
        setLatestScan(historyData[0]);
        setScanResults((previous) => ({
          ...previous,
          hits: previous?.hits?.length ? previous.hits : historyData[0].hits || [],
          scanned_at: previous?.scanned_at || historyData[0].created_at || null,
        }));
      }
    } catch (error) {
      setScanError(error.message || 'Scan failed');
    } finally {
      setScanning(false);
    }
  };

  const displayHits = scanResults?.hits || [];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '32px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <h1 style={{ fontSize: '2rem', margin: 0, color: 'var(--text-primary)' }}>
              {assetLoading ? 'Loading asset...' : (asset?.filename || 'Unknown Asset')}
            </h1>
            {!assetLoading && <span className="badge badge-warning">{pageRiskBadge}</span>}
          </div>
          <p style={{ color: 'var(--text-secondary)', margin: 0, fontFamily: 'monospace', background: 'rgba(0,0,0,0.3)', padding: '4px 8px', borderRadius: '4px', display: 'inline-block' }}>
            ID: {id || '-'} • Reg: {formatDate(asset?.created_at)}
          </p>
          {assetError && <p style={{ color: 'var(--danger)', marginTop: '10px', marginBottom: 0 }}>{assetError}</p>}
          {scanError && <p style={{ color: 'var(--danger)', marginTop: '10px', marginBottom: 0 }}>{scanError}</p>}
        </div>
        <button
          className="btn btn-primary"
          onClick={handleManualScan}
          disabled={scanning || !id}
        >
          {scanning ? (
            <><div className="loader" style={{ width: '16px', height: '16px', borderWidth: '2px' }}></div> Scanning Web...</>
          ) : (
            <><Search size={18} /> Trigger Manual Scan</>
          )}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '32px' }}>
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h3 style={{ color: 'var(--text-primary)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldAlert size={20} color="var(--warning)" /> Propagation Distribution
          </h3>
          {chartData.length > 0 ? (
            <PropagationChart data={chartData} />
          ) : (
            <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
              Trigger a manual scan to visualize real propagation data.
            </p>
          )}
        </div>

        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ color: 'var(--text-primary)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={20} color="var(--accent-primary)" /> Scan Intelligence
          </h3>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '16px', borderBottom: '1px solid var(--border-light)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Match Confidence (Gemini)</span>
              <span style={{ color: 'var(--success)', fontWeight: 600 }}>
                {bestHit
                  ? `${(bestHit?.decision?.embedding_score || 0).toFixed(2)} (${bestHit?.decision?.confidence || 'NO_MATCH'})`
                  : '-'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '16px', borderBottom: '1px solid var(--border-light)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Detected Hits</span>
              <span style={{ color: 'var(--warning)', fontWeight: 600 }}>{scanResults?.total_hits ?? '-'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '8px', borderTop: '1px solid var(--border-light)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Latest Scan</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                {latestScan?.created_at ? formatDateTime(latestScan.created_at) : 'Not run yet'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Alert Triggered</span>
              <span style={{ color: 'var(--danger)', fontWeight: 600 }}>{scanResults?.alert_triggered ? 'Yes' : 'No'}</span>
            </div>
          </div>
          <Link to={`/evidence/${id || ''}`} className="btn btn-secondary" style={{ marginTop: '24px', width: '100%' }}>
            Generate Evidence Bundle <ArrowRight size={18} />
          </Link>
        </div>
      </div>

      <h2 style={{ fontSize: '1.4rem', marginBottom: '16px', color: 'var(--text-primary)' }}>Detected Instances</h2>
      <div className="table-container glass-panel">
        <table>
          <thead>
            <tr>
              <th>URL</th>
              <th>Platform</th>
              <th>Domain Risk</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {displayHits.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '20px' }}>
                  {scanning
                    ? 'Scanning in progress...'
                    : latestScan
                      ? `Latest scan completed at ${formatDateTime(latestScan.created_at)} but returned no hits.`
                      : 'No scan hits yet. Trigger a manual scan to populate this table.'}
                </td>
              </tr>
            ) : (
              displayHits.map((hit, index) => (
                <tr key={`${hit.url}-${index}`}>
                  <td style={{ fontFamily: 'monospace', color: 'var(--accent-primary)', maxWidth: '420px', overflowWrap: 'anywhere' }}>
                    {hit.url}
                  </td>
                  <td>{toPlatformName(hit.domain)}</td>
                  <td>
                    <DomainRiskBadge riskScore={riskToScore[hit?.decision?.domain_risk] || 55} />
                  </td>
                  <td style={{ color: 'var(--text-secondary)' }}>{formatDateTime(hit.discovered_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default AssetDetail;
