// ai-report-generator/frontend/src/components/Navbar.js
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { FileText, History, Github } from 'lucide-react';

const Navbar = () => {
  const location = useLocation();
  const isActive = (path) => location.pathname === path;

  return (
    <nav className="sticky top-0 z-50 backdrop-blur-md bg-gradient-to-r from-blue-50/80 to-white/80 border-b border-blue-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 group">
            <div className="p-2 rounded-xl bg-blue-100 group-hover:bg-blue-200 transition">
              <FileText className="h-6 w-6 text-blue-600" />
            </div>
            <span className="font-semibold text-lg text-gray-900 tracking-tight">
              AI Report Generator
            </span>
          </Link>

          {/* Nav Links */}
          <div className="flex items-center gap-2">

            {/* <Link
              to="/generate"
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                isActive('/generate')
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-700 hover:bg-blue-100'
              }`}
            >
              Generate
            </Link> */}

            <Link
              to="/history"
              className={`flex items-center gap-1 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                isActive('/history')
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-700 hover:bg-blue-100'
              }`}
            >
              <History className="h-4 w-4" />
              History
            </Link>

            {/* GitHub */}
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 p-2 rounded-xl text-gray-500 hover:text-blue-600 hover:bg-blue-100 transition"
            >
              <Github className="h-5 w-5" />
            </a>

          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;