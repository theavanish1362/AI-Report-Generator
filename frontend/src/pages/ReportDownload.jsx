// ai-report-generator/frontend/src/pages/ReportDownload.js
import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import toast from 'react-hot-toast';
import {
  Download,
  FileText,
  ArrowLeft,
  CheckCircle,
  Loader2
} from 'lucide-react';

const ReportDownload = () => {
  const { reportId } = useParams();
  const navigate = useNavigate();
  const [downloading, setDownloading] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const response = await axios.get(
        `/api/download/${reportId}`,
        { responseType: 'blob' }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `report_${reportId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();

      setDownloaded(true);
      toast.success('Report downloaded successfully!');
    } catch {
      toast.error('Failed to download report. Please try again.');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center px-4">
      <div className="max-w-md w-full">

        <div className="bg-white/80 backdrop-blur-xl rounded-2xl border border-blue-100 shadow-lg p-8 text-center">

          {/* Icon */}
          {downloaded ? (
            <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
          ) : downloading ? (
            <Loader2 className="h-16 w-16 text-blue-600 animate-spin mx-auto mb-4" />
          ) : (
            <FileText className="h-16 w-16 text-blue-600 mx-auto mb-4" />
          )}

          {/* Title */}
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            {downloaded
              ? 'Download Complete!'
              : downloading
              ? 'Preparing Your Report'
              : 'Report Ready'}
          </h2>

          {/* Description */}
          <p className="text-gray-600 mb-6">
            {downloaded
              ? 'Your AI-generated report has been downloaded successfully.'
              : downloading
              ? 'Please wait while we prepare your report for download.'
              : 'Your report has been generated and is ready to download.'}
          </p>

          {/* Actions */}
          <div className="space-y-3">
            {!downloaded && (
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-blue-500 py-3 text-white font-medium shadow hover:opacity-95 transition"
              >
                <Download className="h-5 w-5" />
                {downloading ? 'Downloading...' : 'Download Report'}
              </button>
            )}

            <button
              onClick={() => navigate('/generate')}
              className="w-full flex items-center justify-center gap-2 rounded-xl border border-gray-300 py-3 text-gray-700 font-medium hover:bg-gray-50 transition"
            >
              <ArrowLeft className="h-5 w-5" />
              Generate Another Report
            </button>
          </div>

          {/* Report Info */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <p className="text-sm text-gray-500 mb-1">Report ID</p>
            <p className="text-xs font-mono bg-gray-100 px-3 py-2 rounded-lg break-all">
              {reportId}
            </p>
          </div>

        </div>
      </div>
    </div>
  );
};

export default ReportDownload;
