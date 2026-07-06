import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Layout from "@/components/Layout";
import Landing from "@/pages/Landing";
import Auth from "@/pages/Auth";
import Dashboard from "@/pages/Dashboard";
import Advisor from "@/pages/Advisor";
import BuildGenerator from "@/pages/BuildGenerator";
import Tracker from "@/pages/Tracker";
import ProductDetail from "@/pages/ProductDetail";
import DesktopAgent from "@/pages/DesktopAgent";
import MyPc from "@/pages/MyPc";
import Upgrade from "@/pages/Upgrade";
import Live from "@/pages/Live";
import Profiles from "@/pages/Profiles";
import Games from "@/pages/Games";
import BiosRestore from "@/pages/BiosRestore";
import Commands from "@/pages/Commands";
import Admin from "@/pages/Admin";
import { Loader2 } from "lucide-react";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-[#050505] flex items-center justify-center"><Loader2 className="animate-spin text-[#E5FF00]" size={32} /></div>;
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
  if (loading) return <div className="min-h-screen bg-[#050505] flex items-center justify-center"><Loader2 className="animate-spin text-[#E5FF00]" size={32} /></div>;
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
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Guest><Auth mode="login" /></Guest>} />
            <Route path="/register" element={<Guest><Auth mode="register" /></Guest>} />
            <Route path="/app" element={<Protected><Layout /></Protected>}>
              <Route index element={<Dashboard />} />
              <Route path="advisor" element={<Advisor />} />
              <Route path="builds" element={<BuildGenerator />} />
              <Route path="upgrade" element={<Upgrade />} />
              <Route path="tracker" element={<Tracker />} />
              <Route path="tracker/:id" element={<ProductDetail />} />
              <Route path="pc" element={<MyPc />} />
              <Route path="live" element={<Live />} />
              <Route path="profiles" element={<Profiles />} />
              <Route path="games" element={<Games />} />
              <Route path="bios" element={<BiosRestore />} />
              <Route path="commands" element={<Commands />} />
              <Route path="desktop" element={<DesktopAgent />} />
              <Route path="admin" element={<AdminOnly><Admin /></AdminOnly>} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
