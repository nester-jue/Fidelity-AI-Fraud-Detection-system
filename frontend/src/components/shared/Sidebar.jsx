import { useMemo, useState } from 'react';
import { ShieldCheck, ChevronLeft, ChevronRight, User } from 'lucide-react';

// ---------------------------------------------------------------------------
// NEXA — Professional collapsible, fixed-position LEFT sidebar (not a drawer).
//
// Layout model — a fixed, fully structural flex column; no absolute overlaps:
//
//  ┌────────────────────────────────────┐
//  │  Header  (brand + toggle)          │  shrink-0, pinned at the top
//  ├────────────────────────────────────┤
//  │  Nav                               │  flex-1, independent vertical
//  │  (role nav + section groups)       │  scrolling (overflow-y-auto)
//  ├────────────────────────────────────┤
//  │  Account footer                    │  shrink-0, sits at the bottom and
//  │  (user + role)                     │  never overlaps the navigation
//  └────────────────────────────────────┘
//
// Behaviour:
//  - Expanded: logo + platform name, icons + labels for every item, sections.
//  - Collapsed: narrow icon rail; labels hidden; tooltips on hover (title).
//  - Never slides; always fixed in place; content adjusts via margin-left.
//  - Sidebar preference is persisted (localStorage) and survives navigation.
//  - Group sections collapse individually in expanded mode; every group is
//    always open in collapsed mode so no icon becomes unreachable.
//  - Mobile: hamburger triggers an accessible slide-over sheet of the same
//    nav, with its own scrolling region and a bottom account footer.
// ---------------------------------------------------------------------------

