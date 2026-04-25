import React, { useState, useRef } from 'react';
import { UploadCloud, Image as ImageIcon, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const OWNER_ID = 'demo-user';

const Register = () => {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setError('');
    
    // Create FormData for the API
    const formData = new FormData();
    formData.append('file', file);
    formData.append('owner_id', OWNER_ID);

    try {
      const response = await fetch('/api/v1/register', {
        method: 'POST',
        body: formData,
      });
      
      const data = await response.json();

      if (!response.ok) {
        let errMsg = data?.message || 'Registration failed';
        if (typeof data?.detail === 'string') {
          errMsg = data.detail;
        } else if (data?.detail && typeof data.detail === 'object' && data.detail.existing_asset_id) {
          errMsg = `Duplicate asset! Already registered with ID: ${data.detail.existing_asset_id}`;
        }
        throw new Error(errMsg);
      }

      if (!data?.asset_id) {
        throw new Error('Registration succeeded but no asset_id was returned');
      }
      
      setSuccess(true);
      setTimeout(() => {
        navigate(`/asset/${data.asset_id}`);
      }, 1500);
    } catch (error) {
      setError(error.message || 'Registration failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '8px', color: 'var(--text-primary)' }}>Register Asset</h1>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Upload your content. PROVCHAIN will generate a pHash and Gemini embedding, anchoring it to the Bitcoin blockchain via OpenTimestamps.
        </p>
      </div>

      {success ? (
        <div className="glass-panel animate-fade-in" style={{ padding: '40px', textAlign: 'center', borderColor: 'var(--success)', boxShadow: '0 0 30px var(--success-glow)' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
            <CheckCircle size={64} color="var(--success)" />
          </div>
          <h2 style={{ color: 'var(--success)', marginBottom: '16px' }}>Registration Complete!</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Your asset has been successfully fingerprinted and anchored.</p>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '8px' }}>Redirecting to asset details...</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="glass-card animate-fade-in">
          <div 
            style={{ 
              border: '2px dashed var(--border-light)', 
              borderRadius: 'var(--border-radius-md)', 
              padding: '60px 20px', 
              textAlign: 'center',
              cursor: 'pointer',
              background: 'rgba(0,0,0,0.2)',
              transition: 'all 0.3s ease',
              borderColor: file ? 'var(--accent-primary)' : 'var(--border-light)'
            }}
            onClick={() => fileInputRef.current.click()}
          >
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleFileChange} 
              style={{ display: 'none' }} 
              accept="image/*,text/plain,.pdf"
            />
            
            {file ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
                {file.type.startsWith('image/') ? <ImageIcon size={48} color="var(--accent-primary)" /> : <FileText size={48} color="var(--accent-primary)" />}
                <div>
                  <h3 style={{ color: 'var(--text-primary)', marginBottom: '4px' }}>{file.name}</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
                <button type="button" className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); setFile(null); }}>
                  Remove
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
                <UploadCloud size={48} color="var(--text-secondary)" />
                <div>
                  <h3 style={{ color: 'var(--text-primary)', marginBottom: '8px' }}>Click to upload or drag and drop</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Supports images, PDF, and text up to 100MB</p>
                </div>
              </div>
            )}
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              <AlertCircle size={16} /> 
              Maximum file size is 100MB
            </div>
            <button 
              type="submit" 
              className="btn btn-primary" 
              disabled={!file || uploading}
              style={{ minWidth: '160px' }}
            >
              {uploading ? (
                <><div className="loader" style={{ width: '16px', height: '16px', borderWidth: '2px' }}></div> Processing...</>
              ) : (
                'Register Asset'
              )}
            </button>
          </div>
          {error && (
            <p style={{ color: 'var(--danger)', marginTop: '14px', marginBottom: 0 }}>
              {error}
            </p>
          )}
        </form>
      )}
    </div>
  );
};

export default Register;
