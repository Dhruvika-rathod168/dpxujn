import {
  LatestForecastResponse,
  ForecastVintagesResponse,
  AccuracySummaryResponse,
  AccuracyBreakdownResponse,
  ErrorDistributionResponse,
} from '../types';

const BASE_URL = import.meta.env.DEV
  ? (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
  : '';

async function fetchJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    let errorDetail = `HTTP ${resp.status}: ${resp.statusText}`;
    try {
      const errJson = await resp.json();
      if (errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // Keep status text
    }
    throw new Error(errorDetail);
  }
  return resp.json();
}

export const api = {
  getHealth: async () => {
    return fetchJson<{ status: string; dataLoaded: boolean; scope: string }>(`${BASE_URL}/api/health`);
  },

  getLatestForecast: async (deliveryDate: string, cutoff: string = '09:00'): Promise<LatestForecastResponse> => {
    const params = new URLSearchParams({ delivery_date: deliveryDate, cutoff });
    return fetchJson<LatestForecastResponse>(`${BASE_URL}/api/forecast/latest?${params.toString()}`);
  },

  getForecastVintages: async (targetDate: string): Promise<ForecastVintagesResponse> => {
    const params = new URLSearchParams({ target_date: targetDate });
    return fetchJson<ForecastVintagesResponse>(`${BASE_URL}/api/forecast/vintages?${params.toString()}`);
  },

  getAccuracySummary: async (start: string, end: string, cutoff: string = '09:00'): Promise<AccuracySummaryResponse> => {
    const params = new URLSearchParams({ start, end, cutoff });
    return fetchJson<AccuracySummaryResponse>(`${BASE_URL}/api/accuracy/summary?${params.toString()}`);
  },

  getAccuracyBreakdown: async (
    by: 'day' | 'hour' | 'horizon' | 'level',
    start: string,
    end: string,
    cutoff: string = '09:00'
  ): Promise<AccuracyBreakdownResponse> => {
    const params = new URLSearchParams({ by, start, end, cutoff });
    return fetchJson<AccuracyBreakdownResponse>(`${BASE_URL}/api/accuracy/breakdown?${params.toString()}`);
  },

  getErrorDistribution: async (start: string, end: string, cutoff: string = '09:00'): Promise<ErrorDistributionResponse> => {
    const params = new URLSearchParams({ start, end, cutoff });
    return fetchJson<ErrorDistributionResponse>(`${BASE_URL}/api/accuracy/error-distribution?${params.toString()}`);
  },
};
