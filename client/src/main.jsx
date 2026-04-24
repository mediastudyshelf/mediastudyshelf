import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import App from './App.jsx'
import CoursesPage from './components/CoursesPage.jsx'
import './styles.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/courses" element={<CoursesPage />} />
        <Route path="/course/:courseSlug/:moduleSlug/:classSlug" element={<App />} />
        <Route path="/course/:courseSlug/:moduleSlug" element={<App />} />
        <Route path="/course/:courseSlug" element={<App />} />
        <Route path="/" element={<Navigate to="/courses" replace />} />
        <Route path="*" element={<Navigate to="/courses" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
