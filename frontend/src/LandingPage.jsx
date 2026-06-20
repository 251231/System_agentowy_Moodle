import React from 'react';
import './LandingPage.css';

export default function LandingPage({ onLoginClick }) {
    const scrollTo = (id) => {
        const el = document.getElementById(id);
        if(el) el.scrollIntoView({ behavior: 'smooth' });
    };

    return (
        <div className="landing-page-root">
            <div className="bg-orbs">
                <div className="orb"></div>
                <div className="orb"></div>
                <div className="orb"></div>
            </div>

            <div className="content">
                <nav>
                    <div className="nav-container">
                        <div className="logo">
                            <div className="logo-icon">M</div>
                            <div className="logo-text">Moodle AI</div>
                        </div>
                        <button className="login-btn" onClick={onLoginClick}>Zaloguj się</button>
                    </div>
                </nav>

                <section className="hero">
                    <div className="hero-container">
                        <div className="hero-content">
                            <div className="badge">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{"verticalAlign":"text-bottom"}}>
                                    <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path>
                                    <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path>
                                    <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"></path>
                                    <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"></path>
                                </svg> Zaawansowana Automatyzacja AI
                            </div>
                            <h1>Inteligentna Transformacja<br />Twoich Kursów <span className="gradient">Moodle</span></h1>
                            <p className="hero-description">
                                Oszczędzaj dziesiątki godzin żmudnej pracy. Nasz System Agentowy automatycznie generuje interaktywne fiszki H5P, tłumaczy moduły na obce języki i weryfikuje poprawność każdego linku, operując bezpośrednio na plikach .mbz bez ryzykownej integracji API.
                            </p>
                            <div className="button-group">
                                <button className="btn btn-primary" onClick={onLoginClick}>Uruchom Agenty</button>
                            </div>
                            <div className="stats">
                                <div className="stat">
                                    <div className="stat-value">3</div>
                                    <div className="stat-label">Eksperckie Agenty</div>
                                </div>
                                <div className="stat">
                                    <div className="stat-value">10x</div>
                                    <div className="stat-label">Szybsza Praca</div>
                                </div>
                                <div className="stat">
                                    <div className="stat-value">100%</div>
                                    <div className="stat-label">Prywatności Danych</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <section className="agents" id="agents">
                    <div className="section-header">
                        <h2>Trzej Inteligentni Agenci</h2>
                        <p>Każdy agent specjalizuje się w innym aspekcie optymalizacji Twoich materiałów dydaktycznych</p>
                    </div>
                    <div className="agents-container">
                        <div className="agent-card">
                            <div className="agent-card-content">
                                <div className="agent-icon">
                                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                                        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                                    </svg>
                                </div>
                                <h3 className="agent-title">Link Checker</h3>
                                <p className="agent-description">
                                    Automatycznie skanuje całą strukturę kursu i weryfikuje każdy link. Sprawdza przekierowania, kody HTTP i zabezpiecza materiały przed martwymi odnośnikami.
                                </p>
                                <div className="agent-features">
                                    <div className="feature-item">
                                        <span className="feature-icon">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="20 6 9 17 4 12"></polyline>
                                            </svg>
                                        </span>
                                        <span>Pełne skanowanie struktury</span>
                                    </div>
                                    <div className="feature-item">
                                        <span className="feature-icon">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="20 6 9 17 4 12"></polyline>
                                            </svg>
                                        </span>
                                        <span>Weryfikacja statusów HTTP</span>
                                    </div>
                                    <div className="feature-item">
                                        <span className="feature-icon">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="20 6 9 17 4 12"></polyline>
                                            </svg>
                                        </span>
                                        <span>Raport szczegółowy</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="agent-card">
                            <div className="agent-card-content">
                                <div className="agent-icon">
                                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"></path>
                                    </svg>
                                </div>
                                <h3 className="agent-title">H5P Generator</h3>
                                <p className="agent-description">
                                    Czyta surowe materiały i automatycznie buduje interaktywne moduły H5P. Tworzy quizy, fiszki i ćwiczenia z uzupełnianiem luk.
                                </p>
                                <div className="agent-features">
                                    <div className="feature-item">
                                        <span className="feature-icon">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="20 6 9 17 4 12"></polyline>
                                            </svg>
                                        </span>
                                        <span>Automatyczne quizy</span>
                                    </div>
                                    <div className="feature-item">
                                        <span className="feature-icon">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="20 6 9 17 4 12"></polyline>
                                            </svg>
                                        </span>
                                        <span>Interaktywne fiszki</span>
                                    </div>
                                    <div className="feature-item">
                                        <span className="feature-icon">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="20 6 9 17 4 12"></polyline>
                                            </svg>
                                        </span>
                                        <span>Ćwiczenia edukacyjne</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="agent-card">
                            <div className="agent-card-content">
                                <div className="agent-icon">
                                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <circle cx="12" cy="12" r="10"></circle>
                                        <line x1="2" y1="12" x2="22" y2="12"></line>
                                        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                                    </svg>
                                </div>
                                <h3 className="agent-title">Translator</h3>
                                <p className="agent-description">
                                    Obsługuje umiędzynarodowienie edukacji. Płynnie tłumaczy wybrane sekcje i moduły kursu na inne języki.
                                </p>
                                <div className="agent-features">
                                    <div className="feature-item">
                                        <span className="feature-icon">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="20 6 9 17 4 12"></polyline>
                                            </svg>
                                        </span>
                                        <span>Wielojęzyczne wsparcie</span>
                                    </div>
                                    <div className="feature-item">
                                        <span className="feature-icon">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="20 6 9 17 4 12"></polyline>
                                            </svg>
                                        </span>
                                        <span>Automatyczne tłumaczenie</span>
                                    </div>
                                    <div className="feature-item">
                                        <span className="feature-icon">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <polyline points="20 6 9 17 4 12"></polyline>
                                            </svg>
                                        </span>
                                        <span>Integracja OpenAI/DeepL</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <section className="how-it-works">
                    <div className="section-header">
                        <h2>Jak to Działa</h2>
                        <p>Prosty, trzystopniowy proces do doskonałości</p>
                    </div>
                    <div className="steps-container">
                        <div className="step">
                            <div className="step-number">1</div>
                            <div className="step-card">
                                <h3>Załaduj Plik</h3>
                                <p>Prześlij plik kopii zapasowej Moodle (.mbz) do naszego systemu. Bez API, bez komplikacji.</p>
                            </div>
                        </div>
                        <div className="step">
                            <div className="step-number">2</div>
                            <div className="step-card">
                                <h3>Agenci Pracują</h3>
                                <p>Trzy wyspecjalizowane agenty analizują i transformują Twoje materiały równocześnie.</p>
                            </div>
                        </div>
                        <div className="step">
                            <div className="step-number">3</div>
                            <div className="step-card">
                                <h3>Pobierz Rezultat</h3>
                                <p>Pobierz przetworzony plik gotowy do zaimportowania z powrotem do Moodle.</p>
                            </div>
                        </div>
                    </div>
                </section>

                <footer>
                    <div className="footer-container">
                        <div className="footer-grid">
                            <div className="footer-column">
                                <div className="logo">
                                    <div className="logo-icon">M</div>
                                    <div className="logo-text">Moodle AI</div>
                                </div>
                                <p style={{"color":"var(--text-muted)","fontSize":"0.875rem","marginTop":"0.5rem"}}>System Agentowy dla Moodle</p>
                            </div>
                            <div className="footer-column">
                                <h4>Informacje</h4>
                                <ul>
                                    <li><a href="#" onClick={(e) => { e.preventDefault(); scrollTo(''); }}>O nas</a></li>
                                </ul>
                            </div>
                            <div className="footer-column">
                                <h4>Kontakt</h4>
                                <ul>
                                    <li><a href="mailto:moodle.ai.agent@gmail.com">moodle.ai.agent@gmail.com</a></li>
                                </ul>
                            </div>
                        </div>
                        <div className="footer-bottom">
                            <p>&copy; 2026 Moodle AI. Wszystkie prawa zastrzeżone.</p>
                            <div className="footer-links">
                                <a href="#" onClick={(e) => { e.preventDefault(); scrollTo(''); }}>Polityka Prywatności</a>
                                <a href="#" onClick={(e) => { e.preventDefault(); scrollTo(''); }}>Warunki Użytkowania</a>
                            </div>
                        </div>
                    </div>
                </footer>
            </div>
        </div>
    );
}