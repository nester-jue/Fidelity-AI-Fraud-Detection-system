# NEXA Sample Claim Documents — Document Register

Genuine, publicly-available insurance, medical, funeral, hospitalisation and
accident/disability claim forms (all PDFs downloaded with `curl`). Original
documents preserved; nothing was altered. This register is read by
`backend/app/services/sample_documents.py` for source attribution.

| # | File | Category | Source Institution | Source URL | Size (bytes) |
|---|---|---|---|---|---|
| 1 | life_insurance_bajajlife_death_claim_form.pdf | life_insurance | Bajaj Life | https://bajajlifeinsurance.com/content/dam/balic-web/pdf/claims/deathClaim/Deathclaimapplicationform-min.pdf | 176335 |
| 2 | life_insurance_pearlnylife_death_claim_form.pdf | life_insurance | Pearl NY Life | https://marketing.pearlinsurance.com/cdn/NYL-Forms/Death-Claim-Form.pdf | 2033630 |
| 3 | funeral_claims_fiji_care_funeral_benefit_claim_form.pdf | funeral_claims | Fiji Care | https://fijicare.com.fj/Images/Forms/Funeral%20Benefit%20Claim%20Form.pdf | 41590 |
| 4 | funeral_claims_hollard_funeral_claim_form.pdf | funeral_claims | Hollard Group Risk | https://hollardgrouprisk.com/forms/Funeral_Claim_Form.pdf | 3643261 |
| 5 | funeral_claims_uwrf_funeral_claim_form.pdf | funeral_claims | UWF / Sanlam | https://uwrf.co.za/wp-content/uploads/2024/01/Funeral-claim-form.pdf | 842429 |
| 6 | medical_insurance_cigna_medical_claim_form.pdf | medical_insurance | Cigna | https://cigna.com/static/www-cigna-com/docs/form-medical-claim.pdf | 651002 |
| 7 | medical_insurance_mediassist_reimbursement_claim_form.pdf | medical_insurance | Medi Assist | https://t.mediassist.in/Resource/PolicyDocs/Reimbursement_ClaimForm.pdf | 951760 |
| 8 | hospitalisation_uhs_discharge_summary.pdf | hospitalisation | UHS NHS Trust (UK) | https://www.uhs.nhs.uk/Media/UHS-website-2019/Docs/Clinical-forms/Dischargesummary.pdf | 27687 |
| 9 | hospitalisation_vidal_standard_discharge_summary.pdf | hospitalisation | Vidal Health TPA | https://vidalfestorage.blob.core.windows.net/vidal-homepage/vidalhealthtpa/vidal%20forms/Standard_Discharge_Summary.pdf | 260774 |
| 10 | accident_disability_cic_kenya_personal_accident_claim_form.pdf | accident_disability | CIC Insurance Group (Kenya) | https://ke.cicinsurancegroup.com/wp-content/uploads/2021/09/Personal-Accident-Claim-Form.pdf | 432133 |
| 11 | accident_disability_magma_individual_personal_accident_claim_form.pdf | accident_disability | Magma Insurance | https://www.magmainsurance.com/documents/5553002/0/Claim+Form+%E2%80%93+Individual+Personal+Accident.pdf/2d59aae4-6df1-0bfd-35df-de8e4e127b89?t=1765015379162 | 1457516 |

> Note: the Magma form URL was dead (redirected to the homepage); the working
> URL above includes the required signed query string (verified: HTTP 200,
> `application/pdf`).
| 12 | accident_disability_mua_personal_accident_claim_form.pdf | accident_disability | MUA (South Africa) | https://mua.co.za/wp-content/uploads/2026/07/Personal-Accident-Claim-Form-2026-version-1.pdf | 239656 |

Notes:
- Doc 11 (Magma): text extraction returned empty — image-based PDF;
  confidence 0.35, flagged for manual review during forensic checks.
- Docs 3 & 5: funeral forms of Fiji Care, Hollard Group Risk and Sanlam UWF.
- Docs 1 & 2: death claim forms of Bajaj Life and Pearl NY Life.
