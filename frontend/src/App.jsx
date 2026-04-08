import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Upload, Settings as SettingsIcon, FileCheck, Loader2,
    Download, AlertCircle, BookOpen, Layers, Languages,
    ChevronLeft, ChevronRight, Sparkles, Info
} from 'lucide-react';
import './App.css';

const FLASH_PER_PAGE = 8;

/* ── Reusable dropzone ─────────────────────────────────────────────────────── */
const Dropzone = ({ id, file, onChange }) => (
    <div className={`dropzone ${file ? 'has-file' : ''}`}>
        <input type="file" id={id} accept=".mbz" onChange={onChange} />
        <label htmlFor={id}>
            <div className="icon-wrapper"><FileCheck size={38} /></div>
            <span>{file ? file.name : 'Przeciągnij plik .mbz lub kliknij'}</span>
        </label>
    </div>
);

/* ── API config panel ──────────────────────────────────────────────────────── */
const ApiConfig = ({ apiType, apiKey, onChange }) => (
    <div className="api-config-row">
        <div className="input-group" style={{ flex: 1 }}>
            <label>Silnik tłumaczenia / AI</label>
            <select value={apiType} onChange={e => onChange('apiType', e.target.value)}>
                <option value="none">Brak API (tryb testowy)</option>
                <option value="openai">OpenAI (GPT-4o)</option>
                <option value="deepl">DeepL</option>
            </select>
        </div>
        {apiType !== 'none' && (
            <div className="input-group" style={{ flex: 1 }}>
                <label>Klucz API</label>
                <input type="password" value={apiKey} placeholder="sk-…"
                    onChange={e => onChange('apiKey', e.target.value)} />
            </div>
        )}
    </div>
);

