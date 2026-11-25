import React, { useState, useEffect, useRef } from 'react';
import {
  Upload, ScanText, FileText, CheckCircle2, AlertTriangle,
  X, Eye, Edit3, Check, Clock, AlertCircle, Info
} from 'lucide-react';
import { api } from '../../api/apiClient.js';

const statusBadge = (status) => {
  const map = {
    pending: 'bg-slate-100 text-slate-700',
    processing: 'bg-blue-100 text-blue-800',
    completed: 'bg-emerald-100 text-emerald-800',
    failed: 'bg-red-100 text-red-800',
  };
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${map[status] || 'bg-slate-100 text-slate-700'}`}>{status}</span>;
};

function ConfidenceBar({ score }) {
  const pct = Math.min(100, Math.max(0, score || 0));
  const color = pct >= 80 ? '#10B981' : pct >= 50 ? '#F59E0B' : '#EF4444';
  return (
    <div className="flex items-center space-x-2">
      <div className="w-16 h-2 bg-slate-200 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-mono font-bold" style={{ color }}>{pct.toFixed(0)}%</span>
    </div>
  );
}

export default function OCRDocumentPage({ user, activeTab }) {
  const [overview, setOverview] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [uploadError, setUploadError] = useState('');
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [claimRef, setClaimRef] = useState('');
  const [correctionField, setCorrectionField] = useState('');
  const [correctionValue, setCorrectionValue] = useState('');
  const [correctionNote, setCorrectionNote] = useState('');
  const [showCorrectionForm, setShowCorrectionForm] = useState(false);
  const [sampleDocs, setSampleDocs] = useState([]);
  const [sampleDetail, setSampleDetail] = useState(null);
  const [forensics, setForensics] = useState(null);
  const fileInputRef = useRef(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [ovRes, docsRes, samplesRes, forensicsRes] = await Promise.all([
        api.ocrOverview(),
        api.listOcrDocuments(),
        api.listSampleDocuments(),
        api.getForensicAnalysis(),
      ]);
      if (ovRes.ok) setOverview(await ovRes.json());
      if (docsRes.ok) setDocuments(await docsRes.json());
      if (samplesRes.ok) setSampleDocs(await samplesRes.json());
      if (forensicsRes.ok) setForensics(await forensicsRes.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (['ocr-upload', 'ocr-results', 'ocr-evidence', 'ocr-samples', 'ocr-forensics'].includes(activeTab)) {
      loadData();
    }
  }, [activeTab]);

  const handleUpload = async (e) => {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadResult(null);
    setUploadError('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      if (claimRef.trim()) fd.append('claim_reference', claimRef.trim());
      const res = await api.uploadDocument(fd);
      const data = await res.json();
      if (res.ok) {
        setUploadResult(data);
        await loadData();
        if (fileInputRef.current) fileInputRef.current.value = '';
        setClaimRef('');
      } else {
        setUploadError(data.detail || 'Upload failed. Please try again.');
      }
    } catch (err) {
      setUploadError('Network error during upload. Please check your connection.');
    } finally {
      setUploading(false);
    }
  };

  const handleCorrection = async (docId) => {
    if (!correctionField || !correctionValue) return;
    try {
      const res = await api.correctOcrField(docId, {
        field_name: correctionField,
        corrected_value: correctionValue,
        correction_note: correctionNote,
      });
      if (res.ok) {
        setShowCorrectionForm(false);
        setCorrectionField('');
        setCorrectionValue('');
        setCorrectionNote('');
        // Reload selected doc
        const docRes = await api.getOcrDocument(docId);
        if (docRes.ok) setSelectedDoc(await docRes.json());
        await loadData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleVerify = async (docId) => {
    try {
      await api.verifyOcrDocument(docId);
      const docRes = await api.getOcrDocument(docId);
      if (docRes.ok) setSelectedDoc(await docRes.json());
      await loadData();
    } catch (err) {
      console.error(err);
    }
  };

  if (activeTab === 'ocr-upload') {
    return (
      <div className="space-y-6 max-w-4xl">
        {/* Header */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
          <div className="flex items-center space-x-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center">
              <Upload size={20} className="text-blue-700" />
            </div>
            <div>
              <h1 className="nexa-suite-heading text-slate-900">Document Upload & OCR Processing</h1>
              <p className="text-xs text-slate-500">Upload claim documents for automated text extraction and fraud analysis integration.</p>
            </div>
          </div>
        </div>

        {/* Upload Form */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <h2 className="nexa-suite-section text-slate-900 uppercase mb-4">Upload Document</h2>
          <form onSubmit={handleUpload} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Select Document *</label>
              <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center hover:border-blue-400 transition cursor-pointer"
                onClick={() => fileInputRef.current?.click()}>
                <ScanText size={32} className="mx-auto text-slate-400 mb-2" />
                <p className="text-xs font-semibold text-slate-600">Click to select or drag and drop</p>
                <p className="text-[11px] text-slate-400 mt-1">PDF, PNG, JPG, TIFF — Max 20MB</p>
                <input ref={fileInputRef} type="file" className="hidden"
                  accept=".pdf,.png,.jpg,.jpeg,.tiff,.webp,.txt" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Associated Claim Reference (Optional)</label>
              <input
                type="text"
                placeholder="e.g. CLM-2026-XXXXXX"
                value={claimRef}
                onChange={e => setClaimRef(e.target.value)}
                className="w-full p-3 border border-slate-300 rounded-xl text-xs"
              />
              <p className="text-[11px] text-slate-400 mt-1">Link this document to an existing claim for integrated fraud analysis.</p>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
              <p className="text-xs font-bold text-blue-800 mb-2">Supported Document Types:</p>
              <div className="grid grid-cols-2 gap-1 text-[11px] text-blue-700">
                {['Claim Forms', 'National ID Documents', 'Medical Reports', 'Death Certificates',
                  'Police Reports', 'Funeral Invoices', 'Receipts', 'Policy Documents'].map(d => (
                  <div key={d} className="flex items-center space-x-1">
                    <CheckCircle2 size={11} className="text-blue-500" />
                    <span>{d}</span>
                  </div>
                ))}
              </div>
            </div>

            {uploadError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl flex items-start space-x-2">
                <AlertCircle size={16} className="text-red-600 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-red-800 font-semibold">{uploadError}</p>
              </div>
            )}

            <button type="submit" disabled={uploading}
              className="w-full py-3 bg-blue-700 hover:bg-blue-800 text-white rounded-xl font-bold text-sm transition disabled:opacity-50 flex items-center justify-center space-x-2">
              <Upload size={16} />
              <span>{uploading ? 'Processing Document...' : 'Upload & Extract'}</span>
            </button>
          </form>

          {/* Upload Result */}
          {uploadResult && (
            <div className="mt-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
              <div className="flex items-center space-x-2 mb-3">
                <CheckCircle2 size={18} className="text-emerald-600" />
                <p className="text-sm font-bold text-emerald-800">Document processed successfully!</p>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <p className="text-slate-500 font-semibold">Document Type</p>
                  <p className="font-bold text-slate-800">{uploadResult.document_type || 'Unknown'}</p>
                </div>
                <div>
                  <p className="text-slate-500 font-semibold">Confidence Score</p>
                  <p className="font-bold text-slate-800">{(uploadResult.confidence_score || 0).toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-slate-500 font-semibold">Extracted Dates</p>
                  <p className="font-bold text-slate-800">{uploadResult.extracted_dates?.join(', ') || 'None detected'}</p>
                </div>
                <div>
                  <p className="text-slate-500 font-semibold">National IDs</p>
                  <p className="font-bold text-slate-800">{uploadResult.extracted_national_ids?.join(', ') || 'None detected'}</p>
                </div>
              </div>
              {uploadResult.has_date_mismatch && (
                <div className="mt-3 p-2 bg-amber-100 border border-amber-300 rounded-lg flex items-center space-x-2">
                  <AlertTriangle size={14} className="text-amber-600" />
                  <p className="text-xs font-bold text-amber-800">Date mismatch detected between document and claim date.</p>
                </div>
              )}
              {uploadResult.flags?.length > 0 && (
                <div className="mt-2">
                  <p className="text-[11px] font-bold text-slate-600 mb-1">Processing Flags:</p>
                  <div className="flex flex-wrap gap-1">
                    {uploadResult.flags.map((f, i) => (
                      <span key={i} className="px-2 py-0.5 bg-amber-100 text-amber-800 rounded text-[10px] font-bold">{f}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* OCR Overview Stats */}
        {overview && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {[
              { label: 'Total Documents', value: overview.total_documents, color: 'border-t-slate-700' },
              { label: 'Successfully Processed', value: overview.documents_completed, color: 'border-t-emerald-500' },
              { label: 'Awaiting Processing', value: overview.documents_pending, color: 'border-t-blue-500' },
              { label: 'Failed Jobs', value: overview.documents_failed, color: 'border-t-red-500' },
              { label: 'Requiring Review', value: overview.documents_requiring_manual_review, color: 'border-t-amber-500' },
              { label: 'Avg. Confidence', value: `${overview.average_extraction_confidence}%`, color: 'border-t-purple-500' },
            ].map((kpi, i) => (
              <div key={i} className={`bg-white p-4 rounded-2xl border border-slate-200 shadow-sm border-t-4 ${kpi.color}`}>
                <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{kpi.label}</p>
                <p className="nexa-suite-card mt-1">{kpi.value ?? '—'}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Genuine Claim Forms tab — sample claim documents from data/sample_claim_documents
  if (activeTab === 'ocr-samples') {
    return (
      <div className="space-y-6">
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <h1 className="nexa-suite-heading text-slate-900">Genuine Claim Forms (Sample Documents)</h1>
            <p className="text-xs text-slate-500">
              Real, publicly-available insurance, medical, funeral, hospitalisation and accident/disability claim forms,
              ingested from verified institutions. Extracted information and OCR results are shown below.
            </p>
          </div>
          <button onClick={loadData} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-xl text-xs font-bold text-slate-700 transition">
            Refresh
          </button>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-slate-400 text-sm">Loading documents...</div>
          ) : sampleDocs.length === 0 ? (
            <div className="p-12 text-center">
              <FileText size={40} className="mx-auto text-slate-300 mb-3" />
              <p className="text-sm font-bold text-slate-500">No sample claim documents yet</p>
              <p className="text-xs text-slate-400 mt-1">Sample claim forms are ingested from data/sample_claim_documents by the system.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4">ID</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4">Filename</th>
                    <th className="py-3 px-4">Source Institution</th>
                    <th className="py-3 px-4">Confidence</th>
                    <th className="py-3 px-4">Missing Fields</th>
                    <th className="py-3 px-4">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {sampleDocs.map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-50 transition">
                      <td className="py-3 px-4 font-mono text-slate-600">#{doc.id}</td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded text-[10px] font-bold uppercase">{doc.sample_category}</span>
                      </td>
                      <td className="py-3 px-4 font-semibold text-slate-800 max-w-[170px] truncate" title={doc.filename}>{doc.filename}</td>
                      <td className="py-3 px-4 text-slate-500" title={doc.source_url}>{doc.source_institution || '—'}</td>
                      <td className="py-3 px-4"><ConfidenceBar score={doc.confidence_score} /></td>
                      <td className="py-3 px-4">
                        {doc.missing_fields?.length > 0
                          ? doc.missing_fields.join(', ')
                          : <span className="text-emerald-600 font-bold">None detected</span>}
                      </td>
                      <td className="py-3 px-4">
                        <button
                          onClick={() => api.getSampleDocument(doc.id).then(r => r.ok && r.json()).then(d => setSampleDetail(d)).catch(() => setSampleDetail(null))}
                          className="px-3 py-1 bg-blue-700 text-white rounded-lg text-[11px] font-bold hover:bg-blue-800 transition flex items-center space-x-1"
                        >
                          <Eye size={11} />
                          <span>View Details</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Sample document detail modal — full OCR extraction data */}
        {sampleDetail && (
          <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 overflow-y-auto">
            <div className="bg-white rounded-3xl max-w-3xl w-full shadow-2xl border border-slate-200 max-h-[85vh] overflow-y-auto">
              <div className="sticky top-0 bg-white border-b border-slate-200 p-5 flex items-center justify-between rounded-t-3xl">
                <div>
                  <h2 className="nexa-suite-section text-slate-900">Sample Claim Form — OCR Details</h2>
                  <p className="text-xs text-slate-500">{sampleDetail.filename} · {sampleDetail.source_institution || 'n/a'}</p>
                </div>
                <button onClick={() => setSampleDetail(null)} className="p-2 text-slate-400 hover:text-slate-700 rounded-xl hover:bg-slate-100">
                  <X size={18} />
                </button>
              </div>
              <div className="p-6 space-y-5">
                <div className="grid grid-cols-2 gap-4 text-xs">
                  {[
                    ['Document Type', sampleDetail.document_type || 'Unknown'],
                    ['Category', sampleDetail.sample_category],
                    ['OCR Engine', sampleDetail.ocr_engine || 'Unknown'],
                    ['Confidence', `${(sampleDetail.confidence_score || 0).toFixed(1)}%`],
                    ['SHA-256 Fingerprint', sampleDetail.document_hash_sha256 ? `${sampleDetail.document_hash_sha256.slice(0, 16)}…` : 'n/a'],
                    ['Size (bytes)', sampleDetail.file_size_bytes],
                  ].map(([label, val], i) => (
                    <div key={i} className="bg-slate-50 rounded-xl p-3">
                      <p className="text-slate-500 font-semibold">{label}</p>
                      <p className="font-bold text-slate-800 break-all">{val ?? '—'}</p>
                    </div>
                  ))}
                </div>
                {sampleDetail.source_url && (
                  <div className="bg-slate-50 rounded-xl p-3">
                    <p className="text-slate-500 font-semibold">Source URL</p>
                    <a href={sampleDetail.source_url} target="_blank" rel="noreferrer"
                       className="text-blue-700 font-bold hover:underline break-all">{sampleDetail.source_url}</a>
                  </div>
                )}
                {sampleDetail.has_date_mismatch && (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-start space-x-2">
                    <AlertTriangle size={16} className="text-amber-600 mt-0.5 flex-shrink-0" />
                    <p className="text-xs text-amber-800 font-semibold">Date mismatch detected between document and claim date.</p>
                  </div>
                )}
                <h3 className="nexa-suite-section text-slate-700 uppercase">Structured Extracted Fields</h3>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  {[
                    ['Claimant Name', sampleDetail.extracted_fields?.claimant_name],
                    ['Policy Number', sampleDetail.extracted_fields?.policy_number],
                    ['Claim Number', sampleDetail.extracted_fields?.claim_number],
                    ['Date of Birth', sampleDetail.extracted_fields?.date_of_birth],
                    ['Incident/Death Date', sampleDetail.extracted_fields?.incident_date],
                    ['Claimed Amount', sampleDetail.extracted_fields?.claimed_amount != null ? `$${sampleDetail.extracted_fields.claimed_amount.toLocaleString()}` : null],
                    ['Medical Practitioner', sampleDetail.extracted_fields?.medical_practitioner],
                    ['Hospital/Institution', sampleDetail.extracted_fields?.hospital_name],
                    ['Diagnosis', sampleDetail.extracted_fields?.diagnosis],
                    ['Beneficiary Name', sampleDetail.extracted_fields?.beneficiary_name],
                  ].map(([label, val]) => val && (
                    <div key={label} className="bg-slate-50 rounded-xl p-3">
                      <p className="text-slate-500 font-semibold text-[10px] uppercase">{label}</p>
                      <p className="font-bold text-slate-800 break-all">{val}</p>
                    </div>
                  ))}
                </div>
                <h3 className="nexa-suite-section text-slate-700 uppercase mt-4">Observed Data</h3>
                <div className="grid grid-cols-1 gap-3 text-xs">
                  {sampleDetail.extracted_dates?.length > 0 && (
                    <div className="bg-slate-50 rounded-xl p-3">
                      <p className="text-[11px] font-bold text-slate-500 uppercase mb-1">Extracted Dates</p>
                      <div className="flex flex-wrap gap-2">
                        {sampleDetail.extracted_dates.map((d, i) => (
                          <span key={i} className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs font-bold">{d}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {sampleDetail.extracted_amounts?.length > 0 && (
                    <div className="bg-slate-50 rounded-xl p-3">
                      <p className="text-[11px] font-bold text-slate-500 uppercase mb-1">Extracted Amounts</p>
                      <div className="flex flex-wrap gap-2">
                        {sampleDetail.extracted_amounts.map((a, i) => (
                          <span key={i} className="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded text-xs font-bold">${Number(a).toLocaleString()}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {sampleDetail.extracted_national_ids?.length > 0 && (
                    <div className="bg-slate-50 rounded-xl p-3">
                      <p className="text-[11px] font-bold text-slate-500 uppercase mb-1">National IDs</p>
                      <div className="flex flex-wrap gap-2">
                        {sampleDetail.extracted_national_ids.map((id, i) => (
                          <span key={i} className="px-2 py-0.5 bg-purple-100 text-purple-800 rounded text-xs font-mono font-bold">{id}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                {(sampleDetail.missing_fields || []).length > 0 && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-xl">
                    <p className="text-xs font-bold text-red-700 mb-2 flex items-center space-x-1">
                      <AlertCircle size={14} className="text-red-600" />
                      <span>Missing Mandatory Fields</span>
                    </p>
                    {sampleDetail.missing_fields.map((f, i) => (
                      <p key={i} className="text-xs text-red-800">• {f}</p>
                    ))}
                  </div>
                )}
                {sampleDetail.raw_text_snippet && (
                  <div>
                    <h3 className="nexa-suite-section text-slate-700 uppercase mb-2">Extracted Text (Snippet)</h3>
                    <div className="bg-slate-900 text-slate-200 rounded-xl p-4 text-[11px] font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
                      {sampleDetail.raw_text_snippet}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Document Forensics tab — duplicates, cross-document inconsistencies, suspicious flags
  if (activeTab === 'ocr-forensics') {
    const analysis = forensics || { duplicate_groups: [], claim_consistency_issues: [], suspicious_flags: [] };
    return (
      <div className="space-y-6">
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <h1 className="nexa-suite-heading text-slate-900">Document Forensics</h1>
            <p className="text-xs text-slate-500">
              Duplicate documents, cross-document inconsistencies and suspicious flags — all findings require human review.
            </p>
          </div>
          <button onClick={loadData} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-xl text-xs font-bold text-slate-700 transition">
            Refresh
          </button>
        </div>

        {/* Summary */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-blue-500">
            <p className="text-[11px] font-bold text-slate-500 uppercase">Duplicate Groups</p>
            <p className="nexa-suite-card mt-1">{analysis.summary?.duplicate_groups ?? analysis.duplicate_groups.length}</p>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-amber-500">
            <p className="text-[11px] font-bold text-slate-500 uppercase">Consistency Issues</p>
            <p className="nexa-suite-card mt-1">{analysis.summary?.claim_consistency_issues ?? analysis.claim_consistency_issues.length}</p>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm border-t-4 border-red-500">
            <p className="text-[11px] font-bold text-slate-500 uppercase">Suspicious Flags</p>
            <p className="nexa-suite-card mt-1">{analysis.summary?.suspicious_flags ?? analysis.suspicious_flags.length}</p>
          </div>
        </div>

        {/* Duplicate groups */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-200">
            <h2 className="nexa-suite-section text-slate-900 uppercase">Duplicate Documents (SHA-256 fingerprint match)</h2>
          </div>
          {analysis.duplicate_groups.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm">No duplicate documents found.</div>
          ) : (
            analysis.duplicate_groups.map((group, gi) => (
              <div key={group.hash} className="p-4 border-b border-slate-100 last:border-b-0">
                <p className="text-xs font-mono text-slate-500 mb-2">Hash: {group.hash}</p>
                <ul className="space-y-1">
                  {group.documents.map((d, i) => (
                    <li key={i} className="text-xs text-slate-700">
                      • {d.filename} {d.claim_id ? `(Claim ${d.claim_id})` : ''}
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </div>

        {/* Cross-document consistency issues */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-200">
            <h2 className="nexa-suite-section text-slate-900 uppercase">Cross-Document Consistency Issues</h2>
          </div>
          {analysis.claim_consistency_issues.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm">No consistency issues found across documents.</div>
          ) : (
            <div className="divide-y divide-slate-100">
              {analysis.claim_consistency_issues.map((issue, i) => (
                <div key={i} className="p-4">
                  <div className="flex items-center space-x-2 mb-1">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      issue.severity === 'potential_inconsistency' ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'
                    }`}>{issue.severity}</span>
                    <span className="text-xs font-bold text-slate-700">{issue.type}</span>
                    <span className="text-xs text-slate-500 font-mono">Claim {issue.claim_id}</span>
                  </div>
                  <p className="text-xs text-slate-600">{issue.details}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Suspicious flags */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-slate-200">
            <h2 className="nexa-suite-section text-slate-900 uppercase">Suspicious Flags</h2>
          </div>
          {analysis.suspicious_flags.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm">No suspicious flags found.</div>
          ) : (
            <div className="divide-y divide-slate-100">
              {analysis.suspicious_flags.map((flag, i) => (
                <div key={i} className="p-4">
                  <p className="text-xs font-semibold text-slate-700">{flag.filename}</p>
                  <p className="text-xs text-slate-500">{flag.type}{flag.details?.length ? ` — ${flag.details.join(', ')}` : ''}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // OCR Results tab
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex items-center justify-between">
        <div>
          <h1 className="nexa-suite-heading text-slate-900">OCR Extraction Results</h1>
          <p className="text-xs text-slate-500">View, verify and correct OCR-extracted document information.</p>
        </div>
        <button onClick={loadData} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-xl text-xs font-bold text-slate-700 transition">
          Refresh
        </button>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-400 text-sm">Loading documents...</div>
        ) : documents.length === 0 ? (
          <div className="p-12 text-center">
            <ScanText size={40} className="mx-auto text-slate-300 mb-3" />
            <p className="text-sm font-bold text-slate-500">No OCR documents yet</p>
            <p className="text-xs text-slate-400 mt-1">Upload a document to begin OCR processing.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase font-bold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">ID</th>
                  <th className="py-3 px-4">Filename</th>
                  <th className="py-3 px-4">Doc Type</th>
                  <th className="py-3 px-4">Linked Claim</th>
                  <th className="py-3 px-4">Confidence</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Flags</th>
                  <th className="py-3 px-4">Verified</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-4 font-mono text-slate-600">#{doc.id}</td>
                    <td className="py-3 px-4 font-semibold text-slate-800 max-w-[150px] truncate">{doc.filename}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded text-[10px] font-bold">{doc.document_type || 'Unknown'}</span>
                    </td>
                    <td className="py-3 px-4 font-mono text-blue-700">{doc.claim_id || '—'}</td>
                    <td className="py-3 px-4"><ConfidenceBar score={doc.confidence_score} /></td>
                    <td className="py-3 px-4">{statusBadge(doc.processing_status)}</td>
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1">
                        {doc.has_date_mismatch && (
                          <span className="px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded text-[10px] font-bold">Date Mismatch</span>
                        )}
                        {(doc.flags || []).filter(f => f !== 'date_inconsistency').slice(0, 2).map((f, i) => (
                          <span key={i} className="px-1.5 py-0.5 bg-red-100 text-red-800 rounded text-[10px] font-bold">{f}</span>
                        ))}
                        {!doc.has_date_mismatch && (doc.flags || []).length === 0 && (
                          <span className="text-emerald-600 font-bold">Clean</span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {doc.is_manually_verified
                        ? <span className="flex items-center space-x-1 text-emerald-600 font-bold"><Check size={12} /><span>Verified</span></span>
                        : <span className="text-amber-600 font-bold">Pending</span>}
                    </td>
                    <td className="py-3 px-4 text-slate-500">{doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : '—'}</td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() => setSelectedDoc(doc)}
                        className="px-3 py-1 bg-blue-700 text-white rounded-lg text-[11px] font-bold hover:bg-blue-800 transition flex items-center space-x-1"
                      >
                        <Eye size={11} />
                        <span>View</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Document Detail Modal */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-3xl max-w-3xl w-full shadow-2xl border border-slate-200 max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-slate-200 p-5 flex items-center justify-between rounded-t-3xl">
              <div>
                <h2 className="nexa-suite-section text-slate-900">OCR Verification Interface</h2>
                <p className="text-xs text-slate-500">{selectedDoc.filename}</p>
              </div>
              <button onClick={() => { setSelectedDoc(null); setShowCorrectionForm(false); }}
                className="p-2 text-slate-400 hover:text-slate-700 rounded-xl hover:bg-slate-100">
                <X size={18} />
              </button>
            </div>

            <div className="p-6 space-y-5">
              {/* Meta info */}
              <div className="grid grid-cols-2 gap-4 text-xs">
                {[
                  ['Document Type', selectedDoc.document_type || 'Unknown'],
                  ['Processing Status', selectedDoc.processing_status],
                  ['OCR Engine', selectedDoc.ocr_engine || 'Unknown'],
                  ['Confidence Score', `${(selectedDoc.confidence_score || 0).toFixed(1)}%`],
                  ['Linked Claim', selectedDoc.claim_id || 'Not linked'],
                  ['Uploaded By', selectedDoc.uploaded_by || 'Unknown'],
                ].map(([label, val], i) => (
                  <div key={i} className="bg-slate-50 rounded-xl p-3">
                    <p className="text-slate-500 font-semibold mb-0.5">{label}</p>
                    <p className="font-bold text-slate-800">{val}</p>
                  </div>
                ))}
              </div>

              {/* Flags and issues */}
              {(selectedDoc.has_date_mismatch || selectedDoc.flags?.length > 0) && (
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
                  <p className="text-xs font-bold text-amber-800 mb-2 flex items-center space-x-1">
                    <AlertTriangle size={14} />
                    <span>Validation Issues Detected</span>
                  </p>
                  {selectedDoc.has_date_mismatch && (
                    <p className="text-xs text-amber-700 mb-1">• Date mismatch between document and claim submission date.</p>
                  )}
                  {(selectedDoc.missing_fields || []).map((f, i) => (
                    <p key={i} className="text-xs text-amber-700 mb-1">• Missing mandatory field: <strong>{f}</strong></p>
                  ))}
                  {(selectedDoc.flags || []).filter(f => f !== 'date_inconsistency').map((f, i) => (
                    <p key={i} className="text-xs text-amber-700 mb-1">• Flag: <strong>{f}</strong></p>
                  ))}
                </div>
              )}

              {/* Extracted fields */}
              <div>
                <h3 className="nexa-suite-section text-slate-700 uppercase mb-3">Extracted Information</h3>
                <div className="grid grid-cols-1 gap-3">
                  {selectedDoc.extracted_dates?.length > 0 && (
                    <div className="bg-slate-50 rounded-xl p-3">
                      <p className="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-1">Extracted Dates</p>
                      <div className="flex flex-wrap gap-2">
                        {selectedDoc.extracted_dates.map((d, i) => (
                          <span key={i} className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs font-bold">{d}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {selectedDoc.extracted_amounts?.length > 0 && (
                    <div className="bg-slate-50 rounded-xl p-3">
                      <p className="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-1">Extracted Amounts</p>
                      <div className="flex flex-wrap gap-2">
                        {selectedDoc.extracted_amounts.map((a, i) => (
                          <span key={i} className="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded text-xs font-bold">${Number(a).toLocaleString()}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {selectedDoc.extracted_national_ids?.length > 0 && (
                    <div className="bg-slate-50 rounded-xl p-3">
                      <p className="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-1">National IDs</p>
                      <div className="flex flex-wrap gap-2">
                        {selectedDoc.extracted_national_ids.map((id, i) => (
                          <span key={i} className="px-2 py-0.5 bg-purple-100 text-purple-800 rounded text-xs font-mono font-bold">{id}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {!selectedDoc.extracted_dates?.length && !selectedDoc.extracted_amounts?.length && !selectedDoc.extracted_national_ids?.length && (
                    <p className="text-xs text-slate-400 italic">No structured data extracted from this document.</p>
                  )}
                </div>
              </div>

              {/* Raw text snippet */}
              {selectedDoc.raw_text_snippet && (
                <div>
                  <h3 className="nexa-suite-section text-slate-700 uppercase mb-2">Extracted Text (Snippet)</h3>
                  <div className="bg-slate-900 text-slate-200 rounded-xl p-4 text-[11px] font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
                    {selectedDoc.raw_text_snippet}
                  </div>
                </div>
              )}

              {/* Corrections history */}
              {selectedDoc.corrections?.length > 0 && (
                <div>
                  <h3 className="nexa-suite-section text-slate-700 uppercase mb-2">Manual Corrections (Audit Trail)</h3>
                  <div className="space-y-2">
                    {selectedDoc.corrections.map((c, i) => (
                      <div key={i} className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs">
                        <div className="flex justify-between mb-1">
                          <span className="font-bold text-slate-800">Field: <span className="text-blue-700">{c.field}</span></span>
                          <span className="text-slate-500">{c.corrected_by} · {c.corrected_at ? new Date(c.corrected_at).toLocaleDateString() : ''}</span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className="text-red-600 line-through">{c.original || 'N/A'}</span>
                          <span className="text-slate-400">→</span>
                          <span className="text-emerald-700 font-bold">{c.corrected}</span>
                        </div>
                        {c.note && <p className="text-slate-500 mt-1 italic">{c.note}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center space-x-3 pt-2 border-t border-slate-100">
                {!selectedDoc.is_manually_verified && (
                  <button
                    onClick={() => handleVerify(selectedDoc.id)}
                    className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold text-xs transition flex items-center justify-center space-x-2"
                  >
                    <Check size={14} />
                    <span>Mark as Verified</span>
                  </button>
                )}
                <button
                  onClick={() => setShowCorrectionForm(!showCorrectionForm)}
                  className="flex-1 py-2.5 bg-blue-700 hover:bg-blue-800 text-white rounded-xl font-bold text-xs transition flex items-center justify-center space-x-2"
                >
                  <Edit3 size={14} />
                  <span>Apply Correction</span>
                </button>
              </div>

              {/* Correction form */}
              {showCorrectionForm && (
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                  <p className="text-xs font-extrabold text-slate-700 uppercase tracking-wider">Correction Entry</p>
                  <div>
                    <label className="block text-xs font-bold text-slate-600 mb-1">Field Name *</label>
                    <input type="text" placeholder="e.g. customer_name, date_of_death"
                      value={correctionField} onChange={e => setCorrectionField(e.target.value)}
                      className="w-full p-2.5 border border-slate-300 rounded-lg text-xs" />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-600 mb-1">Corrected Value *</label>
                    <input type="text" placeholder="Enter the correct value"
                      value={correctionValue} onChange={e => setCorrectionValue(e.target.value)}
                      className="w-full p-2.5 border border-slate-300 rounded-lg text-xs" />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-600 mb-1">Correction Note</label>
                    <input type="text" placeholder="Reason for correction (optional)"
                      value={correctionNote} onChange={e => setCorrectionNote(e.target.value)}
                      className="w-full p-2.5 border border-slate-300 rounded-lg text-xs" />
                  </div>
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <p className="text-[11px] text-blue-700 font-semibold">
                      <Info size={12} className="inline mr-1" />
                      Original extracted value will be preserved in the audit trail. This correction will be recorded with your name and timestamp.
                    </p>
                  </div>
                  <button onClick={() => handleCorrection(selectedDoc.id)}
                    className="w-full py-2.5 bg-blue-700 hover:bg-blue-800 text-white rounded-xl font-bold text-xs transition">
                    Submit Correction
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
