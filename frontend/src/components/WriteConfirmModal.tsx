import React from 'react';
import { AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { ObservationInput } from '../api/client';

interface WriteConfirmModalProps {
  isOpen: boolean;
  observationData: ObservationInput | null;
  onConfirm: () => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export const WriteConfirmModal: React.FC<WriteConfirmModalProps> = ({
  isOpen,
  observationData,
  onConfirm,
  onCancel,
  isSubmitting = false,
}) => {
  if (!isOpen || !observationData) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full overflow-hidden border border-gray-100 animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="bg-amber-50 border-b border-amber-200 px-6 py-4 flex items-center space-x-3">
          <div className="p-2 bg-amber-100 rounded-full text-amber-700">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900">Write Authorization Required</h3>
            <p className="text-xs text-amber-800">
              Review and authorize saving this farm observation to the SQLite database.
            </p>
          </div>
        </div>

        {/* Observation Summary Details */}
        <div className="px-6 py-5 space-y-3.5 text-sm">
          <div className="bg-gray-50 p-3.5 rounded-lg border border-gray-200 space-y-2">
            <div className="flex justify-between items-start">
              <span className="text-gray-500 font-medium">Crop:</span>
              <span className="font-semibold text-gray-900 capitalize">{observationData.crop}</span>
            </div>

            {observationData.growth_stage && (
              <div className="flex justify-between items-center">
                <span className="text-gray-500 font-medium">Growth Stage:</span>
                <span className="font-medium text-gray-800 capitalize">{observationData.growth_stage}</span>
              </div>
            )}

            {observationData.location_name && (
              <div className="flex justify-between items-center">
                <span className="text-gray-500 font-medium">Field / Sector:</span>
                <span className="font-medium text-gray-800">{observationData.location_name}</span>
              </div>
            )}

            {observationData.latitude != null && observationData.longitude != null && (
              <div className="flex justify-between items-center">
                <span className="text-gray-500 font-medium">GPS Coordinates:</span>
                <span className="font-mono text-xs text-gray-700">
                  {observationData.latitude.toFixed(4)}°N, {observationData.longitude.toFixed(4)}°E
                </span>
              </div>
            )}

            {observationData.observer_role && (
              <div className="flex justify-between items-center">
                <span className="text-gray-500 font-medium">Observer Role:</span>
                <span className="font-medium text-gray-800 capitalize">{observationData.observer_role}</span>
              </div>
            )}

            <div className="pt-2 border-t border-gray-200">
              <span className="text-gray-500 font-medium block mb-1">Field Notes / Symptoms:</span>
              <p className="text-gray-900 bg-white p-2.5 rounded border border-gray-200 text-xs sm:text-sm whitespace-pre-wrap leading-relaxed">
                {observationData.notes}
              </p>
            </div>
          </div>

          <p className="text-xs text-gray-500 leading-relaxed italic">
            * Write-Safety Policy: Records cannot be saved without your explicit permission. Cancelling will discard this entry without modifying database state.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="bg-gray-50 px-6 py-3.5 border-t border-gray-200 flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-3 space-y-2 space-y-reverse sm:space-y-0">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="w-full sm:w-auto inline-flex justify-center items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50 focus:outline-none"
          >
            <XCircle className="w-4 h-4 mr-1.5 text-gray-500" />
            Cancel (Do Not Save)
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSubmitting}
            className="w-full sm:w-auto inline-flex justify-center items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-lg text-white bg-forest-600 hover:bg-forest-700 focus:outline-none disabled:opacity-50"
          >
            <CheckCircle className="w-4 h-4 mr-1.5 text-emerald-200" />
            {isSubmitting ? 'Saving to Database...' : 'Authorize & Save Record'}
          </button>
        </div>
      </div>
    </div>
  );
};
