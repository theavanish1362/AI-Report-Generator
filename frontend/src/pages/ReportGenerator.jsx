import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import axios from 'axios';
import { FileText, Send, Loader2, BookOpen, Briefcase, X } from 'lucide-react';

const ReportGenerator = () => {
  const [loading, setLoading] = useState(false);
  const [zipInputKey, setZipInputKey] = useState(0);
  const navigate = useNavigate();

  const { register, setValue, handleSubmit, watch, formState: { errors } } = useForm({
    defaultValues: {
      title: '',
      project_type: 'academic',
      description: '',
      pages: 20,
    }
  });

  const projectType = watch('project_type');
  const descriptionLength = watch('description')?.length || 0;
  const pages = watch('pages') || 20;
  const uploadedZip = watch('project_zip');
  const uploadedZipFile = uploadedZip?.[0];

  const clearUploadedZip = () => {
    setValue('project_zip', []);
    setZipInputKey((value) => value + 1);
  };

  const onSubmit = async (data) => {
    const zipFile = data.project_zip?.[0];
    if (zipFile && !zipFile.name.toLowerCase().endsWith('.zip')) {
      toast.error('Please upload a valid .zip file');
      return;
    }
    if (zipFile && zipFile.size > 25 * 1024 * 1024) {
      toast.error('ZIP file must be smaller than 25MB');
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('title', data.title);
      formData.append('project_type', data.project_type);
      formData.append('description', data.description);
      formData.append('pages', String(data.pages));
      if (zipFile) {
        formData.append('project_zip', zipFile);
      }

      const response = await axios.post('/api/generate-report-job', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const jobId = response.data?.job_id;
      if (!jobId) {
        throw new Error('Missing job ID');
      }

      navigate(`/progress/${jobId}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Something went wrong');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white py-10 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-gray-900 mb-3">
            Generate Professional AI Report
          </h1>
          <p className="text-lg text-gray-600">
            Convert your project idea into a polished ~{pages}-page PDF report
          </p>
        </div>

        <div className="bg-white/80 backdrop-blur-xl rounded-2xl shadow-lg border border-blue-100 p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Project Title
              </label>
              <input
                type="text"
                {...register('title', { required: true, minLength: 3 })}
                placeholder="AI-Powered Food Delivery Application"
                className="w-full rounded-xl border border-gray-200 px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
              {errors.title && (
                <p className="text-sm text-red-600 mt-1">
                  Title must be at least 3 characters
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Project Type
              </label>

              <div className="grid grid-cols-2 gap-4">
                {[
                  { type: 'academic', icon: BookOpen, label: 'Academic', desc: 'Research & university projects' },
                  { type: 'industrial', icon: Briefcase, label: 'Industrial', desc: 'Business & startup projects' }
                ].map(({ type, icon, label, desc }) => {
                  const Icon = icon;
                  return (
                    <label
                      key={type}
                      className={`cursor-pointer rounded-xl border p-4 transition ${
                        projectType === type
                          ? 'border-blue-600 bg-blue-50'
                          : 'border-gray-200 bg-white hover:bg-blue-50'
                      }`}
                    >
                      <input
                        type="radio"
                        value={type}
                        {...register('project_type')}
                        className="sr-only"
                      />
                      <div className="flex gap-3">
                        <Icon
                          className={`h-5 w-5 ${
                            projectType === type ? 'text-blue-600' : 'text-gray-400'
                          }`}
                        />
                        <div>
                          <p className="font-medium text-gray-900">{label}</p>
                          <p className="text-sm text-gray-500">{desc}</p>
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Project Code ZIP (optional)
              </label>
              <input
                key={zipInputKey}
                type="file"
                accept=".zip,application/zip"
                {...register('project_zip')}
                className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:text-blue-700 hover:file:bg-blue-100 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
              <p className="mt-1 text-sm text-gray-500">
                Upload your repository archive to generate a code-aware report.
              </p>
              {uploadedZipFile && (
                <div className="mt-1 flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
                  <p className="text-sm text-blue-700 truncate pr-3">
                    Attached: {uploadedZipFile.name} ({(uploadedZipFile.size / (1024 * 1024)).toFixed(2)} MB)
                  </p>
                  <button
                    type="button"
                    onClick={clearUploadedZip}
                    className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-blue-200 bg-white text-blue-700 hover:bg-blue-100 transition"
                    aria-label="Remove uploaded ZIP"
                    title="Remove ZIP"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Project Description
              </label>
              <textarea
                rows="6"
                {...register('description', { required: true, minLength: 50, maxLength: 5000 })}
                className="w-full rounded-xl border border-gray-200 px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="Explain your project, technologies, features, and architecture..."
              />
              <div className="flex justify-between mt-1 text-sm">
                <span className="text-gray-500">Min 50 characters</span>
                <span className={descriptionLength > 4500 ? 'text-orange-600' : 'text-gray-500'}>
                  {descriptionLength}/5000
                </span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Number of Pages (approx.)
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min="18"
                  max="40"
                  step="1"
                  {...register('pages', { valueAsNumber: true, min: 18, max: 40 })}
                  className="w-full"
                />
                <span className="w-16 text-right text-sm font-semibold text-gray-900">
                  {pages}
                </span>
              </div>
              {errors.pages && (
                <p className="text-sm text-red-600 mt-1">
                  Please choose between 18 and 40 pages
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-blue-500 py-3 text-white font-medium shadow hover:opacity-95 transition"
            >
              {loading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Starting generation...
                </>
              ) : (
                <>
                  <Send className="h-5 w-5" />
                  Generate Report
                </>
              )}
            </button>
          </form>

          <div className="mt-10 pt-6 border-t border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              What you’ll get
            </h3>
            <div className="grid md:grid-cols-2 gap-4">
              {[
                `${pages} page professional PDF`,
                'Technical nested subsections',
                'Well-structured chapters',
                'Cover page & table of contents'
              ].map((text, i) => (
                <div key={i} className="flex gap-3">
                  <FileText className="h-5 w-5 text-blue-600 mt-1" />
                  <p className="text-gray-700">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportGenerator;
