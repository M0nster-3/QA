import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import LoginPage from './pages/LoginPage';
import QaHomePage from './pages/QaHomePage';
import SessionPage from './pages/SessionPage';
import BenchmarkHomePage from './pages/BenchmarkHomePage';
import BenchmarkSessionPage from './pages/BenchmarkSessionPage';
import NavBar from './components/NavBar';
import ErrorBoundary from './components/ErrorBoundary';
import './App.css';

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading">Loading...</div>;
  if (!user) return <Navigate to="/login" />;
  return (
    <ErrorBoundary>
      <NavBar />
      {children}
    </ErrorBoundary>
  );
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" /> : <LoginPage />} />
      <Route path="/" element={<Protected><QaHomePage /></Protected>} />
      <Route path="/session/:sessionId" element={<Protected><SessionPage /></Protected>} />
      <Route path="/benchmark" element={<Protected><BenchmarkHomePage /></Protected>} />
      <Route path="/benchmark/:sessionId" element={<Protected><BenchmarkSessionPage /></Protected>} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </ErrorBoundary>
    </BrowserRouter>
  );
}
