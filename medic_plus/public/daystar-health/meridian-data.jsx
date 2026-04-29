// Meridian Health — mock data
const PATIENTS = [
  { id: 'MH-10042', mrn: '04287-119', name: 'Eleanor Chen', dob: '1964-03-14', age: 62, sex: 'F', phone: '(415) 555-0142', email: 'e.chen@email.co', insurance: 'BlueCross PPO', primary: 'Dr. Patel', status: 'Stable', risk: 'Low', lastSeen: 'Mar 18, 2026', nextAppt: 'May 02, 2026', conditions: ['Hypertension', 'Type 2 Diabetes'], allergies: ['Penicillin'], meds: 4, vitals: { bp: '128/82', hr: 72, spo2: 98, weight: '142 lb', bmi: 24.1 } },
  { id: 'MH-10118', mrn: '04287-220', name: 'Marcus Rivera', dob: '1981-09-02', age: 44, sex: 'M', phone: '(212) 555-0188', email: 'm.rivera@email.co', insurance: 'Aetna HMO', primary: 'Dr. Okafor', status: 'Watch', risk: 'Moderate', lastSeen: 'Apr 21, 2026', nextAppt: 'Apr 30, 2026', conditions: ['Asthma', 'Seasonal allergies'], allergies: ['Sulfa drugs'], meds: 2, vitals: { bp: '118/76', hr: 78, spo2: 96, weight: '186 lb', bmi: 25.8 } },
  { id: 'MH-10256', mrn: '04287-331', name: 'Priya Nair', dob: '1992-11-28', age: 33, sex: 'F', phone: '(503) 555-0166', email: 'p.nair@email.co', insurance: 'Kaiser', primary: 'Dr. Patel', status: 'Stable', risk: 'Low', lastSeen: 'Apr 10, 2026', nextAppt: 'Oct 15, 2026', conditions: ['Migraine'], allergies: [], meds: 1, vitals: { bp: '110/70', hr: 66, spo2: 99, weight: '128 lb', bmi: 22.4 } },
  { id: 'MH-10341', mrn: '04287-409', name: 'James Whitaker', dob: '1958-06-19', age: 67, sex: 'M', phone: '(617) 555-0190', email: 'j.whitaker@email.co', insurance: 'Medicare + Supp', primary: 'Dr. Okafor', status: 'Urgent', risk: 'High', lastSeen: 'Apr 27, 2026', nextAppt: 'Apr 29, 2026', conditions: ['CHF', 'Atrial fibrillation', 'Type 2 Diabetes'], allergies: ['Codeine', 'Latex'], meds: 7, vitals: { bp: '142/94', hr: 88, spo2: 94, weight: '218 lb', bmi: 28.7 } },
  { id: 'MH-10488', mrn: '04287-512', name: 'Sofia Lindqvist', dob: '1995-02-07', age: 31, sex: 'F', phone: '(404) 555-0123', email: 's.lindqvist@email.co', insurance: 'United HC', primary: 'Dr. Patel', status: 'Stable', risk: 'Low', lastSeen: 'Mar 04, 2026', nextAppt: 'Sep 04, 2026', conditions: ['Hypothyroidism'], allergies: [], meds: 1, vitals: { bp: '116/72', hr: 68, spo2: 99, weight: '136 lb', bmi: 21.9 } },
  { id: 'MH-10527', mrn: '04287-604', name: 'Daniel Osei', dob: '1976-12-11', age: 49, sex: 'M', phone: '(312) 555-0177', email: 'd.osei@email.co', insurance: 'Cigna PPO', primary: 'Dr. Okafor', status: 'Watch', risk: 'Moderate', lastSeen: 'Apr 19, 2026', nextAppt: 'May 14, 2026', conditions: ['Hyperlipidemia'], allergies: [], meds: 2, vitals: { bp: '132/86', hr: 74, spo2: 97, weight: '198 lb', bmi: 27.1 } },
  { id: 'MH-10612', mrn: '04287-718', name: 'Aisha Patel', dob: '1988-04-22', age: 38, sex: 'F', phone: '(305) 555-0102', email: 'a.patel@email.co', insurance: 'Aetna PPO', primary: 'Dr. Patel', status: 'Stable', risk: 'Low', lastSeen: 'Feb 12, 2026', nextAppt: 'Aug 12, 2026', conditions: [], allergies: ['Shellfish'], meds: 0, vitals: { bp: '108/68', hr: 64, spo2: 99, weight: '124 lb', bmi: 22.0 } },
  { id: 'MH-10744', mrn: '04287-822', name: 'Robert Kim', dob: '1949-08-30', age: 76, sex: 'M', phone: '(206) 555-0145', email: 'r.kim@email.co', insurance: 'Medicare', primary: 'Dr. Okafor', status: 'Watch', risk: 'High', lastSeen: 'Apr 24, 2026', nextAppt: 'May 06, 2026', conditions: ['COPD', 'Hypertension'], allergies: [], meds: 5, vitals: { bp: '138/88', hr: 82, spo2: 93, weight: '162 lb', bmi: 23.4 } },
  { id: 'MH-10891', mrn: '04287-901', name: 'Lucia Mendoza', dob: '2001-01-15', age: 25, sex: 'F', phone: '(713) 555-0199', email: 'l.mendoza@email.co', insurance: 'BlueCross HMO', primary: 'Dr. Patel', status: 'Stable', risk: 'Low', lastSeen: 'Mar 28, 2026', nextAppt: 'Sep 28, 2026', conditions: [], allergies: [], meds: 0, vitals: { bp: '112/70', hr: 68, spo2: 99, weight: '130 lb', bmi: 22.1 } },
  { id: 'MH-10923', mrn: '04287-988', name: 'Nathaniel Brooks', dob: '1972-05-08', age: 53, sex: 'M', phone: '(919) 555-0134', email: 'n.brooks@email.co', insurance: 'United HC', primary: 'Dr. Okafor', status: 'Stable', risk: 'Moderate', lastSeen: 'Apr 02, 2026', nextAppt: 'Jul 02, 2026', conditions: ['Anxiety', 'Insomnia'], allergies: ['Iodine'], meds: 3, vitals: { bp: '124/80', hr: 76, spo2: 98, weight: '178 lb', bmi: 25.5 } },
];

