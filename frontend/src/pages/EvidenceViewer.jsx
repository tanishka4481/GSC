import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Download, Mail, FileText, CheckCircle, ExternalLink } from 'lucide-react';
import IPFSVerifier from '../components/IPFSVerifier';

const EvidenceViewer = () => {
  const { id } = useParams();
  const [asset, setAsset] = useState(null);
  const [loadingAsset, setLoadingAsset] = useState(true);
  const [assetError, setAssetError] = useState('');

  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [sendError, setSendError] = useState('');
  const [downloadError, setDownloadError] = useState('');

  useEffect(() => {
    const fetchAsset = async () => {
      if (!id) {
        setAssetError('Missing asset ID.');
        setLoadingAsset(false);
        return;
      }

      setLoadingAsset(true);
      setAssetError('');

      try {
        const response = await fetch(`/api/v1/assets/${id}`);
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data?.detail || 'Failed to fetch asset details');
        }

        setAsset(data);
      } catch (error) {
        setAssetError(error.message || 'Failed to fetch asset details');
      } finally {
        setLoadingAsset(false);
      }
    };

    fetchAsset();
  }, [id]);

  const handleDownloadBundle = async () => {
    if (!id) return;
    setDownloadError('');

    try {
      const response = await fetch(`/api/v1/evidence/${id}?download=true`);
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data?.detail || data?.message || 'Evidence endpoint not ready');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `evidence_bundle_${id}.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      setDownloadError(error.message || 'Evidence endpoint not ready');
    }
  };

  const handleSendNotice = async () => {
    if (!id) return;

    setSending(true);
    setSendError('');

    try {
      const response = await fetch('/api/v1/notice/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          asset_id: id,
          jurisdiction: 'dmca',
        }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.detail || data?.message || 'Notice dispatch endpoint not ready');
      }

      setSent(Boolean(data?.dispatched));
      if (data?.status === 'preview_only') {
        setSendError(data?.message || 'Notice generated in preview mode.');
      }
    } catch (error) {
      setSendError(error.message || 'Notice dispatch endpoint not ready');
      setSent(false);
    } finally {
      setSending(false);
    }
  };

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '2rem', marginBottom: '8px', color: 'var(--text-primary)' }}>Evidence Bundle</h1>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            Generated for Asset:{' '}
            <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
              {loadingAsset ? 'Loading...' : (asset?.filename || id || 'Unknown Asset')}
            </span>
          </p>
          {assetError && <p style={{ color: 'var(--danger)', marginTop: '8px', marginBottom: 0 }}>{assetError}</p>}
        </div>
        <button className="btn btn-secondary" onClick={handleDownloadBundle}>
          <Download size={18} /> Download Bundle (ZIP)
        </button>
      </div>

      {downloadError && <p style={{ color: 'var(--danger)', marginTop: '-16px', marginBottom: '20px' }}>{downloadError}</p>}

      <div style={{ marginBottom: '32px' }}>
        {asset?.ipfs_cid ? (
          <IPFSVerifier cid={asset.ipfs_cid} />
        ) : (
          <div className="glass-panel" style={{ padding: '20px', color: 'var(--text-secondary)' }}>
            No IPFS CID found yet for this asset.
          </div>
        )}
      </div>

      <div className="dashboard-grid">
        <div className="glass-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <div style={{ background: 'rgba(99, 102, 241, 0.1)', padding: '10px', borderRadius: '8px' }}>
              <FileText size={20} color="var(--accent-primary)" />
            </div>
            <h3 style={{ color: 'var(--text-primary)', margin: 0 }}>Registration Certificate</h3>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '16px' }}>
            Contains pHash, Gemini embeddings, and Bitcoin OpenTimestamps receipt.
          </p>
          <a href="#" className="btn btn-secondary" style={{ width: '100%', fontSize: '0.85rem' }}>
            View PDF <ExternalLink size={14} />
          </a>
        </div>

        <div className="glass-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <div style={{ background: 'rgba(99, 102, 241, 0.1)', padding: '10px', borderRadius: '8px' }}>
              <FileText size={20} color="var(--accent-primary)" />
            </div>
            <h3 style={{ color: 'var(--text-primary)', margin: 0 }}>Match Report</h3>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '16px' }}>
            Visual diffs, cosine similarity scores, and identified infringing domains.
          </p>
          <a href="#" className="btn btn-secondary" style={{ width: '100%', fontSize: '0.85rem' }}>
            View PDF <ExternalLink size={14} />
          </a>
        </div>

        <div className="glass-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <div style={{ background: 'rgba(239, 68, 68, 0.1)', padding: '10px', borderRadius: '8px' }}>
              <FileText size={20} color="var(--danger)" />
            </div>
            <h3 style={{ color: 'var(--text-primary)', margin: 0 }}>Legal Notice</h3>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '16px' }}>
            Pre-filled IT Rules 2021 Takedown Notice targeting High Risk domains.
          </p>
          <a href="#" className="btn btn-secondary" style={{ width: '100%', fontSize: '0.85rem' }}>
            Preview Draft <ExternalLink size={14} />
          </a>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: '32px', marginTop: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ color: 'var(--text-primary)', marginBottom: '8px', fontSize: '1.2rem' }}>Automated Dispatch</h3>
            <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
              Send the IPFS-anchored IT Rules 2021 notice to the abuse contacts of the top 3 infringing domains.
            </p>
          </div>
          
          {sent ? (
            <div className="badge badge-success" style={{ padding: '10px 20px', fontSize: '0.9rem' }}>
              <CheckCircle size={18} /> Notice Sent Successfully
            </div>
          ) : (
            <button 
              className="btn btn-primary" 
              onClick={handleSendNotice}
              disabled={sending || !id}
              style={{ padding: '12px 24px', minWidth: '180px' }}
            >
              {sending ? (
                <><div className="loader" style={{ width: '16px', height: '16px', borderWidth: '2px' }}></div> Sending...</>
              ) : (
                <><Mail size={18} /> Dispatch Legal Notice</>
              )}
            </button>
          )}
        </div>

        {sendError && <p style={{ color: 'var(--danger)', marginTop: '14px', marginBottom: 0 }}>{sendError}</p>}
        
        {sent && (
          <div style={{ marginTop: '24px', padding: '16px', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', borderLeft: '4px solid var(--success)' }}>
            <p style={{ color: 'var(--text-primary)', margin: '0 0 8px 0', fontWeight: 500 }}>Dispatch Log:</p>
            <ul style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', paddingLeft: '20px', margin: 0 }}>
              <li>Sent to abuse@dailyhunt.in (Ticket #DH-8921)</li>
              <li>Sent to grievance@sharechat.com (Ticket #SC-4491)</li>
              <li>BCC archived to legal@indianexpress.in</li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default EvidenceViewer;
