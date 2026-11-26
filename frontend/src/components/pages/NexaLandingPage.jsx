import React, { useState } from 'react';
import { api } from '../../api/apiClient.js';
import {
  ShieldCheck, LockKeyhole, FileSearch, Brain, Network, GanttChart,
  BarChart3, Building2, ArrowRight, Mail, Phone, MapPin,
  CheckCircle2, ShieldAlert,
} from 'lucide-react';

// NEXA public landing page. Static product information only — no live
// statistics, no fabricated customer claims and no commercial licensing
// actions are performed here. All visual assets are local SVG files.
const LOGO = '/images/branding/nexa-logo.svg';
const HERO = '/images/landing/hero-analytics.svg';

const CAPABILITIES = [
  { icon: Brain, image: '/images/features/ai-fraud.svg', title: 'AI Fraud Detection', text: 'Explainable risk scoring across claim amounts, frequency, policy history, documents and beneficiary data. Every alert records the indicators and recommended human action.' },
  { icon: FileSearch, image: '/images/features/ocr-forensics.svg', title: 'Forensic Document Laboratory', text: 'OCR extraction, document classification, duplicate detection, consistency checks and cross-document comparison with a reviewable report.' },
  { icon: BarChart3, image: '/images/features/financial-risk.svg', title: 'Financial Intelligence', text: 'Separate views of suspected exposure, confirmed losses, prevented losses and recoveries — all calculated from claims and investigation records.' },
  { icon: GanttChart, image: '/images/features/investigation.svg', title: 'Investigation Management', text: 'Case references, assignment, deadlines, evidence, notes, escalation and a complete audit history from intake to outcome.' },
  { icon: Network, title: 'Relationship Network Analysis', text: 'A data-driven graph connecting claimants, beneficiaries, policies, contacts and documents to expose repeated links for investigator review.' },
  { icon: ShieldCheck, image: '/images/features/enterprise-security.svg', title: 'Enterprise Security', text: 'Role-based access, audited activity, protected document access, secure sessions and configurable authentication controls.' },
];

const EDITIONS = [
  {
    name: 'NEXA Essential', audience: 'Smaller insurance providers',
    features: ['Core claims intake and AI risk scoring', 'OCR document verification', 'Standard investigation workflow', 'Role-based access and audit logs'],
  },
  {
    name: 'NEXA Professional', audience: 'Medium-sized insurers and administrators', featured: true,
    features: ['Everything in Essential', 'Forensic laboratory and document comparison', 'Fraud network analysis and predictive alerts', 'Financial intelligence and executive reporting'],
  },
  {
    name: 'NEXA Enterprise', audience: 'Large insurers and multi-branch groups',
    features: ['Everything in Professional', 'Organisation-level separation and branding', 'Configurable integration adapters', 'Deployment and support by agreement'],
  },
];

const INDUSTRIES = [
  'Life assurance', 'Funeral assurance', 'Medical insurance', 'General insurance',
  'Pension and financial services', 'Brokers and administrators', 'Investigation departments',
];

function SectionHeading({ eyebrow, title, text }) {
  return (
    <div className="max-w-3xl">
      {eyebrow && <p className="text-[11px] font-black uppercase tracking-[0.22em] text-amber-700 mb-2">{eyebrow}</p>}
      <h2 className="nexa-suite-heading text-slate-900">{title}</h2>
      {text && <p className="mt-3 text-[15px] leading-relaxed text-slate-600">{text}</p>}
    </div>
  );
}

