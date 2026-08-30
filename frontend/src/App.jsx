import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import ProjectList from './pages/ProjectList';
import ProjectDetail from './pages/ProjectDetail';
import VendorNetwork from './pages/VendorNetwork';
import GeoMap from './pages/GeoMap';
import SurveyDashboard from './pages/SurveyDashboard';
import CitizenSurvey from './pages/CitizenSurvey';

function AppShell() {
  const isPublicSurvey = window.location.pathname.startsWith('/survey/');

  if (isPublicSurvey) {
    return (
      <main className="min-h-screen bg-white text-slate-950">
        <Routes>
          <Route path="/survey/:projectId" element={<CitizenSurvey />} />
        </Routes>
      </main>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-900 text-slate-100 selection:bg-emerald-500 selection:text-white">
      <Navbar />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/projects" element={<ProjectList />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/vendors" element={<VendorNetwork />} />
          <Route path="/map" element={<GeoMap />} />
          <Route path="/geomap" element={<GeoMap />} />
          <Route path="/surveys" element={<SurveyDashboard />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AppShell />
    </Router>
  );
}
