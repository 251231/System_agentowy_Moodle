import React, { useState, useEffect, useRef } from 'react';
import api from './api';
import Auth from './Auth';
import ResetPassword from './ResetPassword';
import LandingPage from './LandingPage';
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

const IconCards = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="2" y="3" width="20" height="14" rx="2" />
    <path d="M8 21h8M12 17v4" />
  </svg>
);

const IconLink = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
  </svg>
);

const IconText = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
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
    api_type: 'openrouter',
    api_key: '',
    translate: true,
    generate_h5p: false,
    check_links: false,
    extract_texts: false,
    h5p_types: ['Quiz (ABCD)'],
    h5p_level: 'Mieszany (auto)',
    h5p_amount: 5,
    h5p_focus: [],
    h5p_instructions: '',
  });
  const [linksReports, setLinksReports] = useState({});
  const [expandedLinksReport, setExpandedLinksReport] = useState(null);
  const [selectedLinks, setSelectedLinks] = useState({}); // task_id -> array of link indices

  const toggleSelectLink = (taskId, idx) => {
    setSelectedLinks(prev => {
      const current = prev[taskId] || [];
      const updated = current.includes(idx)
        ? current.filter(i => i !== idx)
        : [...current, idx];
      return { ...prev, [taskId]: updated };
    });
  };

  const toggleSelectAll = (taskId, brokenLinksIndices) => {
    setSelectedLinks(prev => {
      const current = prev[taskId] || [];
      const allSelected = brokenLinksIndices.every(idx => current.includes(idx));
      const updated = allSelected ? [] : brokenLinksIndices;
      return { ...prev, [taskId]: updated };
    });
  };

  const handleReplaceSelectedLinks = async (taskId) => {
    const selectedIndices = selectedLinks[taskId] || [];
    if (selectedIndices.length === 0) return;

    const report = linksReports[taskId];
    if (!report) return;

    const replacements = selectedIndices.map(idx => {
      const link = report.links[idx];
      return {
        url: link.url,
        suggested_url: link.suggested_url,
        archive_path: link.archive_path || ''
      };
    }).filter(r => r.suggested_url);

    if (replacements.length === 0) {
      alert("Żaden z zaznaczonych linków nie ma sugerowanego zamiennika.");
      return;
    }

    if (!window.confirm(`Czy na pewno chcesz zastąpić te ${replacements.length} linki w pliku MBZ?`)) {
      return;
    }

    try {
      const res = await api.post(`/tasks/${taskId}/replace-links`, { replacements });
      alert(`Pomyślnie zaktualizowano ${res.data.replaced_files_count} plików w archiwum MBZ.`);
      // Clear selection
      setSelectedLinks(prev => ({ ...prev, [taskId]: [] }));
      // Refetch links report to show updated state
      const updatedReport = await api.get(`/tasks/${taskId}/links`);
      setLinksReports(prev => ({ ...prev, [taskId]: updatedReport.data }));
      // Refetch tasks so the approve state in task is updated
      fetchTasks();
    } catch (err) {
      console.error("Failed to replace links:", err);
      alert("Wystąpił błąd podczas zastępowania linków.");
    }
  };

  const handleApproveLinks = async (taskId, e) => {
    if (e) {
      e.stopPropagation();
      e.preventDefault();
    }
    if (!window.confirm("Czy na pewno chcesz zatwierdzić stan linków i odblokować pobieranie MBZ?")) {
      return;
    }
    try {
      await api.post(`/tasks/${taskId}/approve-links`);
      alert("Odblokowano pobieranie pliku MBZ.");
      fetchTasks();
    } catch (err) {
      console.error("Failed to approve links:", err);
      alert("Wystąpił błąd podczas zatwierdzania linków.");
    }
  };
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

  const fetchLinksReport = async (taskId) => {
    if (expandedLinksReport === taskId) {
      setExpandedLinksReport(null);
      return;
    }
    if (linksReports[taskId]) {
      setExpandedLinksReport(taskId);
      return;
    }
    try {
      const res = await api.get(`/tasks/${taskId}/links`);
      setLinksReports(p => ({ ...p, [taskId]: res.data }));
      setExpandedLinksReport(taskId);
    } catch (err) {
      console.error('Failed to fetch links report:', err);
      alert('Nie udało się pobrać raportu linków.');
    }
  };

  const handleDownloadLinks = async (task, e) => {
    e.stopPropagation();
    e.preventDefault();
    try {
      const response = await api.get(`/tasks/${task.id}/links`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `links_${task.original_filename.replace('.mbz', '')}.json`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download links error:', err);
      alert('Nie udało się pobrać raportu linków JSON.');
    }
  };

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
    fd.append('check_links', config.check_links);
    fd.append('extract_texts', config.extract_texts);
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
      link.setAttribute('download', `h5p_${task.original_filename.replace('.mbz', '.h5p')}`);
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
    : (!config.translate && !config.generate_h5p && !config.check_links && !config.extract_texts)
      ? 'Wybierz co najmniej jeden agent'
      : (config.translate && config.target_langs.length === 0)
        ? 'Wybierz co najmniej jeden język docelowy'
        : '';

  const canRun = !!file && (config.translate || config.generate_h5p || config.check_links || config.extract_texts) && (!config.translate || config.target_langs.length > 0) && !isSubmitting;

  const [showAuth, setShowAuth] = useState(window.location.hash === '#login');

  useEffect(() => {
    const handleHashChange = () => {
      setShowAuth(window.location.hash === '#login');
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  if (resetToken) {
    return <ResetPassword token={resetToken} onResetSuccess={() => {
      setResetToken(null);
      window.history.replaceState({}, document.title, "/");
    }} />;
  }

  if (!isAuthenticated) {
    if (showAuth) {
      return <Auth 
        onLoginSuccess={() => {
          window.location.hash = '';
          setIsAuthenticated(true);
        }} 
        onBack={() => {
          if (window.history.state !== null || window.history.length > 1) {
            window.history.back();
          } else {
            window.location.hash = '';
          }
        }} 
      />;
    }
    return <LandingPage onLoginClick={() => window.location.hash = '#login'} />;
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

        {/* Krok 2: Wybierz agenty */}
        <div className="sidebar-section">
          <div
            className="sidebar-section-header active"
            onClick={() => toggleSection(2)}
          >
            <span className="step-num">2</span>
            Wybierz agenty
          </div>
          {!collapsedSections[2] && (
            <div className="sidebar-section-body">
              <div className="agent-tabs">
                <button 
                  className={`agent-tab ${config.translate ? 'active' : ''}`}
                  onClick={() => setConfig(p => ({ ...p, translate: !p.translate }))}
                >
                  <IconGlobe /> Tłumaczenie
                </button>
                <button 
                  className={`agent-tab ${config.generate_h5p ? 'active' : ''}`}
                  onClick={() => setConfig(p => ({ ...p, generate_h5p: !p.generate_h5p }))}
                >
                  <IconCards /> Materiały H5P
                </button>
                <button 
                  className={`agent-tab ${config.check_links ? 'active' : ''}`}
                  onClick={() => setConfig(p => ({ ...p, check_links: !p.check_links }))}
                >
                  <IconLink /> Linki
                </button>
                <button 
                  className={`agent-tab ${config.extract_texts ? 'active' : ''}`}
                  onClick={() => setConfig(p => ({ ...p, extract_texts: !p.extract_texts }))}
                >
                  <IconText /> Parser tekstu
                </button>
              </div>

              {config.translate && (
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
                </div>
              )}

              {config.generate_h5p && (
                <div className="agent-config-section">
                  <div className="agent-config-label">
                    <IconCards />
                    Opcje treści H5P
                  </div>

                  <div className="field">
                    <label>Format zawartości</label>
                    <div className="tag-group">
                      {['Quiz (ABCD)', 'Fiszki', 'Uzupełnianie luk', 'Prawda / Fałsz'].map(tag => (
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
                    <label>Obszar tematyczny <span style={{fontSize:'11px', opacity: 0.5, fontWeight: 400}}>(opcjonalnie – zostaw puste = mieszany)</span></label>
                    <div className="tag-group focus-group">
                      {['Pojęcia kluczowe', 'Definicje i terminy', 'Przykłady praktyczne', 'Zastosowania', 'Porównania', 'Podsumowanie'].map(tag => (
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
                    <label>Liczba elementów</label>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <div className="number-stepper">
                        <button className="stepper-btn" onClick={() => setConfig(p => ({ ...p, h5p_amount: Math.max(1, p.h5p_amount - 1) }))}>−</button>
                        <input className="stepper-val" type="number" value={config.h5p_amount} readOnly />
                        <button className="stepper-btn" onClick={() => setConfig(p => ({ ...p, h5p_amount: Math.min(30, p.h5p_amount + 1) }))}>+</button>
                      </div>
                      <span className="stepper-hint">elementów (1–30)</span>
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

              {config.check_links && (
                <div className="agent-config-section">
                  <div className="agent-config-label">
                    <IconLink />
                    Weryfikacja linków
                  </div>
                  <div className="field">
                    <span style={{fontSize: '0.8rem', color: 'var(--muted)'}}>Automatyczna weryfikacja wszystkich odnośników w kursie pod kątem ich poprawności. Raport zostanie udostępniony po zakończeniu analizy.</span>
                  </div>
                </div>
              )}

              {config.extract_texts && (
                <div className="agent-config-section">
                  <div className="agent-config-label">
                    <IconText />
                    Parser tekstu
                  </div>
                  <div className="field">
                    <span style={{fontSize: '0.8rem', color: 'var(--muted)'}}>Wyodrębnia całą zawartość tekstową z kursu i zapisuje ją do pliku JSON bez modyfikowania archiwum MBZ. Przydatne do analizy treści lub niezależnego tłumaczenia.</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Silnik AI is managed via server env key */}

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
                        {(() => {
                          const isTranslate = task.config?.translate === true || task.config?.translate === 'true';
                          const isH5p = task.config?.generate_h5p === true || task.config?.generate_h5p === 'true';
                          const isLinks = task.config?.check_links === true || task.config?.check_links === 'true';
                          const isExtract = task.config?.extract_texts === true || task.config?.extract_texts === 'true';
                          const hasAny = isTranslate || isH5p || isLinks || isExtract;
                          
                          return (
                            <>
                              {isTranslate && <span className="task-agent-tag">Tłumaczenie</span>}
                              {isH5p && <span className="task-agent-tag">H5P</span>}
                              {isLinks && <span className="task-agent-tag">Linki</span>}
                              {isExtract && <span className="task-agent-tag">Parser tekstu</span>}
                              {!hasAny && <span className="task-agent-tag">Tłumaczenie</span>}
                            </>
                          );
                        })()}
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
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                          {task.has_links_report && (
                            <button
                              className="btn-dl"
                              onClick={e => {
                                e.stopPropagation();
                                e.preventDefault();
                                fetchLinksReport(task.id);
                                if (expandedLinksReport !== task.id) {
                                  setExpanded(p => ({ ...p, [task.id]: true }));
                                }
                              }}
                              style={{ background: 'linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)', borderColor: '#2a5298', color: '#fff' }}
                              title="Pokaż interaktywny raport z weryfikacji linków"
                            >
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ marginRight: '4px' }}>
                                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                              </svg>
                              {expandedLinksReport === task.id ? 'Ukryj linki' : 'Raport linków'}
                            </button>
                          )}
                          {task.has_links_report && (
                            <button
                              className="btn-dl"
                              onClick={e => handleDownloadLinks(task, e)}
                              style={{ background: 'var(--raised)', borderColor: 'var(--border-hi)' }}
                              title="Pobierz raport weryfikacji linków w formacie JSON"
                            >
                              <IconDl /> Raport (JSON)
                            </button>
                          )}
                          {task.h5p_filename && (
                            <button
                              className="btn-dl"
                              onClick={e => handleDownloadH5p(task, e)}
                              style={{ background: 'var(--primary)', borderColor: 'var(--primary)', color: '#fff' }}
                              title="Pobierz wygenerowane treści H5P"
                            >
                              <IconDl /> Treści H5P
                            </button>
                          )}
                          {task.has_texts_report && (
                            <button
                              className="btn-dl"
                              onClick={e => handleDownloadTexts(task, e)}
                              style={{ background: 'var(--raised)', borderColor: 'var(--border-hi)' }}
                              title="Pobierz wyekstrahowane teksty w formacie JSON"
                            >
                              <IconDl /> Teksty (JSON)
                            </button>
                          )}
                          {(() => {
                            const isTranslate = task.config?.translate === true || task.config?.translate === 'true';
                            const isH5p = task.config?.generate_h5p === true || task.config?.generate_h5p === 'true';
                            const isLinks = task.config?.check_links === true || task.config?.check_links === 'true';
                            const isApproved = task.config?.links_approved === true || task.config?.links_approved === 'true';
                            
                            const hasMbzOutput = isTranslate || isLinks || isH5p;
                            
                            if (!hasMbzOutput) return null;
                            
                            if (isLinks && !isApproved) {
                              return (
                                <button
                                  className="btn-dl"
                                  onClick={e => handleApproveLinks(task.id, e)}
                                  style={{ background: 'var(--primary)', borderColor: 'var(--primary)', color: '#fff' }}
                                  title="Zatwierdź status linków, aby odblokować pobieranie MBZ"
                                >
                                  Zatwierdź linki
                                </button>
                              );
                            }
                            
                            return (
                              <button
                                className="btn-dl"
                                onClick={e => handleDownload(task, e)}
                              >
                                <IconDl /> Pobierz MBZ
                              </button>
                            );
                          })()}
                        </div>
                      )}
                      {(task.subtasks?.length > 0 || task.has_links_report) && (
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

                  {/* Links Report Interactive View */}
                  {isExpanded && expandedLinksReport === task.id && linksReports[task.id] && (
                    <div className="links-report-container" onClick={e => e.stopPropagation()} style={{ display: 'block', margin: '12px 16px 16px' }}>
                      <div className="links-report-header">
                        <div className="links-report-title">Weryfikacja Linków Zewnętrznych</div>
                        <div className="links-report-summary-stats">
                          <span className="stat-badge total">Wszystkie: <strong>{linksReports[task.id].summary.total}</strong></span>
                          <span className="stat-badge active">Aktywne: <strong>{linksReports[task.id].summary.active}</strong></span>
                          <span className="stat-badge broken">Nieaktywne: <strong>{linksReports[task.id].summary.broken}</strong></span>
                        </div>
                      </div>
                      
                      {linksReports[task.id].links.length === 0 ? (
                        <div className="links-report-empty">Nie wykryto żadnych linków zewnętrznych w tym kursie.</div>
                      ) : (
                        <div className="links-table-wrapper">
                          <table className="links-report-table">
                            <thead>
                              <tr>
                                <th style={{ width: '40px', textAlign: 'center' }}>
                                  <input 
                                    type="checkbox" 
                                    checked={
                                      (() => {
                                        const brokenIndices = linksReports[task.id].links
                                          .map((l, i) => ({ l, i }))
                                          .filter(item => !item.l.is_active)
                                          .map(item => item.i);
                                        const selected = selectedLinks[task.id] || [];
                                        return brokenIndices.length > 0 && brokenIndices.every(idx => selected.includes(idx));
                                      })()
                                    }
                                    onChange={() => {
                                      const brokenIndices = linksReports[task.id].links
                                        .map((l, i) => ({ l, i }))
                                        .filter(item => !item.l.is_active)
                                        .map(item => item.i);
                                      toggleSelectAll(task.id, brokenIndices);
                                    }}
                                  />
                                </th>
                                <th>Adres URL</th>
                                <th>Lokalizacja w kursie</th>
                                <th>Status</th>
                                <th>Sugestia AI (Rozwiązanie)</th>
                              </tr>
                            </thead>
                            <tbody>
                              {linksReports[task.id].links.map((link, idx) => (
                                <tr key={idx} className={link.is_active ? "row-active" : "row-broken"}>
                                  <td style={{ textAlign: 'center' }}>
                                    {!link.is_active && link.suggested_url && (
                                      <input 
                                        type="checkbox"
                                        checked={(selectedLinks[task.id] || []).includes(idx)}
                                        onChange={() => toggleSelectLink(task.id, idx)}
                                      />
                                    )}
                                  </td>
                                  <td className="url-cell" title={link.url}>
                                    {link.is_active ? (
                                      <a href={link.url} target="_blank" rel="noopener noreferrer" className="external-link-anchor">
                                        {link.url}
                                      </a>
                                    ) : (
                                      <span style={{ color: 'var(--text-muted)', textDecoration: 'line-through', opacity: 0.6 }}>
                                        {link.url}
                                      </span>
                                    )}
                                  </td>
                                  <td className="context-cell">
                                    {link.context}
                                  </td>
                                  <td className="status-cell">
                                    {link.is_active ? (
                                      <span className="link-badge ok">Aktywny</span>
                                    ) : (
                                      <span className="link-badge fail" title={link.error || "Błąd połączenia"}>
                                        Nieaktywny
                                        {link.error && (
                                          <div style={{ fontSize: '0.68rem', opacity: 0.85, marginTop: '3px', fontWeight: 'normal', whiteSpace: 'pre-wrap' }}>
                                            {link.error}
                                          </div>
                                        )}
                                      </span>
                                    )}
                                  </td>
                                  <td className="suggestion-cell">
                                    {link.is_active ? (
                                      <span className="no-suggestion">—</span>
                                    ) : (
                                      <div className="suggestion-box">
                                        <div className="suggested-url-wrapper">
                                          <a href={link.suggested_url} target="_blank" rel="noopener noreferrer" className="suggested-url-link">
                                            {link.suggested_url}
                                          </a>
                                          <button 
                                            className="btn-copy-url" 
                                            onClick={() => {
                                              navigator.clipboard.writeText(link.suggested_url);
                                              alert("Skopiowano link do schowka!");
                                            }}
                                            title="Skopiuj sugerowany URL"
                                          >
                                            Kopiuj
                                          </button>
                                        </div>
                                        <div className="suggestion-reason">{link.reason}</div>
                                      </div>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {selectedLinks[task.id]?.length > 0 && (
                            <div className="replace-links-action-bar" style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
                              <button
                                className="btn-replace-links"
                                onClick={() => handleReplaceSelectedLinks(task.id)}
                                style={{
                                  background: 'var(--primary)',
                                  border: '1px solid var(--primary)',
                                  color: '#fff',
                                  fontWeight: 'bold',
                                  padding: '8px 16px',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontFamily: 'inherit',
                                  fontSize: '0.78rem',
                                  textTransform: 'uppercase',
                                  letterSpacing: '0.06em',
                                  transition: 'background 0.2s'
                                }}
                              >
                                Zastąp zaznaczone linki ({selectedLinks[task.id].length})
                              </button>
                            </div>
                          )}
                        </div>
                      )}
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
