import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { surveysApi } from '../api/apiClient';

function ChoiceButton({ active, children, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`min-h-14 rounded-2xl border px-4 text-lg font-black transition ${
        active ? 'border-blue-600 bg-blue-600 text-white shadow-lg shadow-blue-200' : 'border-slate-200 bg-white text-slate-800'
      }`}
    >
      {children}
    </button>
  );
}

function StarRating({ value, onChange }) {
  return (
    <div className="grid grid-cols-5 gap-2">
      {[1, 2, 3, 4, 5].map((score) => (
        <button
          key={score}
          type="button"
          onClick={() => onChange(score)}
          className={`h-14 rounded-2xl border text-2xl transition ${value >= score ? 'border-amber-400 bg-amber-100' : 'border-slate-200 bg-white'}`}
          aria-label={`${score} stars`}
        >
          ⭐
        </button>
      ))}
    </div>
  );
}

function Question({ number, english, hindi, children }) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-black text-blue-700">Q{number}</p>
      <h2 className="mt-1 text-xl font-black leading-tight text-slate-950">{english}</h2>
      <p className="mt-1 text-base font-semibold leading-snug text-slate-600">{hindi}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function CitizenSurvey() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({
    saw_project: null,
    quality_score: 0,
    satisfaction_score: 0,
    money_spent_properly: '',
    comments: '',
  });

  useEffect(() => {
    const loadProject = async () => {
      try {
        const response = await surveysApi.link(projectId);
        setProject(response.data);
      } catch (err) {
        console.error('Failed to load survey project info', err);
        setProject({ project_id: projectId, work_name: 'MPLAD Project', district: 'your area', state: '', amount: 0 });
      } finally {
        setLoading(false);
      }
    };

    loadProject();
  }, [projectId]);

  const canSubmit = form.saw_project !== null && form.quality_score > 0 && form.satisfaction_score > 0 && form.money_spent_properly;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!canSubmit) return;
    try {
      setSubmitting(true);
      await surveysApi.submitPublic(projectId, form);
      setSubmitted(true);
    } catch (err) {
      console.error('Citizen survey submit failed', err);
      window.alert('Could not submit your response. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <main className="grid min-h-screen place-items-center bg-white px-4 text-slate-900">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      </main>
    );
  }

  if (submitted) {
    return (
      <main className="grid min-h-screen place-items-center bg-white px-4 text-center text-slate-900">
        <section className="w-full max-w-sm rounded-3xl border border-emerald-200 bg-emerald-50 p-7 shadow-sm">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-emerald-600 text-3xl text-white">✓</div>
          <h1 className="mt-5 text-3xl font-black">शुक्रिया! धन्यवाद! 🙏</h1>
          <p className="mt-3 text-lg font-semibold text-slate-700">Your feedback helps fight corruption.</p>
          <p className="mt-4 rounded-2xl bg-white px-4 py-3 font-mono text-sm text-slate-600">Reference: {projectId}</p>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-5 text-slate-950">
      <form onSubmit={handleSubmit} className="mx-auto max-w-xl space-y-5">
        <header className="rounded-3xl bg-white p-5 text-center shadow-sm">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-blue-700 text-xl font-black text-white">MPLAD</div>
          <h1 className="mt-4 text-2xl font-black leading-tight">Your voice matters.</h1>
          <p className="text-xl font-black text-blue-700">आपकी राय मायने रखती है।</p>
          <p className="mt-4 rounded-2xl bg-slate-100 p-4 text-base font-semibold leading-relaxed text-slate-700">
            {project?.work_name || 'MPLAD Project'} in {project?.district || 'your area'}, {project?.state || ''} | ₹{Number(project?.amount || 0).toFixed(2)} Lakhs
          </p>
        </header>

        <Question number="1" english="Did you see or know about this project?" hindi="क्या आपने इस परियोजना को देखा या इसके बारे में जानते हैं?">
          <div className="grid grid-cols-2 gap-3">
            <ChoiceButton active={form.saw_project === true} onClick={() => setForm({ ...form, saw_project: true })}>Yes</ChoiceButton>
            <ChoiceButton active={form.saw_project === false} onClick={() => setForm({ ...form, saw_project: false })}>No</ChoiceButton>
          </div>
        </Question>

        <Question number="2" english="Is the work physically visible and complete?" hindi="क्या काम स्थल पर दिखाई देता है और पूरा है?">
          <StarRating value={form.quality_score} onChange={(quality_score) => setForm({ ...form, quality_score })} />
        </Question>

        <Question number="3" english="Are you satisfied with the quality of work?" hindi="क्या आप काम की गुणवत्ता से संतुष्ट हैं?">
          <StarRating value={form.satisfaction_score} onChange={(satisfaction_score) => setForm({ ...form, satisfaction_score })} />
        </Question>

        <Question number="4" english="Do you think funds were used properly?" hindi="क्या आपको लगता है कि धन का सही उपयोग हुआ?">
          <div className="grid grid-cols-1 gap-3 min-[360px]:grid-cols-3">
            <ChoiceButton active={form.money_spent_properly === 'yes'} onClick={() => setForm({ ...form, money_spent_properly: 'yes' })}>Yes</ChoiceButton>
            <ChoiceButton active={form.money_spent_properly === 'no'} onClick={() => setForm({ ...form, money_spent_properly: 'no' })}>No</ChoiceButton>
            <ChoiceButton active={form.money_spent_properly === 'unsure'} onClick={() => setForm({ ...form, money_spent_properly: 'unsure' })}>Not Sure</ChoiceButton>
          </div>
        </Question>

        <Question number="5" english="Any concerns?" hindi="कोई चिंता या सुझाव?">
          <textarea
            maxLength={200}
            value={form.comments}
            onChange={(event) => setForm({ ...form, comments: event.target.value })}
            placeholder="Hindi or English, optional"
            className="min-h-32 w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 p-4 text-lg font-semibold text-slate-900 outline-none focus:border-blue-600"
          />
          <p className="mt-2 text-right text-sm font-semibold text-slate-500">{form.comments.length}/200</p>
        </Question>

        <button
          type="submit"
          disabled={!canSubmit || submitting}
          className="sticky bottom-4 h-14 w-full rounded-2xl bg-blue-700 text-xl font-black text-white shadow-xl shadow-blue-200 transition hover:bg-blue-600 disabled:bg-slate-300 disabled:text-slate-500"
        >
          {submitting ? 'Submitting...' : 'Submit'}
        </button>
      </form>
    </main>
  );
}
