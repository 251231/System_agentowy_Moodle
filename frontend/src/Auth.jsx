import React, { useState, useEffect, useRef } from 'react';
import api from './api';

export default function Auth({ onLoginSuccess, onBack }) {
  const [isLogin, setIsLogin] = useState(true);
  const [isForgotPassword, setIsForgotPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const emailRef = useRef(null);

  useEffect(() => {
    if (emailRef.current) {
      emailRef.current.focus();
    }
    setConfirmPassword('');
    setPassword('');
    setError(null);
    setSuccess(null);
  }, [isLogin, isForgotPassword]);

  const handleEmailChange = (e) => { setEmail(e.target.value); setError(null); setSuccess(null); };
  const handlePasswordChange = (e) => { setPassword(e.target.value); setError(null); };
  const handleConfirmPasswordChange = (e) => { setConfirmPassword(e.target.value); setError(null); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (isForgotPassword) {
      setLoading(true);
      try {
        const res = await api.post('/password-recovery', { email });
        setSuccess(res.data.msg);
      } catch (err) {
        setError("Wystąpił błąd. Spróbuj ponownie.");
      } finally {
        setLoading(false);
      }
      return;
    }

    if (!isLogin) {
      if (password.length < 8) {
        setError('Hasło musi mieć co najmniej 8 znaków.');
        return;
      }
      if (password !== confirmPassword) {
        setError('Hasła nie są identyczne.');
        return;
      }
    }

    setLoading(true);

    try {
      if (isLogin) {
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        const res = await api.post('/login/access-token', formData);
        localStorage.setItem('token', res.data.access_token);
        onLoginSuccess();
      } else {
        await api.post('/register', {
          email,
          password
        });
        setIsLogin(true);
        setError("Konto utworzone! Możesz się teraz zalogować.");
      }
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        const detail = err.response.data.detail;
        if (typeof detail === 'string') {
          if (detail === 'Incorrect email or password') {
            setError('Nieprawidłowy e-mail lub hasło.');
          } else if (detail === 'The user with this email already exists in the system.') {
            setError('Użytkownik o tym adresie e-mail już istnieje w systemie.');
          } else {
            setError(detail);
          }
        } else if (Array.isArray(detail)) {
          const messages = detail.map(d => {
            if (d.loc && d.loc.includes('email')) {
              return "Nieprawidłowy format adresu e-mail.";
            }
            return d.msg;
          });
          setError(messages.join(' '));
        } else {
          setError(JSON.stringify(detail));
        }
      } else {
        setError("Wystąpił błąd. Spróbuj ponownie.");
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
          <h2 style={{ color: 'var(--fg)', margin: 0 }}>
            {isForgotPassword ? 'Reset hasła' : (isLogin ? 'Zaloguj się' : 'Stwórz konto')}
          </h2>
          <p style={{ color: 'var(--dim)', marginTop: '0.5rem', fontSize: '0.9rem' }}>
            {isForgotPassword ? 'Podaj e-mail, aby otrzymać link' : 'System Agentowy Moodle'}
          </p>
        </div>

        {error && (
          <div style={{
            padding: '10px',
            backgroundColor: error.includes('utworzone') ? 'rgba(46, 204, 113, 0.1)' : 'rgba(231, 76, 60, 0.1)',
            color: error.includes('utworzone') ? '#2ecc71' : '#e74c3c',
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

        <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="field">
            <label>Email</label>
            <input
              ref={emailRef}
              type="email"
              value={email}
              onChange={handleEmailChange}
              placeholder="adres@email.com"
              required
              style={{ width: '100%', boxSizing: 'border-box' }}
            />
          </div>
          {!isForgotPassword && (
            <>
              <div className="field" style={{ position: 'relative' }}>
                <label>Hasło</label>
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={handlePasswordChange}
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

              {!isLogin && (
                <div className="field">
                  <label>Potwierdź hasło</label>
                  <input
                    type={showPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={handleConfirmPasswordChange}
                    placeholder="••••••••"
                    required
                    style={{ width: '100%', boxSizing: 'border-box' }}
                  />
                </div>
              )}
            </>
          )}

          <button
            type="submit"
            className="btn-run"
            disabled={loading}
            style={{ marginTop: '1rem', justifyContent: 'center' }}
          >
            {loading ? <div className="spinner" /> : (isForgotPassword ? 'Wyślij link' : (isLogin ? 'Zaloguj się' : 'Zarejestruj się'))}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.9rem', color: 'var(--dim)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {isLogin && !isForgotPassword && (
            <div>
              <span
                onClick={() => { setIsForgotPassword(true); setError(null); setSuccess(null); }}
                style={{ color: 'var(--dim)', cursor: 'pointer', textDecoration: 'underline' }}
              >
                Zapomniałeś hasła?
              </span>
            </div>
          )}
          
          {isForgotPassword ? (
            <div>
              Wróć do{' '}
              <span
                onClick={() => { setIsForgotPassword(false); setIsLogin(true); setError(null); setSuccess(null); }}
                style={{ color: 'var(--fg)', cursor: 'pointer', fontWeight: 500, textDecoration: 'underline' }}
              >
                logowania
              </span>
            </div>
          ) : (
            <div>
              {isLogin ? "Nie masz konta? " : "Masz już konto? "}
              <span
                onClick={() => { setIsLogin(!isLogin); setError(null); }}
                style={{ color: 'var(--fg)', cursor: 'pointer', fontWeight: 500, textDecoration: 'underline' }}
              >
                {isLogin ? 'Zarejestruj się' : 'Zaloguj się'}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
