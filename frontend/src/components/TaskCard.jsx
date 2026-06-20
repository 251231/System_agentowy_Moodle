import React from 'react';
import { IconX, IconFile, IconDl, IconDown } from './Icons';
import LinksReport from './LinksReport';

export default function TaskCard({
  task,
  isExpanded,
  toggleExpand,
  handleCancel,
  handleDownload,
  handleDownloadTexts,
  handleDownloadH5p,
  handleDownloadLinks,
  fetchLinksReport,
  expandedLinksReport,
  linksReports,
  selectedLinks,
  toggleSelectLink,
  toggleSelectAll,
  handleReplaceSelectedLinks,
  handleApproveLinks
}) {
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
    <div className={`task-card status-${task.status}${isExpanded ? ' expanded' : ''}`}>
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

      {isExpanded && expandedLinksReport === task.id && linksReports[task.id] && (
        <LinksReport
          taskId={task.id}
          report={linksReports[task.id]}
          selectedLinks={selectedLinks}
          toggleSelectLink={toggleSelectLink}
          toggleSelectAll={toggleSelectAll}
          handleReplaceSelectedLinks={handleReplaceSelectedLinks}
        />
      )}
    </div>
  );
}
