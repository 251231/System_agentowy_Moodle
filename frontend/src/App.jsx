import React, { useState, useEffect, useRef } from 'react';
import api from './api';
import Auth from './Auth';
import ResetPassword from './ResetPassword';
import LandingPage from './LandingPage';
import Topbar from './components/Topbar';
import Sidebar from './components/Sidebar';
import TaskCard from './components/TaskCard';
import { IconGrid } from './components/Icons';
import './App.css';

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
  const [selectedLinks, setSelectedLinks] = useState({});

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
      setSelectedLinks(prev => ({ ...prev, [taskId]: [] }));
      const updatedReport = await api.get(`/tasks/${taskId}/links`);
      setLinksReports(prev => ({ ...prev, [taskId]: updatedReport.data }));
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

  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  };

  const handleFileChange = (e) => {
    if (e.target.files?.[0]) setFile(e.target.files[0]);
  };

  const toggleTargetLang = (code) => {
    const lower = code.toLowerCase();
    setConfig(prev => {
      const has = prev.target_langs.includes(lower);
      if (has && prev.target_langs.length === 1) return prev;
      return {
        ...prev,
        target_langs: has
          ? prev.target_langs.filter(l => l !== lower)
          : [...prev.target_langs, lower],
      };
    });
  };

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

  return (
    <div className="layout">
      <Topbar
        user={user}
        showDropdown={showDropdown}
        setShowDropdown={setShowDropdown}
        handleLogout={handleLogout}
        dropdownRef={dropdownRef}
      />

      <Sidebar
        file={file}
        setFile={setFile}
        fileInputRef={fileInputRef}
        handleDrop={handleDrop}
        handleFileChange={handleFileChange}
        config={config}
        setConfig={setConfig}
        toggleTargetLang={toggleTargetLang}
        toggleH5pType={toggleH5pType}
        toggleH5pFocus={toggleH5pFocus}
        collapsedSections={collapsedSections}
        toggleSection={toggleSection}
        isSubmitting={isSubmitting}
        handleSubmit={handleSubmit}
        canRun={canRun}
        runHint={runHint}
        LANGUAGES={LANGUAGES}
        TARGET_LANG_TAGS={TARGET_LANG_TAGS}
      />

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
            filteredTasks.map(task => (
              <TaskCard
                key={task.id}
                task={task}
                isExpanded={!!expanded[task.id]}
                toggleExpand={toggleExpand}
                handleCancel={handleCancel}
                handleDownload={handleDownload}
                handleDownloadTexts={handleDownloadTexts}
                handleDownloadH5p={handleDownloadH5p}
                handleDownloadLinks={handleDownloadLinks}
                fetchLinksReport={fetchLinksReport}
                expandedLinksReport={expandedLinksReport}
                linksReports={linksReports}
                selectedLinks={selectedLinks}
                toggleSelectLink={toggleSelectLink}
                toggleSelectAll={toggleSelectAll}
                handleReplaceSelectedLinks={handleReplaceSelectedLinks}
                handleApproveLinks={handleApproveLinks}
              />
            ))
          )}
        </div>
      </main>
    </div>
  );
};

export default App;
