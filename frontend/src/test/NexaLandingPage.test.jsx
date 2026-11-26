import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import NexaLandingPage from '../components/pages/NexaLandingPage.jsx';

describe('NexaLandingPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders local SVG assets and the Secure Login CTA without making network calls', () => {
    const fetchMock = vi.fn(() => {
      throw new Error('The landing page must not call the network');
    });
    vi.stubGlobal('fetch', fetchMock);
    const xhrOpen = vi.spyOn(XMLHttpRequest.prototype, 'open');
    const onLogin = vi.fn();
    const onRequestDemo = vi.fn();

    render(<NexaLandingPage onLogin={onLogin} onRequestDemo={onRequestDemo} />);

    expect(screen.getByAltText('NEXA shield logo')).toHaveAttribute('src', '/images/branding/nexa-logo.svg');
    expect(screen.getByAltText(/NEXA analytics environment/)).toHaveAttribute('src', '/images/landing/hero-analytics.svg');
    expect(document.querySelector('img[src="/images/features/ai-fraud.svg"]')).toBeInTheDocument();
    expect(document.querySelector('img[src="/images/features/enterprise-security.svg"]')).toBeInTheDocument();

    const loginButtons = screen.getAllByRole('button', { name: /Secure Login/ });
    expect(loginButtons.length).toBeGreaterThan(0);
    fireEvent.click(loginButtons[0]);
    expect(onLogin).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: /Request a demonstration/ }));
    expect(onRequestDemo).toHaveBeenCalledTimes(1);

    expect(fetchMock).not.toHaveBeenCalled();
    expect(xhrOpen).not.toHaveBeenCalled();
  });

  it('keeps marketing claims descriptive and avoids live statistics', () => {
    render(<NexaLandingPage onLogin={vi.fn()} onRequestDemo={vi.fn()} />);

    expect(screen.getByText(/No production customer records are used/)).toBeInTheDocument();
    expect(screen.getByText(/No regulatory certification is claimed/)).toBeInTheDocument();
    expect(screen.getByText(/A risk score is a lead for a trained investigator/)).toBeInTheDocument();
    expect(screen.queryByText(/\b\d{2,3}\s?%\b/)).not.toBeInTheDocument();
  });
});