const TODAY_APPTS = [
  { time: '08:00', dur: 30, patient: 'Eleanor Chen', id: 'MH-10042', reason: 'Annual physical', provider: 'Dr. Patel', room: 'Room 3', status: 'Checked in', kind: 'standard' },
  { time: '08:45', dur: 20, patient: 'Marcus Rivera', id: 'MH-10118', reason: 'Asthma follow-up', provider: 'Dr. Okafor', room: 'Room 1', status: 'In room', kind: 'followup' },
  { time: '09:30', dur: 45, patient: 'James Whitaker', id: 'MH-10341', reason: 'CHF management', provider: 'Dr. Okafor', room: 'Room 2', status: 'Scheduled', kind: 'urgent' },
  { time: '10:30', dur: 30, patient: 'Daniel Osei', id: 'MH-10527', reason: 'Lipid panel review', provider: 'Dr. Okafor', room: 'Room 1', status: 'Scheduled', kind: 'standard' },
  { time: '11:15', dur: 20, patient: 'Lucia Mendoza', id: 'MH-10891', reason: 'New patient intake', provider: 'Dr. Patel', room: 'Room 4', status: 'Scheduled', kind: 'standard' },
  { time: '13:00', dur: 30, patient: 'Robert Kim', id: 'MH-10744', reason: 'COPD review', provider: 'Dr. Okafor', room: 'Room 2', status: 'Scheduled', kind: 'followup' },
  { time: '14:00', dur: 20, patient: 'Sofia Lindqvist', id: 'MH-10488', reason: 'Thyroid labs', provider: 'Dr. Patel', room: 'Room 3', status: 'Scheduled', kind: 'standard' },
  { time: '15:30', dur: 30, patient: 'Nathaniel Brooks', id: 'MH-10923', reason: 'Med review', provider: 'Dr. Okafor', room: 'Room 1', status: 'Scheduled', kind: 'standard' },
];

