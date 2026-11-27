import { useMemo, useState } from 'react';
import { ShieldCheck, ChevronLeft, ChevronRight, User, X } from 'lucide-react';

// ---------------------------------------------------------------------------
// FIDELITY LIFE — white corporate navigation rail.
//
// Structural flex column with no absolute positioning:
//   Header (brand + collapse)  — shrink-0
//   Nav (role groups)          — flex-1, independent scroll
//   Account footer             — shrink-0
//
// Corporate treatment: white surface, charcoal labels, Fidelity-red icons,
// light-red active state with a red edge indicator. Props, persistence and
// the shared width constants are unchanged, so RBAC and layout behaviour are
// identical to the previous implementation.
// ---------------------------------------------------------------------------

export const SIDEBAR_WIDTH_EXPANDED = 264;
export const SIDEBAR_WIDTH_COLLAPSED = 56;

const groupSections = (items) => {
  const groups = [];
  for (const item of items) {
    const title = item.section || 'Main';
    let g = groups.find((x) => x.title === title);
    if (!g) {
      g = { title, items: [] };
      groups.push(g);
    }
    g.items.push(item);
  }
  return groups;
};

export default function Sidebar({ user, sidebar, activeTab, onTab, expanded, onToggle, mobileOpen, onMobileClose }) {
  const groups = useMemo(() => groupSections(sidebar || []), [sidebar]);
  const [closedGroups, setClosedGroups] = useState(() => {
    try {
      return JSON.parse(window.localStorage.getItem('nexa_sidebar_groups_closed') || '{}');
    } catch {
      return {};
    }
  });

  const toggleGroup = (title) => {
    const next = { ...closedGroups, [title]: !closedGroups[title] };
    setClosedGroups(next);
    try { window.localStorage.setItem('nexa_sidebar_groups_closed', JSON.stringify(next)); } catch { /* ignore */ }
  };

  const width = expanded ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED;
  const isGroupClosed = (title) => (expanded ? !!closedGroups[title] : false);

  const accountInitials = (user?.full_name || user?.username || 'U').slice(0, 2).toUpperCase();
  const displayName = user?.full_name || user?.username || 'User';
  const displayRole = (user?.role || '').replace(/_/g, ' ');

  const navItems = (
    <div className="space-y-4">
      {groups.map((g) => {
        const closed = isGroupClosed(g.title);
        return (
          <div key={g.title}>
            <button
              type="button"
              onClick={() => toggleGroup(g.title)}
              className={`w-full flex items-center justify-between text-[10px] font-extrabold uppercase tracking-wider px-3 py-2 text-[#222222] hover:text-[#8B0000] transition ${expanded ? 'block' : 'hidden'}`}
            >
              <span className="truncate">{g.title}</span>
              <ChevronRight className={`w-3.5 h-3.5 transition-transform ${closed ? '-rotate-90' : ''}`} />
            </button>
            <div className={`transition-all duration-200 ease-in-out overflow-hidden ${closed ? 'max-h-0 opacity-0' : ''}`}>
              <div className="space-y-1">
                {g.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      title={item.label}
                      aria-label={item.label}
                      aria-current={isActive ? 'page' : undefined}
                      onClick={() => onTab(item.id)}
                      className={`relative w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-semibold transition-colors ${
                        isActive
                          ? 'bg-[#FCEBED] text-[#222222]'
                          : 'text-[#222222] hover:bg-[#FCEBED]'
                      } ${expanded ? '' : 'justify-center'}`}
                    >
                      {isActive && (
                        <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-full bg-[#C8102E]" aria-hidden="true" />
                      )}
                      <Icon className="w-[19px] h-[19px] text-[#C8102E] shrink-0" />
                      {expanded && <span className="truncate">{item.label}</span>}
                      {!expanded && isActive && (
                        <span className="absolute -right-0.5 -top-0.5 w-2 h-2 rounded-full bg-[#C8102E] ring-2 ring-white" aria-hidden="true" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <>
      {/* Mobile hamburger — reserved space is provided by the header's pl-16. */}
      <button
        type="button"
        aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
        aria-expanded={mobileOpen}
        onClick={() => onMobileClose?.(!mobileOpen)}
        className="md:hidden fixed top-4 left-4 z-[60] p-2.5 rounded-md bg-white text-[#C8102E] border border-[#EEEEEE] shadow-sm"
      >
        {mobileOpen ? <X size={20} /> : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        )}
      </button>

      {/* Desktop: fixed collapsible rail. */}
      <aside
        aria-label="Fidelity Life platform navigation"
        className="fidelity-sidebar hidden md:flex flex-col fixed left-0 top-0 bottom-0 z-[55] bg-white border-r border-[#EEEEEE] transition-all duration-200 ease-in-out"
        style={{ width }}
      >
        <div className={`relative flex items-center justify-between gap-3 shrink-0 border-b border-[#EEEEEE] ${expanded ? 'px-4 py-5' : 'px-2 py-4 justify-center'}`}>
          {expanded ? (
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-9 h-9 rounded-md bg-[#C8102E] flex items-center justify-center text-white shrink-0">
                <ShieldCheck size={18} />
              </div>
              <div className="min-w-0">
                <span className="block font-extrabold text-sm tracking-wide text-[#222222] leading-none">FIDELITY LIFE</span>
                <span className="block text-[10px] text-[#8B0000] font-semibold tracking-wider uppercase leading-none mt-0.5 truncate">NEXA Fraud Intelligence</span>
              </div>
            </div>
          ) : (
            <div className="w-9 h-9 rounded-md bg-[#C8102E] flex items-center justify-center text-white shrink-0">
              <ShieldCheck size={18} />
            </div>
          )}
          {expanded ? (
            <button
              type="button"
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
              onClick={onToggle}
              className="p-1.5 rounded-md text-[#222222] hover:bg-[#FCEBED] hover:text-[#C8102E] transition shrink-0"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
          ) : (
            <button
              type="button"
              aria-label="Expand sidebar"
              title="Expand sidebar"
              onClick={onToggle}
              className="absolute right-2 p-1.5 rounded-md text-[#222222] hover:bg-[#FCEBED] hover:text-[#C8102E] transition"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          )}
        </div>

        <nav className="flex-1 min-h-0 overflow-y-auto px-3 py-3">
          {navItems}
        </nav>

        <div className={`shrink-0 mt-3 border-t border-[#EEEEEE] px-3 py-3 flex ${expanded ? 'items-center gap-2.5' : 'flex-col items-center gap-1'}`}>
          {expanded ? (
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <div className="w-8 h-8 rounded-md bg-[#FCEBED] border border-[#EEEEEE] flex items-center justify-center font-bold text-xs text-[#8B0000] shrink-0">
                {accountInitials}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-[#222222] truncate">{displayName}</p>
                <p className="text-[10px] text-[#8B0000] font-semibold truncate">{displayRole}</p>
              </div>
            </div>
          ) : (
            <button
              type="button"
              title={`Account — ${displayRole}`}
              aria-label="Account"
              className="p-2 rounded-md text-[#C8102E] hover:bg-[#FCEBED] transition"
            >
              <User className="w-5 h-5" />
            </button>
          )}
        </div>
      </aside>

      {/* Mobile overlay sheet — same navigation, no overlapping content. */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-[55]">
          <div className="absolute inset-0 bg-black/20" onClick={() => onMobileClose?.(false)} />
          <aside className="absolute left-0 top-0 bottom-0 flex flex-col bg-white w-72 max-w-[85vw] border-r border-[#EEEEEE] shadow-xl">
            <div className="flex items-center justify-between gap-2 px-3 py-4 border-b border-[#EEEEEE] shrink-0">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-9 h-9 rounded-md bg-[#C8102E] flex items-center justify-center text-white shrink-0">
                  <ShieldCheck size={18} />
                </div>
                <div className="min-w-0">
                  <span className="block font-extrabold text-sm text-[#222222]">FIDELITY LIFE</span>
                  <span className="block text-[10px] text-[#8B0000] font-semibold uppercase truncate">NEXA Fraud Intelligence</span>
                </div>
              </div>
              <button
                type="button"
                aria-label="Close navigation menu"
                onClick={() => onMobileClose?.(false)}
                className="p-1.5 rounded-md text-[#222222] hover:bg-[#FCEBED] hover:text-[#8B0000] transition shrink-0"
              >
                <X size={18} />
              </button>
            </div>

            <nav className="flex-1 min-h-0 overflow-y-auto px-3 py-3">
              <div className="space-y-4">
                {groups.map((g) => (
                  <div key={g.title}>
                    <p className="text-[10px] font-extrabold uppercase tracking-wider text-[#222222] pb-1.5">{g.title}</p>
                    <div className="space-y-1">
                      {g.items.map((item) => {
                        const Icon = item.icon;
                        const isActive = activeTab === item.id;
                        return (
                          <button
                            key={item.id}
                            type="button"
                            title={item.label}
                            onClick={() => { onMobileClose?.(false); onTab(item.id); }}
                            className={`relative w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-semibold transition-colors ${
                              isActive ? 'bg-[#FCEBED] text-[#222222]' : 'text-[#222222] hover:bg-[#FCEBED]'
                            }`}
                          >
                            {isActive && <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-full bg-[#C8102E]" aria-hidden="true" />}
                            <Icon className="w-5 h-5 text-[#C8102E] shrink-0" />
                            <span className="truncate">{item.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </nav>

            <div className="shrink-0 border-t border-[#EEEEEE] px-3 py-3 flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-md bg-[#FCEBED] border border-[#EEEEEE] flex items-center justify-center font-bold text-xs text-[#8B0000] shrink-0">
                {accountInitials}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-[#222222] truncate">{displayName}</p>
                <p className="text-[10px] text-[#8B0000] truncate">{displayRole}</p>
              </div>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
