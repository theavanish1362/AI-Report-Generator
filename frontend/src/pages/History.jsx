// ai-report-generator/frontend/src/pages/History.js
import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { FileText, Download, Calendar, Trash2, Clock } from "lucide-react";
import toast from "react-hot-toast";
import axios from "axios";

const History = () => {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const response = await axios.get("/api/history");
      setReports(response.data);
    } catch (error) {
      toast.error("Failed to load reports");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    (async () => {
      await fetchReports();
    })();
  }, []);

  const handleDownload = async (reportId) => {
    try {
      const response = await axios.get(`/api/download/${reportId}`, {
        responseType: "blob",
      });
      
      // Create a URL for the blob
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `report_${reportId}.pdf`); // Force download filename
      
      // Append to the document and trigger click
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      toast.success("Report downloaded successfully!");
    } catch (error) {
      console.error("Download error:", error);
      toast.error("Failed to download report");
    }
  };

  const handleDelete = async (reportId) => {
    try {
      await axios.delete(`/api/report/${reportId}`);
      setReports(reports.filter((r) => r.id !== reportId));
      toast.success("Report deleted successfully");
    } catch (error) {
      toast.error("Failed to delete report");
      console.error(error);
    }
  };

  const formatDate = (dateString) =>
    new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(dateString));

  /* ---------- Loading ---------- */
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-b from-blue-50 to-white">
        <div className="text-center">
          <Clock className="h-12 w-12 text-blue-600 animate-spin mx-auto mb-3" />
          <p className="text-gray-600">Loading your reports...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white py-10 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Report History</h1>
          <Link
            to="/generate"
            className="rounded-xl bg-gradient-to-r from-blue-600 to-blue-500 px-5 py-2.5 text-white font-medium shadow hover:opacity-95 transition"
          >
            Generate New Report
          </Link>
        </div>

        {/* Empty State */}
        {reports.length === 0 ? (
          <div className="bg-white/80 backdrop-blur-xl rounded-2xl border border-blue-100 shadow-lg text-center py-16">
            <FileText className="h-16 w-16 text-blue-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              No Reports Yet
            </h3>
            <p className="text-gray-600 mb-6">
              Generate your first AI report to see it here.
            </p>
            <Link
              to="/generate"
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-white font-medium hover:bg-blue-700 transition"
            >
              <FileText className="h-5 w-5" />
              Generate Report
            </Link>
          </div>
        ) : (
          /* Table */
          <div className="bg-white/80 backdrop-blur-xl rounded-2xl border border-blue-100 shadow-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-blue-50 border-b border-blue-100">
                  <tr>
                    {["Report", "Type", "Pages", "Generated", "Actions"].map(
                      (h) => (
                        <th
                          key={h}
                          className="px-6 py-4 text-left text-sm font-semibold text-gray-900"
                        >
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>

                <tbody className="divide-y divide-gray-200">
                  {reports.map((report) => (
                    <tr
                      key={report.id}
                      className="hover:bg-blue-50/50 transition"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <FileText className="h-5 w-5 text-blue-600" />
                          <span className="font-medium text-gray-900">
                            {report.title}
                          </span>
                        </div>
                      </td>

                      <td className="px-6 py-4">
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-medium ${
                            report.type === "academic"
                              ? "bg-blue-100 text-blue-800"
                              : "bg-purple-100 text-purple-800"
                          }`}
                        >
                          {report.type}
                        </span>
                      </td>

                      <td className="px-6 py-4 text-gray-600">
                        {report.pages} pages
                      </td>

                      <td className="px-6 py-4 text-sm text-gray-600 flex items-center gap-2">
                        <Calendar className="h-4 w-4" />
                        {formatDate(report.date)}
                      </td>

                      <td className="px-6 py-4">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => handleDownload(report.id)}
                            className="p-2 rounded-lg text-gray-600 hover:text-blue-600 hover:bg-blue-100 transition"
                            title="Download"
                          >
                            <Download className="h-5 w-5" />
                          </button>
                          <button
                            onClick={() => handleDelete(report.id)}
                            className="p-2 rounded-lg text-gray-600 hover:text-red-600 hover:bg-red-100 transition"
                            title="Delete"
                          >
                            <Trash2 className="h-5 w-5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default History;
