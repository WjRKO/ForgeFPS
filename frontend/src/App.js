import "@/App.css";
import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Loader2 } from "lucide-react";

const Layout = lazy(() => import("@/components/Layout"));
const Landing = lazy(() => import("@/pages/Landing"));
const Auth = lazy(() => import("@/pages/Auth"));
const Security = lazy(() => import("@/pages/Security"));
const PrivacyTelemetry = lazy(() => import("@/pages/PrivacyTelemetry"));
const Changelog = lazy(() => import("@/pages/Changelog"));
const Pricing = lazy(() => import("@/pages/Pricing"));
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const Advisor = lazy(() => import("@/pages/Advisor"));
const BuildGenerator = lazy(() => import("@/pages/BuildGenerator"));
const Tracker = lazy(() => import("@/pages/Tracker"));
const ProductDetail = lazy(() => import("@/pages/ProductDetail"));
const DesktopAgent = lazy(() => import("@/pages/DesktopAgent"));
const MyPcHub = lazy(() => import("@/pages/MyPcHub"));
const Upgrade = lazy(() => import("@/pages/Upgrade"));
const Gaming = lazy(() => import("@/pages/Gaming"));
const Commands = lazy(() => import("@/pages/Commands"));
const Network = lazy(() => import("@/pages/Network"));
const BiosRestore = lazy(() => import("@/pages/BiosRestore"));
const Admin = lazy(() => import("@/pages/Admin"));

const Fallback = () => (
  <div className="min-h-screen bg-[#050505] flex items-center justify-center">
    <Loader2 className="animate-spin text-[#E5FF00]" size={32} />
  </div>
);

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Fallback />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function Guest({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-[#050505]" />;
  if (user) return <Navigate to="/app" replace />;
  return children;
}

function AdminOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Fallback />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/app" replace />;
  return children;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Toaster theme="dark" position="top-right" />
          <Suspense fallback={<Fallback />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/security" element={<Security />} />
              <Route path="/privacy-telemetry" element={<PrivacyTelemetry />} />
              <Route path="/changelog" element={<Changelog />} />
              <Route path="/pricing" element={<Pricing />} />
              <Route path="/login" element={<Guest><Auth mode="login" /></Guest>} />
              <Route path="/register" element={<Guest><Auth mode="register" /></Guest>} />
              <Route path="/app" element={<Protected><Layout /></Protected>}>
                <Route index element={<Dashboard />} />
                <Route path="advisor" element={<Advisor />} />
                <Route path="builds" element={<BuildGenerator />} />
                <Route path="upgrade" element={<Upgrade />} />
                <Route path="tracker" element={<Tracker />} />
                <Route path="tracker/:id" element={<ProductDetail />} />
                <Route path="pc" element={<MyPcHub initialTab="overview" />} />
                <Route path="live" element={<MyPcHub initialTab="live" />} />
                <Route path="network" element={<Network />} />
                <Route path="gaming" element={<Gaming initialTab="games" />} />
                <Route path="profiles" element={<Gaming initialTab="profiles" />} />
                <Route path="games" element={<Gaming initialTab="games" />} />
                <Route path="bios" element={<BiosRestore />} />
                <Route path="commands" element={<Commands />} />
                <Route path="desktop" element={<DesktopAgent />} />
                <Route path="admin" element={<AdminOnly><Admin /></AdminOnly>} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
