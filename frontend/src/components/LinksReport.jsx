import React from 'react';

export default function LinksReport({
  taskId,
  report,
  selectedLinks,
  toggleSelectLink,
  toggleSelectAll,
  handleReplaceSelectedLinks
}) {
  const brokenLinksIndices = report.links
    .map((l, i) => ({ l, i }))
    .filter(item => !item.l.is_active)
    .map(item => item.i);
    
  const currentSelected = selectedLinks[taskId] || [];

  return (
    <div className="links-report-container" onClick={e => e.stopPropagation()} style={{ display: 'block', margin: '12px 16px 16px' }}>
      <div className="links-report-header">
        <div className="links-report-title">Weryfikacja Linków Zewnętrznych</div>
        <div className="links-report-summary-stats">
          <span className="stat-badge total">Wszystkie: <strong>{report.summary.total}</strong></span>
          <span className="stat-badge active">Aktywne: <strong>{report.summary.active}</strong></span>
          <span className="stat-badge broken">Nieaktywne: <strong>{report.summary.broken}</strong></span>
        </div>
      </div>
      
      {report.links.length === 0 ? (
        <div className="links-report-empty">Nie wykryto żadnych linków zewnętrznych w tym kursie.</div>
      ) : (
        <>
          <div className="links-table-wrapper">
            <table className="links-report-table">
              <thead>
                <tr>
                  <th style={{ width: '40px', textAlign: 'center' }}>
                    <input 
                      type="checkbox" 
                      checked={brokenLinksIndices.length > 0 && brokenLinksIndices.every(idx => currentSelected.includes(idx))}
                      onChange={() => toggleSelectAll(taskId, brokenLinksIndices)}
                    />
                  </th>
                  <th>Adres URL</th>
                  <th>Lokalizacja w kursie</th>
                  <th>Status</th>
                  <th>Sugestia AI (Rozwiązanie)</th>
                </tr>
              </thead>
              <tbody>
                {report.links.map((link, idx) => (
                  <tr key={idx} className={link.is_active ? "row-active" : "row-broken"}>
                    <td style={{ textAlign: 'center' }}>
                      {!link.is_active && link.suggested_url && (
                        <input 
                          type="checkbox"
                          checked={currentSelected.includes(idx)}
                          onChange={() => toggleSelectLink(taskId, idx)}
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
          </div>
          {currentSelected.length > 0 && (
            <div className="replace-links-action-bar" style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
              <button
                className="btn-replace-links"
                onClick={() => handleReplaceSelectedLinks(taskId)}
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
                Zastąp zaznaczone linki ({currentSelected.length})
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
