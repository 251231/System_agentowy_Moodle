import React from 'react';
import { IconUpload, IconGlobe, IconCards, IconLink, IconText, IconPlay } from './Icons';

export default function Sidebar({
  file,
  fileInputRef,
  handleDrop,
  handleFileChange,
  config,
  setConfig,
  toggleTargetLang,
  toggleH5pType,
  toggleH5pFocus,
  collapsedSections,
  toggleSection,
  isSubmitting,
  handleSubmit,
  canRun,
  runHint,
  LANGUAGES,
  TARGET_LANG_TAGS
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <div
          className="sidebar-section-header active"
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
  );
}
