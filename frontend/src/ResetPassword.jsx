import React, { useState } from 'react';
import api from './api';

export default function ResetPassword({ token, onResetSuccess }) {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError('Hasło musi mieć co najmniej 8 znaków.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Hasła nie są identyczne.');
      return;
    }

    setLoading(true);
    try {
      await api.post('/reset-password', {
        token,
        new_password: password
      });
      setSuccess("Hasło zostało pomyślnie zmienione! Zaraz nastąpi przekierowanie...");
      setTimeout(() => {
        onResetSuccess();
      }, 3000);
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Wystąpił błąd lub link stracił ważność. Spróbuj ponownie.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      backgroundColor: 'var(--bg)'
    }}>
      <div style={{
        backgroundColor: 'var(--panel-bg)',
        padding: '2.5rem',
        borderRadius: '12px',
        boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
        width: '100%',
        maxWidth: '400px',
        border: '1px solid var(--border)'
      }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div className="logo-mark" style={{ display: 'inline-flex', width: '40px', height: '40px', fontSize: '1.2rem', marginBottom: '1rem' }}>M</div>
          <h2 style={{ color: 'var(--fg)', margin: 0 }}>Ustaw nowe hasło</h2>
        </div>

        {error && (
          <div style={{
            padding: '10px',
            backgroundColor: 'rgba(231, 76, 60, 0.1)',
            color: '#e74c3c',
            borderRadius: '6px',
            marginBottom: '1rem',
            fontSize: '0.9rem',
            textAlign: 'center'
          }}>
            {error}
          </div>
        )}

        {success && (
          <div style={{
            padding: '10px',
            backgroundColor: 'rgba(46, 204, 113, 0.1)',
            color: '#2ecc71',
            borderRadius: '6px',
            marginBottom: '1rem',
            fontSize: '0.9rem',
            textAlign: 'center'
          }}>
            {success}
          </div>
        )}

        {!success && (
          <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div className="field" style={{ position: 'relative' }}>
              <label>Nowe hasło</label>
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError(null); }}
                placeholder="••••••••"
                required
                style={{ width: '100%', boxSizing: 'border-box', paddingRight: '40px' }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '32px',
                  background: 'none',
                  border: 'none',
                  color: 'var(--dim)',
                  cursor: 'pointer',
                  padding: '0',
                  display: 'flex',
                  alignItems: 'center'
                }}
                title={showPassword ? "Ukryj hasło" : "Pokaż hasło"}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  {showPassword ? (
                    <>
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                      <line x1="1" y1="1" x2="23" y2="23"></line>
                    </>
                  ) : (
                    <>
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </>
                  )}
                </svg>
              </button>
            </div>

            <div className="field">
              <label>Potwierdź nowe hasło</label>
              <input
                type={showPassword ? "text" : "password"}
                value={confirmPassword}
                onChange={(e) => { setConfirmPassword(e.target.value); setError(null); }}
                placeholder="••••••••"
                required
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
            </div>

            <button
              type="submit"
              className="btn-run"
              disabled={loading}
              style={{ marginTop: '1rem', justifyContent: 'center' }}
            >
              {loading ? <div className="spinner" /> : 'Zmień hasło'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