const VISITS_FOR = (id) => [
  { date: 'Apr 21, 2026', type: 'Office visit', provider: 'Dr. Patel', reason: 'Routine follow-up', notes: 'BP within target. Continue current regimen.' },
  { date: 'Feb 14, 2026', type: 'Telehealth', provider: 'Dr. Patel', reason: 'Medication check-in', notes: 'Tolerating metformin well. No GI side effects.' },
  { date: 'Dec 03, 2025', type: 'Office visit', provider: 'Dr. Patel', reason: 'Annual physical', notes: 'Comprehensive exam. Labs ordered. Flu vaccine administered.' },
  { date: 'Aug 18, 2025', type: 'Office visit', provider: 'Dr. Okafor (covering)', reason: 'Acute sinusitis', notes: 'Z-pack 5-day course. Symptom resolution expected within 48-72h.' },
];

const LABS_FOR = (id) => [
  { name: 'A1c', value: '6.8', unit: '%', range: '< 7.0', status: 'Normal', date: 'Apr 21' },
  { name: 'Glucose, fasting', value: '118', unit: 'mg/dL', range: '70-99', status: 'High', date: 'Apr 21' },
  { name: 'LDL cholesterol', value: '128', unit: 'mg/dL', range: '< 100', status: 'High', date: 'Apr 21' },
  { name: 'HDL cholesterol', value: '52', unit: 'mg/dL', range: '> 40', status: 'Normal', date: 'Apr 21' },
  { name: 'Creatinine', value: '0.9', unit: 'mg/dL', range: '0.6-1.2', status: 'Normal', date: 'Apr 21' },
  { name: 'TSH', value: '2.4', unit: 'mIU/L', range: '0.4-4.0', status: 'Normal', date: 'Apr 21' },
];

const MEDS_FOR = (id) => [
  { name: 'Lisinopril', dose: '10 mg', freq: 'Once daily', start: 'Jan 2024', refills: 3, status: 'Active', class: 'ACE inhibitor' },
  { name: 'Metformin', dose: '500 mg', freq: 'Twice daily with meals', start: 'Jun 2023', refills: 2, status: 'Active', class: 'Antidiabetic' },
  { name: 'Atorvastatin', dose: '20 mg', freq: 'Once daily, evening', start: 'Mar 2024', refills: 5, status: 'Active', class: 'Statin' },
  { name: 'Aspirin', dose: '81 mg', freq: 'Once daily', start: 'Jan 2024', refills: 11, status: 'Active', class: 'Antiplatelet' },
];

const VITALS_TREND_FOR = (id) => ({
  bp_sys: [136, 134, 132, 138, 135, 130, 128, 132, 130, 128, 126, 128],
  bp_dia: [88, 86, 84, 90, 86, 82, 82, 84, 82, 80, 80, 82],
  weight: [148, 147, 146, 145, 145, 144, 143, 143, 142, 142, 142, 142],
  hr: [78, 76, 74, 80, 76, 72, 72, 74, 72, 70, 70, 72],
});

const NOTES_FOR = (id) => [
  { author: 'Dr. Patel', when: 'Apr 21, 2026', body: 'Patient reports good adherence to current regimen. BP log shows 24-hour averages within target. Reviewed lifestyle modifications and reinforced importance of low-sodium diet. Plan: continue current meds, follow up in 6 weeks with home BP log.' },
  { author: 'RN Cortez', when: 'Apr 21, 2026', body: 'Vitals taken. Patient denies CP, SOB, dizziness. No new concerns reported.' },
  { author: 'Dr. Patel', when: 'Feb 14, 2026', body: 'Telehealth check-in. Discussed metformin tolerance — patient reports occasional mild GI but improving. No need to adjust dose at this time.' },
];

window.MH_DATA = { PATIENTS, TODAY_APPTS, VISITS_FOR, LABS_FOR, MEDS_FOR, VITALS_TREND_FOR, NOTES_FOR };
