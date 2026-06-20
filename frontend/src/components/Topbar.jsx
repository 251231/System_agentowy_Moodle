import React from 'react';
import { IconDown } from './Icons';

export default function Topbar({ user, showDropdown, setShowDropdown, handleLogout, dropdownRef }) {
  return (
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
  );
}
