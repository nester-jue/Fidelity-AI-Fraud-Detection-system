import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SecurityCentre from '../components/dashboards/SecurityCentre.jsx';
import { api } from '../api/apiClient.js';

vi.mock('../api/apiClient.js', () => ({
  api: {
    securityOverview: vi.fn(),
    securityEvents: vi.fn(),
  },
}));

const overviewPayload = {
  reporting_period: { from: '2026-10-28', to: '2026-11-26' },
  authentication: {
    successful_logins: 41,
    failed_logins: 7,
    recently_authenticated_users: 12,
    recent_users_note: 'Distinct users within one token lifetime.',
  },
  audit: { events_in_period: 88 },
  authentication_trend: [{ date: '2026-11-26', successful: 41, failed: 7 }],
  database: { dialect: 'sqlite', status: 'CONNECTED' },
  backup: { status: 'NOT_VERIFIED', detail: 'No backup verification record exists.' },
  controls: [{ name: 'MFA', status: 'ENFORCED', basis: 'Explicit configuration record' }],
};

const eventsPayload = [
  {
    id: 1,
    timestamp: '2026-11-26T10:00:00Z',
    user: 'alice',
    action: 'LOGIN_SUCCESS',
    target: 'web',
    classification: 'SECURITY',
  },
];

const okJson = (payload) => ({ ok: true, status: 200, json: async () => payload });

describe('SecurityCentre', () => {
  beforeEach(() => {
    api.securityOverview.mockResolvedValue(okJson(overviewPayload));
    api.securityEvents.mockResolvedValue(okJson(eventsPayload));
  });

  it('renders an honest NOT_VERIFIED backup status instead of an invented green status', async () => {
    render(<SecurityCentre user={{ name: 'Test User' }} />);

    expect(await screen.findByText('Backup verification')).toBeInTheDocument();
    const backupStatus = screen.getByText('NOT_VERIFIED');
    expect(backupStatus).toHaveClass('bg-amber-50');
    expect(backupStatus).not.toHaveClass('bg-emerald-50');
    expect(screen.getByText('No backup verification record exists.')).toBeInTheDocument();
    expect(screen.queryByText('VERIFIED')).not.toBeInTheDocument();
    expect(screen.getByText(/No green status is shown unless/)).toBeInTheDocument();

    expect(screen.getByText('LOGIN_SUCCESS')).toBeInTheDocument();
    expect(screen.getByText('41')).toBeInTheDocument();
    expect(api.securityOverview).toHaveBeenCalledWith(30);
    expect(api.securityEvents).toHaveBeenCalledWith({ days: 30, limit: 40 });
  });

  it('shows a clear error panel on a 403 overview response and recovers on retry', async () => {
    api.securityOverview
      .mockResolvedValueOnce({ ok: false, status: 403, json: async () => ({ detail: 'Forbidden for this role' }) })
      .mockResolvedValueOnce(okJson(overviewPayload));

    render(<SecurityCentre />);

    expect(await screen.findByText('Security information unavailable')).toBeInTheDocument();
    expect(screen.getByText('Forbidden for this role')).toBeInTheDocument();
    expect(screen.queryByText('Enterprise Security Centre')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('Enterprise Security Centre')).toBeInTheDocument();
    expect(screen.getByText('NOT_VERIFIED')).toBeInTheDocument();
    expect(api.securityOverview).toHaveBeenCalledTimes(2);
  });
});