// Width constants — shared with App.jsx so the main-content offset can never
// drift away from the real rail width.
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

  const toggleGroup = (id) => {
    const next = { ...closedGroups, [id]: !closedGroups[id] };
    setClosedGroups(next);
    try { window.localStorage.setItem('nexa_sidebar_groups_closed', JSON.stringify(next)); } catch { /* ignore */ }
  };

  const width = expanded ? SIDEBAR_WIDTH_EXPANDED : SIDEBAR_WIDTH_COLLAPSED;

  // In collapsed mode the icon rail is always open — labels are hidden there,
  // so a closed group would make its icons permanently unreachable.
  const isGroupClosed = (title) => (expanded ? !!closedGroups[title] : false);

  const navItems = (
    <div className="space-y-4">
      {groups.map((g) => {
        const closed = isGroupClosed(g.title);
        return (
          <div key={g.title}>
            <button
              type="button"
              onClick={() => toggleGroup(g.title)}
              className={`w-full flex items-center justify-between text-[10px] font-extrabold uppercase tracking-wider px-3 py-2 text-slate-400 hover:text-slate-200 transition ${expanded ? 'block' : 'hidden'}`}
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
                      onClick={() => { onTab(item.id); }}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-bold transition-colors ${
                        isActive
                          ? 'bg-white/10 text-amber-300'
                          : 'text-slate-300 hover:bg-white/5 hover:text-white'
                      } ${expanded ? '' : 'justify-center'}`}
                    >
                      <span className={`relative ${isActive ? 'text-amber-300' : ''}`}>
                        <Icon className={`w-[19px] h-[19px] ${isActive ? 'text-amber-300' : ''}`} />
                        {expanded === false && isActive && <span className="absolute -right-1 -top-1 w-2 h-2 rounded-full bg-amber-300" aria-hidden="true" />}
                      </span>
                      {expanded && <span className="truncate">{item.label}</span>}
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

  // Account footer — shared by the desktop rail and the mobile sheet. Statically
  // positioned so it can never cover or overlap navigation items above it.
  const AccountFooter = () => (
    <div className={`shrink-0 mt-3 border-t border-slate-700/60 px-3 py-3 flex ${expanded ? 'items-center gap-2.5' : 'flex-col items-center gap-1'}`}>
      {expanded ? (
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <div className="w-8 h-8 rounded-lg bg-slate-700/70 flex items-center justify-center font-bold text-xs text-amber-300">
            {(user?.full_name || user?.username || 'U').slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="text-xs font-bold text-white truncate">{user?.full_name || user?.username}</p>
            <p className="text-[10px] text-amber-300/80 truncate">{(user?.role || '').replace(/_/g, ' ')}</p>
          </div>
        </div>
      ) : (
        <button type="button" title={`Account — ${(user?.role || '').replace(/_/g, ' ')}`} aria-label="Account" className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition">
          <User className="w-5 h-5" />
        </button>
      )}
    </div>
  );

  // Brand header — pinned at the top of the sidebar (first flex child).
  const Header = () => (
    <div className={`relative flex items-center justify-between gap-3 px-3 shrink-0 border-b border-slate-700/60 ${expanded ? 'px-4 py-5' : 'py-4 justify-center'}`}>
      {expanded ? (
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-400 to-amber-500 flex items-center justify-center shadow text-slate-900 font-black text-lg">
            <ShieldCheck size={18} />
          </div>
          <div className="min-w-0">
            <span className="block font-extrabold text-sm tracking-wide text-white leading-none">NEXA</span>
            <span className="block text-[10px] text-amber-300 font-semibold tracking-wider uppercase leading-none mt-0.5">Enterprise Fraud Intelligence</span>
          </div>
        </div>
      ) : (
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-400 to-amber-500 flex items-center justify-center text-slate-900 font-black text-lg shadow">
          <ShieldCheck size={18} />
        </div>
      )}
      {expanded && (
        <button
          type="button"
          aria-label="Collapse sidebar"
          title="Collapse sidebar"
          onClick={onToggle}
          className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-white/5 transition"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
      )}
      {!expanded && (
        <button
          type="button"
          aria-label="Expand sidebar"
          title="Expand sidebar"
          onClick={onToggle}
          className="absolute right-3 p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-white/5 transition"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      )}
    </div>
  );

  return (
    <>
      {/* Mobile hamburger (accessible nav toggle; desktop uses the fixed rail) */}
      <button
        type="button"
        aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
        aria-expanded={mobileOpen}
        onClick={() => onMobileClose?.(!mobileOpen)}
        className="md:hidden fixed top-4 left-4 z-[60] p-2.5 rounded-lg bg-[#0F2744] text-white border border-slate-700 shadow-lg"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      {/* Desktop: fixed collapsible rail — flex column, nothing absolute */}
      <aside
        aria-label="NEXA platform navigation"
        className="hidden md:flex flex-col fixed left-0 top-0 bottom-0 z-[55] bg-[#0F2744] border-r border-slate-700/80 transition-all duration-200 ease-in-out"
        style={{ width }}
      >
        <Header />

        {/* Nav — independent vertical scrolling */}
        <nav className="flex-1 min-h-0 overflow-y-auto px-3 py-3">
          {navItems}
        </nav>

        {/* Account footer — static, pinned at the bottom, above the border */}
        <AccountFooter />
      </aside>

      {/* Mobile overlay sheet (hamburger → same nav, accessible, scrollable) */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-[55]">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => onMobileClose?.(false)} />
          <aside className="absolute left-0 top-0 bottom-0 flex flex-col bg-[#0F2744] w-72 max-w-[85vw] border-r border-slate-700/80 shadow-2xl">
            {/* Brand header */}
            <div className="flex items-center gap-2.5 px-3 py-4 border-b border-slate-700/60 shrink-0">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-400 to-amber-500 flex items-center justify-center text-slate-900 font-black text-lg">
                <ShieldCheck size={18} />
              </div>
              <div>
                <span className="block font-extrabold text-sm text-white">NEXA</span>
                <span className="block text-[10px] text-amber-300 font-semibold uppercase">Fraud Intelligence</span>
              </div>
            </div>

            {/* Nav — independent vertical scrolling */}
            <nav className="flex-1 min-h-0 overflow-y-auto px-3 py-3">
              <div className="space-y-4">
                {groups.map((g) => (
                  <div key={g.title}>
                    <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 pb-1.5">{g.title}</p>
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
                            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-bold transition-colors ${isActive ? 'bg-white/10 text-amber-300' : 'text-slate-300 hover:bg-white/5'}`}
                          >
                            <Icon className={`w-5 h-5 ${isActive ? 'text-amber-300' : ''}`} />
                            <span className="truncate">{item.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </nav>

            {/* Account footer — static, at the bottom of the sheet */}
            <div className="shrink-0 border-t border-slate-700/60 px-3 py-3 flex flex-col items-center gap-1">
              <button type="button" title={`Account — ${(user?.role || '').replace(/_/g, ' ')}`} aria-label="Account" className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition">
                <User className="w-5 h-5" />
              </button>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
