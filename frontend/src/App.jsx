import React, { useState, useEffect, useRef } from 'react';
import api from './api';
import Auth from './Auth';
import ResetPassword from './ResetPassword';
import './App.css';

// test deploy
const API = import.meta.env.VITE_API_URL ?? '';

// ── SVG icons ──────────────────────────────────────────────────────────────
const IconUpload = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

const IconFile = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

const IconX = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const IconDown = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

const IconDl = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);

const IconPlay = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>
);

const IconGrid = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: 'var(--dim)' }}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M3 9h18M9 21V9" />
  </svg>
);

const IconGlobe = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10z" />
  </svg>
);

// ── Language options matching what the backend supports ──────────────────
const LANGUAGES = [
  { code: 'pl', label: 'Polski (PL)' },
  { code: 'en', label: 'Angielski (EN)' },
  { code: 'de', label: 'Niemiecki (DE)' },
  { code: 'fr', label: 'Francuski (FR)' },
];

const TARGET_LANG_TAGS = ['PL', 'EN', 'DE', 'FR'];

const App = () => {
  const [resetToken, setResetToken] = useState(() => {
    return new URLSearchParams(window.location.search).get('token');
  });
  const [file, setFile] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [filter, setFilter] = useState('all');
  const [collapsedSections, setCollapsedSections] = useState({});
  const [config, setConfig] = useState({
    source_lang: 'en',
    target_langs: ['en', 'pl'],
    api_type: 'none',
    api_key: '',
    translate: true,
    generate_h5p: false,
    h5p_types: ['Pytanie / Odpowiedź', 'Pojęcie / Definicja'],
    h5p_level: 'Mieszany (auto)',
    h5p_amount: 5,
    h5p_focus: ['Pojęcia kluczowe', 'Definicje'],
    h5p_instructions: '',
  });
  const [isAuthenticated, setIsAuthenticated] = useState(() => !!localStorage.getItem('token'));
  const [user, setUser] = useState(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const fileInputRef = useRef(null);
  const dropdownRef = useRef(null);

  const toggleH5pType = (val) => setConfig(p => ({
    ...p, h5p_types: p.h5p_types.includes(val) ? p.h5p_types.filter(t => t !== val) : [...p.h5p_types, val]
  }));

  const toggleH5pFocus = (val) => setConfig(p => ({
    ...p, h5p_focus: p.h5p_focus.includes(val) ? p.h5p_focus.filter(t => t !== val) : [...p.h5p_focus, val]
  }));


  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsAuthenticated(false);
    setUser(null);
  };

  const fetchUser = async () => {
    try {
      const res = await api.get('/users/me');
      setUser(res.data);
    } catch (err) {
      console.error("Failed to fetch user profile", err);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchUser();
    } else {
      setUser(null);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // ── polling ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) return;
    
    fetchTasks();
    const id = setInterval(fetchTasks, 3000);
    return () => clearInterval(id);
  }, [isAuthenticated]);

  const fetchTasks = async () => {
    try {
      const res = await api.get('/tasks');
      setTasks(res.data);
    } catch (_) { }
  };

  // ── file handling ───────────────────────────────────────────────────────
  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  };

  const handleFileChange = (e) => {
    if (e.target.files?.[0]) setFile(e.target.files[0]);
  };

  // ── target lang toggle ──────────────────────────────────────────────────
  const toggleTargetLang = (code) => {
    const lower = code.toLowerCase();
    setConfig(prev => {
      const has = prev.target_langs.includes(lower);
      if (has && prev.target_langs.length === 1) return prev; // keep at least one
      return {
        ...prev,
        target_langs: has
          ? prev.target_langs.filter(l => l !== lower)
          : [...prev.target_langs, lower],
      };
    });
  };

  // ── submit ──────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!file) return;
    setIsSubmitting(true);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('translate', config.translate);
    fd.append('generate_h5p', config.generate_h5p);
    fd.append('source_lang', config.source_lang);
    fd.append('target_langs', config.target_langs.join(','));
    fd.append('api_type', config.api_type);
    if (config.api_key) fd.append('api_key', config.api_key);
    fd.append('h5p_types', config.h5p_types.join(','));
    fd.append('h5p_level', config.h5p_level);
    fd.append('h5p_amount', config.h5p_amount);
    fd.append('h5p_focus', config.h5p_focus.join(','));
    fd.append('h5p_instructions', config.h5p_instructions);
    try {
      await api.post('/tasks', fd);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      fetchTasks();
    } catch (_) {
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── cancel ──────────────────────────────────────────────────────────────
  const handleCancel = async (id, e) => {
    e.stopPropagation();
    try {
      await api.post(`/tasks/${id}/cancel`);
      fetchTasks();
    } catch (_) { }
  };

  const handleDownload = async (task, e) => {
    e.stopPropagation();
    e.preventDefault();
    try {
      const response = await api.get(`/download/${task.id}`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `processed_${task.original_filename}`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download error:', err);
      alert('Nie udało się pobrać pliku.');
    }
  };

  const handleDownloadTexts = async (task, e) => {
    e.stopPropagation();
    e.preventDefault();
    try {
      const response = await api.get(`/tasks/${task.id}/texts`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `texts_${task.original_filename.replace('.mbz', '')}.json`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download texts error:', err);
      alert('Nie udało się pobrać pliku tekstów JSON.');
    }
  };

  const handleDownloadH5p = async (task, e) => {
    e.stopPropagation();
    e.preventDefault();
    try {
      const response = await api.get(`/download-h5p/${task.id}`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `quiz_${task.original_filename.replace('.mbz', '.h5p')}`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download H5P error:', err);
      alert('Nie udało się pobrać pliku H5P.');
    }
  };

  // ── helpers ─────────────────────────────────────────────────────────────
  const toggleExpand = (id) => setExpanded(p => ({ ...p, [id]: !p[id] }));

  const toggleSection = (n) =>
    setCollapsedSections(p => ({ ...p, [n]: !p[n] }));

  const filteredTasks = tasks.filter(t => {
    if (filter === 'all') return true;
    if (filter === 'processing') return t.status === 'processing' || t.status === 'pending';
    return t.status === filter;
  });

  const runHint = !file
    ? 'Wybierz plik aby kontynuować'
    : (!config.translate && !config.generate_h5p)
      ? 'Wybierz co najmniej jeden agent'
      : (config.translate && config.target_langs.length === 0)
        ? 'Wybierz co najmniej jeden język docelowy'
        : '';

  const canRun = !!file && (config.translate || config.generate_h5p) && (!config.translate || config.target_langs.length > 0) && !isSubmitting;

  if (resetToken) {
    return <ResetPassword token={resetToken} onResetSuccess={() => {
      setResetToken(null);
      window.history.replaceState({}, document.title, "/");
    }} />;
  }

  if (!isAuthenticated) {
    return <Auth onLoginSuccess={() => setIsAuthenticated(true)} />;
  }

  // ── render ───────────────────────────────────────────────────────────────
  return (
    <div className="layout">
      {/* ── Topbar ── */}
      <header className="topbar">
        <div className="topbar-logo">
          <div className="logo-mark">M</div>
          <span className="logo-text">Moodle AI</span>
        </div>

        <div className="user-menu-container" ref={dropdownRef}>
          <div className="user-menu-trigger" onClick={() => setShowDropdown(!showDropdown)}>
            <div className="user-avatar">
              {user && user.email ? user.email[0].toUpperCase() : 'U'}
            </div>
            <span className="user-name">
              {user ? user.email : 'Wczytywanie...'}
            </span>
            <IconDown />
          </div>

          {showDropdown && (
            <div className="user-dropdown-menu">
              <button className="user-dropdown-item" onClick={handleLogout}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ marginRight: '6px' }}>
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                Wyloguj się
              </button>
            </div>
          )}
        </div>
      </header>

      {/* ── Sidebar ── */}
      <aside className="sidebar">

        {/* Krok 1: Plik */}
        <div className="sidebar-section">
          <div
            className={`sidebar-section-header active`}
            onClick={() => toggleSection(1)}
          >
            <span className="step-num">1</span>
            Plik źródłowy
          </div>
          {!collapsedSections[1] && (
            <div className="sidebar-section-body">
              <div
                className={`dropzone${file ? ' has-file' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={e => e.preventDefault()}
                onDrop={handleDrop}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".mbz"
                  onChange={handleFileChange}
                />
                <div className="dropzone-icon">
                  <IconUpload />
                </div>
                <div className="dropzone-text">
                  {file ? file.name : <>Przeciągnij plik .mbz<br />lub kliknij aby wybrać</>}
                </div>
                <div className="dropzone-hint">
                  {file ? 'Kliknij aby zmienić plik' : 'Moodle Backup Archive'}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Krok 2: Opcje tłumaczenia */}
        <div className="sidebar-section">
          <div
            className="sidebar-section-header active"
            onClick={() => toggleSection(2)}
          >
            <span className="step-num">2</span>
            Opcje tłumaczenia
          </div>
          {!collapsedSections[2] && (
            <div className="sidebar-section-body">
              <div className="agent-tabs" style={{ display: 'flex', gap: '6px', marginBottom: '14px' }}>
              <div className="agent-config-section" style={{ borderTop: 'none', marginTop: 0, paddingTop: 0 }}>
                <div className="agent-config-label">
                  <IconGlobe />
                  Konfiguracja języków
                </div>

                <div className="field">
                  <label>Język źródłowy</label>
                  <select
                    value={config.source_lang}
                    onChange={e => setConfig({ ...config, source_lang: e.target.value })}
                  >
                    {LANGUAGES.map(l => (
                      <option key={l.code} value={l.code}>{l.label}</option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label>Języki docelowe</label>
                  <div className="tag-group lang-group">
                    {TARGET_LANG_TAGS.map(tag => (
                      <span
                        key={tag}
                        className={`tag-item${config.target_langs.includes(tag.toLowerCase()) ? ' active' : ''}`}
                        onClick={() => toggleTargetLang(tag)}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="field">
                  <label>Opcje dodatkowe</label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: 'var(--text)', textTransform: 'none', fontWeight: 400, fontSize: '0.8rem', marginBottom: '8px' }}>
                    <input
                      type="checkbox"
                      checked={config.translate}
                      onChange={e => setConfig({ ...config, translate: e.target.checked })}
                    />
                    Tłumacz kurs na inne języki
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: 'var(--text)', textTransform: 'none', fontWeight: 400, fontSize: '0.8rem' }}>
                    <input
                      type="checkbox"
                      checked={config.generate_h5p}
                      onChange={e => setConfig({ ...config, generate_h5p: e.target.checked })}
                    />
                    Generuj Quiz H5P na podstawie treści
                  </label>
                </div>
              </div>

              {config.generate_h5p && (
                <div className="agent-config-section">
                  <div className="agent-config-label">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="2" y="3" width="20" height="14" rx="2" />
                      <path d="M8 21h8M12 17v4" />
                    </svg>
                    Opcje fiszek
                  </div>

                  <div className="field">
                    <label>Typ fiszek (multi-wybór)</label>
                    <div className="tag-group">
                      {['Pytanie / Odpowiedź', 'Pojęcie / Definicja', 'Uzupełnianie luk', 'Prawda / Fałsz'].map(tag => (
                        <span
                          key={tag}
                          className={`tag-item lg ${config.h5p_types.includes(tag) ? 'active' : ''}`}
                          onClick={() => toggleH5pType(tag)}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="field">
                    <label>Poziom trudności</label>
                    <select
                      value={config.h5p_level}
                      onChange={e => setConfig({ ...config, h5p_level: e.target.value })}
                    >
                      <option value="Mieszany (auto)">Mieszany (auto)</option>
                      <option value="Łatwy">Łatwy</option>
                      <option value="Średni">Średni</option>
                      <option value="Trudny">Trudny</option>
                    </select>
                  </div>

                  <div className="field">
                    <label>Liczba fiszek na moduł</label>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <div className="number-stepper">
                        <button className="stepper-btn" onClick={() => setConfig(p => ({ ...p, h5p_amount: Math.max(1, p.h5p_amount - 1) }))}>−</button>
                        <input className="stepper-val" type="number" value={config.h5p_amount} readOnly />
                        <button className="stepper-btn" onClick={() => setConfig(p => ({ ...p, h5p_amount: Math.min(30, p.h5p_amount + 1) }))}>+</button>
                      </div>
                      <span className="stepper-hint">fiszek / moduł (1–30)</span>
                    </div>
                  </div>

                  <div className="field">
                    <label>Obszary tematyczne</label>
                    <div className="tag-group focus-group">
                      {['Pojęcia kluczowe', 'Definicje', 'Algorytmy', 'Wzory', 'Przykłady kodu', 'Porównania'].map(tag => (
                        <span
                          key={tag}
                          className={`tag-item lg ${config.h5p_focus.includes(tag) ? 'active' : ''}`}
                          onClick={() => toggleH5pFocus(tag)}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="field">
                    <label>Dodatkowe instrukcje dla AI</label>
                    <textarea
                      placeholder="np. Skup się na zastosowaniach praktycznych. Używaj przykładów w Pythonie. Unikaj teorii formalnej..."
                      value={config.h5p_instructions}
                      onChange={e => setConfig({ ...config, h5p_instructions: e.target.value })}
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Krok 3: Silnik AI */}
        <div className="sidebar-section">
          <div
            className="sidebar-section-header active"
            onClick={() => toggleSection(3)}
          >
            <span className="step-num">3</span>
            Silnik AI
          </div>
          {!collapsedSections[3] && (
            <div className="sidebar-section-body">
              <div className="field">
                <label>Silnik tłumaczenia</label>
                <select
                  value={config.api_type}
                  onChange={e => setConfig({ ...config, api_type: e.target.value })}
                >
                  <option value="none">Mock (bez AI)</option>
                  <option value="openai">OpenAI GPT-4o</option>
                  <option value="deepl">DeepL</option>
                  <option value="gemini">Gemini AI Studio</option>
                  <option value="openrouter">OpenRouter (Auto Free Tier)</option>
                </select>
              </div>

              {config.api_type !== 'none' && (
                <div className="field">
                  <label>Klucz API</label>
                  <input
                    type="password"
                    value={config.api_key}
                    onChange={e => setConfig({ ...config, api_key: e.target.value })}
                    placeholder="sk-..."
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sidebar-footer">
          <button
            className="btn-run"
            disabled={!canRun}
            onClick={handleSubmit}
          >
            {isSubmitting
              ? <><div className="spinner" style={{ borderColor: 'rgba(255,255,255,.2)', borderTopColor: '#fff' }} /> Wysyłanie...</>
              : <><IconPlay /> Uruchom Agenty</>
            }
          </button>
          <div className="run-hint">{runHint}</div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main">
        <div className="task-panel-header">
          <IconGrid />
          <span className="task-panel-title">Monitor Zadań</span>
          <div className="filter-tabs">
            {[
              { key: 'all', label: 'Wszystkie' },
              { key: 'processing', label: 'W toku' },
              { key: 'completed', label: 'Ukończone' },
              { key: 'failed', label: 'Błędy' },
            ].map(f => (
              <button
                key={f.key}
                className={`filter-tab${filter === f.key ? ' active' : ''}`}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="task-list">
          {filteredTasks.length === 0 ? (
            <div className="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" style={{ opacity: 0.3, color: 'var(--muted)' }}>
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18" />
              </svg>
              <p>Brak zadań w tej kategorii.</p>
            </div>
          ) : (
            filteredTasks.map(task => {
              const isExpanded = expanded[task.id];
              const isActive = task.status === 'processing' || task.status === 'pending';

              let iconEl, iconClass = 'task-icon';
              if (isActive) {
                iconEl = <div className="spinner" />;
                iconClass = 'task-icon';
              } else if (task.status === 'failed') {
                iconEl = <IconX />;
                iconClass = 'task-icon err';
              } else if (task.status === 'cancelled') {
                iconEl = <IconX />;
                iconClass = 'task-icon muted';
              } else {
                iconEl = <IconFile />;
              }

              return (
                <div
                  key={task.id}
                  className={`task-card status-${task.status}${isExpanded ? ' expanded' : ''}`}
                >
                  <div className="task-card-main" onClick={() => toggleExpand(task.id)}>
                    <div className={iconClass} style={isActive ? { background: 'transparent', border: 'none' } : {}}>
                      {iconEl}
                    </div>

                    <div className="task-info">
                      <div className="task-name">{task.original_filename}</div>
                      <div className="task-meta">
                        <span className="task-agent-tag">Tłumaczenie</span>
                        <span style={{ fontSize: '0.62rem', color: 'var(--dim)', fontFamily: 'monospace' }}>
                          #{task.id.split('-')[0]}
                        </span>
                      </div>
                    </div>

                    <div className="task-right">
                      {isActive && (
                        <button
                          className="btn-cancel-task"
                          onClick={(e) => handleCancel(task.id, e)}
                        >
                          Zatrzymaj
                        </button>
                      )}
                      {isActive && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontSize: '0.72rem', color: 'var(--muted)', fontWeight: 600 }}>
                            Przetwarzanie... {task.progress || 0}%
                          </span>
                          <div style={{ width: '60px', height: '4px', background: 'var(--border-hi)', borderRadius: '2px', overflow: 'hidden' }}>
                            <div style={{ width: `${task.progress || 0}%`, height: '100%', background: 'var(--primary)', transition: 'width 0.3s ease' }}></div>
                          </div>
                        </div>
                      )}
                      {task.status === 'failed' && (
                        <span className="badge-error"><IconX /> Błąd</span>
                      )}
                      {task.status === 'cancelled' && (
                        <span className="badge-cancelled">Anulowano</span>
                      )}
                      {task.status === 'completed' && (
                        <div style={{ display: 'flex', gap: '8px' }}>
                          {task.h5p_filename && (
                            <button
                              className="btn-dl"
                              onClick={e => handleDownloadH5p(task, e)}
                              style={{ background: 'var(--primary)', borderColor: 'var(--primary)', color: '#fff' }}
                              title="Pobierz wygenerowany Quiz H5P"
                            >
                              <IconDl /> Quiz H5P
                            </button>
                          )}
                          <button
                            className="btn-dl"
                            onClick={e => handleDownloadTexts(task, e)}
                            style={{ background: 'var(--raised)', borderColor: 'var(--border-hi)' }}
                            title="Pobierz wyekstrahowane i przetłumaczone teksty w formacie JSON"
                          >
                            <IconDl /> Teksty (JSON)
                          </button>
                          <button
                            className="btn-dl"
                            onClick={e => handleDownload(task, e)}
                          >
                            <IconDl /> Pobierz MBZ
                          </button>
                        </div>
                      )}
                      {task.subtasks?.length > 0 && (
                        <span className="expand-arrow"><IconDown /></span>
                      )}
                    </div>
                  </div>

                  {/* Subtasks */}
                  {isExpanded && task.subtasks?.length > 0 && (
                    <div className="task-subtasks" style={{ display: 'flex' }}>
                      {task.subtasks.map((st, i) => {
                        let stIcon;
                        if (st.status === 'processing') stIcon = <div className="spinner-sm" />;
                        else if (st.status === 'completed') stIcon = <span className="subtask-done">✓</span>;
                        else if (st.status === 'failed') stIcon = <span className="subtask-fail">✕</span>;
                        else stIcon = <span className="subtask-done" style={{ opacity: 0.4 }}>−</span>;

                        return (
                          <div key={i} className="subtask-row">
                            {stIcon}
                            <span className="subtask-name">{st.agent}</span>
                            <span className="subtask-log">{st.log}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </main>
    </div>
  );
};

export default App;