export default function NexaLandingPage({ onLogin, onRequestDemo }) {
  const [enquiry, setEnquiry] = useState({ organisation: '', email: '', interests: '' });
  const [enquiryStatus, setEnquiryStatus] = useState('');
  const [enquiryBusy, setEnquiryBusy] = useState(false);

  const submitEnquiry = async () => {
    if (!enquiry.organisation.trim() || !enquiry.email.trim()) {
      setEnquiryStatus('Please provide your organisation and work email address.');
      return;
    }
    setEnquiryBusy(true);
    setEnquiryStatus('');
    try {
      const res = await api.submitEnquiry(enquiry);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || 'The enquiry could not be recorded.');
      setEnquiryStatus(`Reference ${body.reference}. ${body.message}`);
      setEnquiry({ organisation: '', email: '', interests: '' });
    } catch (err) {
      setEnquiryStatus(err.message || 'The enquiry could not be recorded. Please try again.');
    } finally {
      setEnquiryBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-white font-sans text-slate-800">
      {/* Navigation */}
      <header className="sticky top-0 z-40 bg-[#0A192F] border-b border-slate-700 shadow-md">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <a href="#top" className="flex items-center gap-3 text-white no-underline" aria-label="NEXA home">
            <img src={LOGO} alt="NEXA shield logo" className="h-10 w-10" />
            <span>
              <span className="block text-lg font-extrabold tracking-widest leading-none">NEXA</span>
              <span className="block text-[10px] uppercase tracking-[0.18em] text-amber-300 mt-1">Fraud Intelligence</span>
            </span>
          </a>
          <nav className="hidden lg:flex items-center gap-6 text-[13px] font-semibold text-slate-200" aria-label="Primary navigation">
            <a className="hover:text-amber-300" href="#capabilities">Capabilities</a>
            <a className="hover:text-amber-300" href="#intelligence">AI &amp; Forensics</a>
            <a className="hover:text-amber-300" href="#security">Security</a>
            <a className="hover:text-amber-300" href="#industries">Industries</a>
            <a className="hover:text-amber-300" href="#editions">Editions</a>
            <a className="hover:text-amber-300" href="#contact">Contact</a>
          </nav>
          <button onClick={onLogin} className="nexa-button inline-flex items-center gap-2 rounded-lg bg-amber-400 px-4 py-2.5 text-[#0A192F] font-extrabold hover:bg-amber-300 transition">
            <LockKeyhole size={16} /> Secure Login
          </button>
        </div>
      </header>

      <main id="top">
        {/* Hero */}
        <section className="bg-gradient-to-b from-[#F7F9FC] to-white border-b border-slate-200">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12 lg:py-20 grid gap-10 lg:grid-cols-2 lg:items-center">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.22em] text-amber-700 mb-4">Enterprise Insurance Risk Technology</p>
              <h1 className="nexa-suite-heading text-slate-900 text-[30px] sm:text-[34px]">
                NEXA — Enterprise Insurance Fraud Intelligence Platform
              </h1>
              <p className="mt-5 text-[16px] leading-relaxed text-slate-700 max-w-2xl">
                An AI-powered fraud detection, forensic document verification, claims investigation and enterprise risk intelligence platform. NEXA helps insurers surface suspicious claims earlier, support investigators with explainable evidence and give executives a reliable view of claims exposure.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <button onClick={onRequestDemo} className="nexa-button inline-flex items-center gap-2 rounded-lg bg-[#0F2744] px-5 py-3 text-white font-bold hover:bg-[#1B3A57] transition">
                  Request a demonstration <ArrowRight size={17} />
                </button>
                <button onClick={onLogin} className="nexa-button inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-5 py-3 font-bold text-slate-800 hover:bg-slate-50 transition">
                  <LockKeyhole size={17} /> Access your workspace
                </button>
              </div>
              <ul className="mt-8 grid gap-2 text-[13px] text-slate-600 sm:grid-cols-2">
                <li className="flex gap-2"><CheckCircle2 className="text-emerald-600 shrink-0" size={17} /> Human-led decisions — no automated claim rejection</li>
                <li className="flex gap-2"><CheckCircle2 className="text-emerald-600 shrink-0" size={17} /> Explainable risk indicators on every alert</li>
                <li className="flex gap-2"><CheckCircle2 className="text-emerald-600 shrink-0" size={17} /> Document forensics and comparison</li>
                <li className="flex gap-2"><CheckCircle2 className="text-emerald-600 shrink-0" size={17} /> Audited, role-based access to information</li>
              </ul>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
              <img src={HERO} alt="NEXA analytics environment showing digital claims analysis, fraud intelligence, document verification and financial risk monitoring" className="w-full h-auto rounded-xl" />
              <p className="text-[12px] text-slate-500 px-2 py-2">Illustrative product visual — dashboards display figures calculated from authorised records.</p>
            </div>
          </div>
        </section>

        {/* Capabilities */}
        <section id="capabilities" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-14 lg:py-20">
          <SectionHeading eyebrow="Platform capabilities" title="One workspace across the claims risk lifecycle" text="From first notice of loss and document intake through investigation and executive reporting, NEXA keeps the evidence and the decision trail together." />
          <div className="mt-9 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map((c) => (
              <article key={c.title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                {c.image ? <img src={c.image} alt="" aria-hidden="true" className="h-12 w-12 mb-4" /> : <span className="inline-flex h-12 w-12 items-center justify-center rounded-lg bg-slate-100 text-amber-700 mb-4"><c.icon size={22} /></span>}
                <h3 className="nexa-card-heading text-slate-900 flex items-center gap-2"><c.icon size={18} className="text-amber-700" /> {c.title}</h3>
                <p className="mt-2 text-[14px] leading-relaxed text-slate-600">{c.text}</p>
              </article>
            ))}
          </div>
        </section>

        {/* AI and forensics */}
        <section id="intelligence" className="border-y border-slate-200 bg-[#F7F9FC]">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-14 lg:py-20 grid gap-10 lg:grid-cols-2">
            <div>
              <SectionHeading eyebrow="Explainable AI" title="Intelligence investigators can examine and challenge" text="The platform evaluates claim amounts, frequency, policy inception, claim history, document consistency and beneficiary information. Each alert explains which indicators contributed, what evidence supports the assessment and which action is recommended. A risk score is a lead for a trained investigator — never a finding of fraud." />
              <div className="mt-6 space-y-3">
                {['Duplicate and near-duplicate claim screening', 'Behavioural and submission-pattern anomalies', 'Relationship network analysis across policies and contacts', 'Historical investigation outcome awareness'].map((t) => (
                  <p key={t} className="flex items-start gap-2 text-[14px] text-slate-700"><CheckCircle2 size={17} className="text-emerald-600 mt-0.5 shrink-0" /> {t}</p>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="nexa-suite-section text-slate-900">Forensic document laboratory</h3>
              <p className="mt-2 text-[14px] text-slate-600">Authorised users upload a document and receive an analysis report covering extraction, classification, extracted fields, inconsistencies, duplicate fingerprints and cross-document checks. Investigators review every finding.</p>
              <ol className="mt-5 space-y-3">
                {['Validate and store the uploaded file', 'Extract text with OCR and identify document type', 'Compare extracted fields against the claim record', 'Record forensic observations and generate a report', 'Investigator reviews and records a verified finding'].map((s, i) => (
                  <li key={s} className="flex gap-3 text-[14px] text-slate-700"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#0F2744] text-[12px] font-bold text-white">{i + 1}</span>{s}</li>
                ))}
              </ol>
              <p className="mt-5 text-[12px] text-slate-500">Supported document types include death certificates, identification documents, medical reports, claim forms, policy documents, beneficiary forms and payment records.</p>
            </div>
          </div>
        </section>

        {/* Security */}
        <section id="security" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-14 lg:py-20 grid gap-10 lg:grid-cols-2 lg:items-center">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <img src="/images/features/enterprise-security.svg" alt="" aria-hidden="true" className="h-16 w-16" />
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {[
                ['Role-based access', 'Permissions are checked by backend APIs, not just the navigation menu.'],
                ['Audit trail', 'Logins, claim changes, document access and investigation updates are recorded.'],
                ['Protected documents', 'Stored with access controls and integrity checks.'],
                ['Security monitoring', 'Authentication activity and failed login trends are available to authorised administrators.'],
              ].map(([t, d]) => (
                <div key={t} className="rounded-lg border border-slate-200 p-4">
                  <ShieldAlert size={18} className="text-amber-700" />
                  <p className="mt-2 font-bold text-[14px] text-slate-900">{t}</p>
                  <p className="mt-1 text-[12px] leading-relaxed text-slate-600">{d}</p>
                </div>
              ))}
            </div>
          </div>
          <div>
            <SectionHeading eyebrow="Enterprise security centre" title="Control access to sensitive claims information" text="NEXA records security-relevant activity and presents it to authorised administrators. Multi-factor authentication, session policy and data retention settings are configurable deployment controls; the active status of each control is reported from system configuration rather than assumed." />
            <p className="mt-4 text-[13px] text-slate-500">Security assertions are limited to controls actually configured and verified in a deployment. Independent certification is not implied.</p>
          </div>
        </section>

        {/* Industries */}
        <section id="industries" className="border-y border-slate-200 bg-[#F7F9FC] py-14 lg:py-16">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <SectionHeading eyebrow="Industry applications" title="Built around insurance and claims operations" />
            <div className="mt-7 flex flex-wrap gap-3">
              {INDUSTRIES.map((i) => (
                <span key={i} className="rounded-full border border-slate-300 bg-white px-4 py-2 text-[14px] font-semibold text-slate-700 flex items-center gap-2"><Building2 size={15} className="text-amber-700" /> {i}</span>
              ))}
            </div>
          </div>
        </section>

        {/* Editions */}
        <section id="editions" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-14 lg:py-20">
          <SectionHeading eyebrow="Product editions" title="Choose the depth of capability your organisation needs" text="Edition availability, limits and commercial terms are agreed directly with NEXA. This page does not process payments or activate subscriptions." />
          <div className="mt-9 grid gap-5 lg:grid-cols-3">
            {EDITIONS.map((e) => (
              <article key={e.name} className={`rounded-xl border p-6 shadow-sm ${e.featured ? 'border-amber-400 bg-amber-50/40' : 'border-slate-200 bg-white'}`}>
                {e.featured && <p className="text-[10px] font-black uppercase tracking-widest text-amber-700 mb-2">Broadest capability set</p>}
                <h3 className="nexa-suite-section text-slate-900">{e.name}</h3>
                <p className="mt-1 text-[13px] text-slate-500">{e.audience}</p>
                <ul className="mt-4 space-y-2 text-[14px] text-slate-700">
                  {e.features.map((f) => <li key={f} className="flex gap-2"><CheckCircle2 size={16} className="text-emerald-600 mt-0.5 shrink-0" /> {f}</li>)}
                </ul>
                <button onClick={onRequestDemo} className="mt-6 w-full rounded-lg border border-slate-300 bg-white py-2.5 text-[14px] font-bold text-slate-800 hover:bg-slate-50">Discuss this edition</button>
              </article>
            ))}
          </div>
        </section>

        {/* Contact */}
        <section id="contact" className="bg-[#0A192F] text-slate-100">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-14 lg:py-20 grid gap-10 lg:grid-cols-2">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.22em] text-amber-300 mb-2">Contact and demonstration</p>
              <h2 className="nexa-suite-heading text-white">See NEXA with your own claims workflow</h2>
              <p className="mt-4 text-[15px] leading-relaxed text-slate-300">We demonstrate the platform using clearly identified synthetic insurance data: claim registration, document upload, OCR extraction, AI risk assessment, investigation assignment, evidence collection, outcomes and executive reporting. No production customer records are used.</p>
              <div className="mt-6 space-y-2 text-[14px] text-slate-300">
                <p className="flex items-center gap-2"><Mail size={16} className="text-amber-300" /> Enquiries are recorded in the NEXA enquiry register with a reference</p>
                <p className="flex items-center gap-2"><Phone size={16} className="text-amber-300" /> Contact arrangements are agreed directly with the deployment team</p>
                <p className="flex items-center gap-2"><MapPin size={16} className="text-amber-300" /> Deployment and support by agreement</p>
              </div>
            </div>
            <div className="rounded-xl bg-white p-6 text-slate-800 shadow-lg">
              <h3 className="nexa-suite-section text-slate-900">Request a product demonstration</h3>
              <p className="mt-2 text-[13px] text-slate-600">Submitting stores your enquiry in the NEXA enquiry register and returns a reference. No email is claimed to be sent, and no licence or payment is created.</p>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <label className="text-[13px] font-bold text-slate-700">Organisation<input value={enquiry.organisation} onChange={e => setEnquiry({ ...enquiry, organisation: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 p-3 text-[14px]" placeholder="Insurance company name" id="demo-org" /></label>
                <label className="text-[13px] font-bold text-slate-700">Work email<input type="email" value={enquiry.email} onChange={e => setEnquiry({ ...enquiry, email: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 p-3 text-[14px]" placeholder="name@organisation.com" id="demo-email" /></label>
              </div>
              <label className="mt-3 block text-[13px] font-bold text-slate-700">Areas of interest<textarea value={enquiry.interests} onChange={e => setEnquiry({ ...enquiry, interests: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 p-3 text-[14px]" rows="3" id="demo-notes" placeholder="Claims, forensics, investigations, executive reporting…" /></label>
              <button
                onClick={submitEnquiry}
                disabled={enquiryBusy}
                className="mt-5 w-full rounded-lg bg-[#0F2744] py-3 text-[15px] font-bold text-white hover:bg-[#1B3A57] disabled:opacity-60"
              >
                {enquiryBusy ? 'Recording enquiry…' : 'Submit enquiry'} <ArrowRight size={16} className="inline" />
              </button>
              {enquiryStatus && <p className="mt-3 text-[13px] font-semibold text-emerald-800" role="status">{enquiryStatus}</p>}
              <p className="mt-3 text-[12px] text-slate-500">Existing customers should use <button onClick={onLogin} className="font-bold text-blue-900 underline">Secure Login</button> instead.</p>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-[#071526] text-slate-400 py-8">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <img src={LOGO} alt="" aria-hidden="true" className="h-9 w-9" />
            <p className="text-[13px]"><strong className="text-slate-100">NEXA</strong> — Enterprise Insurance Fraud Intelligence Platform</p>
          </div>
          <p className="text-[12px]">Illustrative visuals. Product capabilities and availability are subject to agreed deployment scope. No regulatory certification is claimed.</p>
        </div>
      </footer>
    </div>
  );
}