/* ══════════════════════════════════════════════════════════════════════════════
   Main App
══════════════════════════════════════════════════════════════════════════════ */
const App = () => {
    const [activeTab, setActiveTab] = useState('translate');

    /* ── Translation state ────────────────────────────────────────────────── */
    const [file, setFile] = useState(null);
    const [status, setStatus] = useState('idle');
    const [taskId, setTaskId] = useState(null);
    const [config, setConfig] = useState({ sourceLang: 'en', targetLangs: 'en,pl', apiType: 'none', apiKey: '' });

    const resetTranslate = () => {
        setFile(null); setStatus('idle'); setTaskId(null);
        const fi = document.getElementById('fileInput');
        if (fi) fi.value = '';
    };

    const handleFileChange = e => {
        if (e.target.files[0]) { setFile(e.target.files[0]); setStatus('idle'); setTaskId(null); }
    };

    const startTranslation = async () => {
        if (!file) return;
        setStatus('uploading');
        const fd = new FormData();
        fd.append('file', file);
        fd.append('source_lang', config.sourceLang);
        fd.append('target_langs', config.targetLangs);
        fd.append('api_type', config.apiType);
        if (config.apiKey) fd.append('api_key', config.apiKey);
        try {
            const res = await axios.post('/api/translate', fd);
            setTaskId(res.data.task_id);
            setStatus('processing');
        } catch { setStatus('error'); }
    };

    useEffect(() => {
        let iv;
        if (status === 'processing' && taskId) {
            iv = setInterval(async () => {
                try {
                    const res = await axios.get(`/api/status/${taskId}`);
                    if (res.data.status === 'completed') { setStatus('completed'); clearInterval(iv); }
                    else if (res.data.status === 'failed') { setStatus('error'); clearInterval(iv); }
                } catch {}
            }, 2000);
        }
        return () => clearInterval(iv);
    }, [status, taskId]);

    /* ── Flashcards state ─────────────────────────────────────────────────── */
    const [flashFile, setFlashFile] = useState(null);
    const [flashStatus, setFlashStatus] = useState('idle');
    const [flashcards, setFlashcards] = useState([]);
    const [flashPage, setFlashPage] = useState(0);
    const [flashConfig, setFlashConfig] = useState({ apiType: 'none', apiKey: '' });

    const resetFlash = () => {
        setFlashFile(null); setFlashStatus('idle'); setFlashcards([]); setFlashPage(0);
        const fi = document.getElementById('flashFileInput');
        if (fi) fi.value = '';
    };

    const handleFlashFileChange = e => {
        if (e.target.files[0]) { setFlashFile(e.target.files[0]); setFlashStatus('idle'); setFlashcards([]); setFlashPage(0); }
    };

    const generateFlashcards = async () => {
        if (!flashFile) return;
        setFlashStatus('loading');
        const fd = new FormData();
        fd.append('file', flashFile);
        fd.append('api_type', flashConfig.apiType);
        if (flashConfig.apiKey) fd.append('api_key', flashConfig.apiKey);
        try {
            const res = await axios.post('/api/flashcards', fd);
            if (res.data.error) { setFlashStatus('error'); return; }
            setFlashcards(res.data.flashcards || []);
            setFlashPage(0);
            setFlashStatus('done');
        } catch { setFlashStatus('error'); }
    };

    const downloadCsv = async () => {
        if (!flashFile) return;
        const fd = new FormData();
        fd.append('file', flashFile);
        fd.append('api_type', flashConfig.apiType);
        if (flashConfig.apiKey) fd.append('api_key', flashConfig.apiKey);
        try {
            const res = await axios.post('/api/flashcards-csv', fd, { responseType: 'blob' });
            const url = URL.createObjectURL(res.data);
            const a = document.createElement('a'); a.href = url; a.download = 'flashcards.csv'; a.click();
            URL.revokeObjectURL(url);
        } catch {}
    };

    const totalPages = Math.ceil(flashcards.length / FLASH_PER_PAGE);
    const pagedCards = flashcards.slice(flashPage * FLASH_PER_PAGE, (flashPage + 1) * FLASH_PER_PAGE);

    const badgeClass = src => {
        if (src === 'pojęcie' || src === 'definicja') return 'badge-glossary';
        if (src === 'zasada' || src === 'proces') return 'badge-quiz';
        if (src === 'extract') return 'badge-activity';
        return 'badge-activity';
    };

    /* ── Render ───────────────────────────────────────────────────────────── */
    return (
        <div className="app-container">
            <div className="background-shapes">
                <div className="shape shape-1" /><div className="shape shape-2" />
            </div>
            <main className="content">
                <motion.header initial={{ y: -50, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.7 }}>
                    <h1>Moodle MBZ Toolkit</h1>
                    <p>Tłumaczenie kursów i generowanie fiszek AI w jednym miejscu.</p>
                </motion.header>

                {/* Tab bar */}
                <div className="tab-bar">
                    <button id="tab-translate" className={`tab-btn${activeTab === 'translate' ? ' active' : ''}`}
                        onClick={() => setActiveTab('translate')}>
                        <Languages size={16} /> Tłumaczenie
                    </button>
                    <button id="tab-flashcards" className={`tab-btn${activeTab === 'flashcards' ? ' active' : ''}`}
                        onClick={() => setActiveTab('flashcards')}>
                        <BookOpen size={16} /> Fiszki AI
                    </button>
                </div>

                <AnimatePresence mode="wait">
                    {/* ══ TRANSLATION TAB ══ */}
                    {activeTab === 'translate' && (
                        <motion.div key="translate" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.25 }} className="glass-grid">

                            <section className="config-panel">
                                <div className="panel-header"><SettingsIcon size={19} /><h2>Konfiguracja</h2></div>

                                <div className="input-group">
                                    <label>Język źródłowy</label>
                                    <input type="text" value={config.sourceLang} placeholder="np. en"
                                        onChange={e => setConfig({ ...config, sourceLang: e.target.value })} />
                                </div>
                                <div className="input-group">
                                    <label>Języki docelowe (po przecinku)</label>
                                    <input type="text" value={config.targetLangs} placeholder="np. en,pl,de"
                                        onChange={e => setConfig({ ...config, targetLangs: e.target.value })} />
                                </div>
                                <div className="input-group">
                                    <label>Silnik tłumaczenia</label>
                                    <select value={config.apiType}
                                        onChange={e => setConfig({ ...config, apiType: e.target.value })}>
                                        <option value="none">Brak API (prefiks [PL])</option>
                                        <option value="openai">OpenAI (GPT-4o)</option>
                                        <option value="deepl">DeepL</option>
                                    </select>
                                </div>
                                {config.apiType !== 'none' && (
                                    <div className="input-group">
                                        <label>Klucz API</label>
                                        <input type="password" value={config.apiKey} placeholder="sk-…"
                                            onChange={e => setConfig({ ...config, apiKey: e.target.value })} />
                                    </div>
                                )}
                            </section>

                            <section className="upload-panel">
                                <div className="panel-header"><Upload size={19} /><h2>Plik MBZ</h2></div>
                                <Dropzone id="fileInput" file={file} onChange={handleFileChange} />
                                <div className="action-area">
                                    <AnimatePresence mode="wait">
                                        {status === 'idle' && (
                                            <motion.button key="start" whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                                                onClick={startTranslation} disabled={!file} className="btn-primary">
                                                Rozpocznij tłumaczenie
                                            </motion.button>
                                        )}
                                        {(status === 'uploading' || status === 'processing') && (
                                            <motion.div key="loading" className="status-loader">
                                                <Loader2 className="spin" size={26} />
                                                <span>{status === 'uploading' ? 'Wysyłanie…' : 'Przetwarzanie XML…'}</span>
                                            </motion.div>
                                        )}
                                        {status === 'completed' && (
                                            <motion.div key="done" initial={{ scale: 0.85, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                                                className="completed-actions">
                                                <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                                                    onClick={() => window.open(`/api/download/${taskId}`, '_blank')}
                                                    className="btn-success">
                                                    <Download size={19} /> Pobierz MBZ
                                                </motion.button>
                                                <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                                                    onClick={resetTranslate} className="btn-secondary">
                                                    <Upload size={17} /> Przetwórz kolejny kurs
                                                </motion.button>
                                            </motion.div>
                                        )}
                                        {status === 'error' && (
                                            <motion.div key="err" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="error-actions">
                                                <div className="status-error"><AlertCircle size={19} /><span>Przetwarzanie nie powiodło się</span></div>
                                                <motion.button whileHover={{ scale: 1.04 }} onClick={resetTranslate} className="btn-secondary">
                                                    <Upload size={17} /> Spróbuj ponownie
                                                </motion.button>
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </div>
                            </section>
                        </motion.div>
                    )}

                    {/* ══ FLASHCARDS TAB ══ */}
                    {activeTab === 'flashcards' && (
                        <motion.div key="flashcards" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.25 }} className="flashcards-layout">

                            <section className="glass-panel flash-upload-panel">
                                <div className="panel-header"><Layers size={20} /><h2>Generuj Fiszki z MBZ</h2></div>

                                {/* AI info banner */}
                                <div className="ai-banner">
                                    <Sparkles size={16} />
                                    <span>
                                        Z kluczem <strong>OpenAI</strong> — GPT-4o automatycznie streszcza cały kurs
                                        i tworzy inteligentne fiszki edukacyjne. Bez klucza — wyciągane są
                                        tytuły i opisy z pliku XML.
                                    </span>
                                </div>

                                <Dropzone id="flashFileInput" file={flashFile} onChange={handleFlashFileChange} />

                                {/* API config */}
                                <ApiConfig
                                    apiType={flashConfig.apiType}
                                    apiKey={flashConfig.apiKey}
                                    onChange={(k, v) => setFlashConfig(prev => ({ ...prev, [k]: v }))}
                                />

                                <div className="action-area">
                                    <AnimatePresence mode="wait">
                                        {flashStatus === 'idle' && (
                                            <motion.button key="gen" whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                                                onClick={generateFlashcards} disabled={!flashFile} className="btn-primary">
                                                <Sparkles size={17} />
                                                {flashConfig.apiType === 'openai' ? 'Generuj fiszki AI' : 'Generuj fiszki'}
                                            </motion.button>
                                        )}
                                        {flashStatus === 'loading' && (
                                            <motion.div key="loading" className="status-loader">
                                                <Loader2 className="spin" size={26} />
                                                <span>
                                                    {flashConfig.apiType === 'openai'
                                                        ? 'Analizowanie kursu przez AI (może chwilę potrwać)…'
                                                        : 'Analizowanie kursu…'}
                                                </span>
                                            </motion.div>
                                        )}
                                        {flashStatus === 'error' && (
                                            <motion.div key="err" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="error-actions">
                                                <div className="status-error"><AlertCircle size={19} /><span>Nie udało się wygenerować fiszek</span></div>
                                                <motion.button whileHover={{ scale: 1.04 }} onClick={resetFlash} className="btn-secondary">
                                                    <Upload size={17} /> Spróbuj ponownie
                                                </motion.button>
                                            </motion.div>
                                        )}
                                        {flashStatus === 'done' && flashcards.length === 0 && (
                                            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flash-empty">
                                                <Info size={22} />
                                                <span>Kurs nie zawarł treści nadających się do fiszek.<br />Sprawdź czy plik MBZ zawiera aktywności, quizy lub słowniki.</span>
                                                <motion.button whileHover={{ scale: 1.04 }} onClick={resetFlash} className="btn-secondary">
                                                    <Upload size={17} /> Spróbuj inny plik
                                                </motion.button>
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </div>
                            </section>

                            {/* Results */}
                            {flashStatus === 'done' && flashcards.length > 0 && (
                                <motion.section initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.15 }} className="glass-panel flash-results">

                                    <div className="flash-results-header">
                                        <div>
                                            <h3>Wygenerowane fiszki</h3>
                                            <span className="flash-count">
                                                {flashcards.length} fiszek
                                                {flashConfig.apiType === 'openai' && <span className="ai-badge"><Sparkles size={10} /> AI</span>}
                                            </span>
                                        </div>
                                        <div className="flash-header-actions">
                                            <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                                                onClick={downloadCsv} className="btn-success btn-sm">
                                                <Download size={14} /> CSV (Anki)
                                            </motion.button>
                                            <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                                                onClick={resetFlash} className="btn-secondary btn-sm">
                                                <Upload size={14} /> Nowy plik
                                            </motion.button>
                                        </div>
                                    </div>

                                    <div className="flash-cards-grid">
                                        {pagedCards.map((card, idx) => (
                                            <motion.div key={idx} className="flash-card"
                                                initial={{ opacity: 0, y: 12 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                transition={{ delay: idx * 0.04 }}>
                                                <div className="flash-card-front">
                                                    <span className={`source-badge ${badgeClass(card.source)}`}>{card.source}</span>
                                                    <p>{card.front}</p>
                                                </div>
                                                <div className="flash-card-divider" />
                                                <div className="flash-card-back">
                                                    <p>{card.back}</p>
                                                </div>
                                            </motion.div>
                                        ))}
                                    </div>

                                    {totalPages > 1 && (
                                        <div className="flash-pagination">
                                            <button id="page-prev" className="page-btn"
                                                onClick={() => setFlashPage(p => Math.max(0, p - 1))}
                                                disabled={flashPage === 0}>
                                                <ChevronLeft size={16} />
                                            </button>
                                            <span>{flashPage + 1} / {totalPages}</span>
                                            <button id="page-next" className="page-btn"
                                                onClick={() => setFlashPage(p => Math.min(totalPages - 1, p + 1))}
                                                disabled={flashPage === totalPages - 1}>
                                                <ChevronRight size={16} />
                                            </button>
                                        </div>
                                    )}
                                </motion.section>
                            )}
                        </motion.div>
                    )}
                </AnimatePresence>
            </main>
        </div>
    );
};

export default App;
