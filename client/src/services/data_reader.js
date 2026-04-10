/**
 * Data Reader Service
 *
 * Provides a standardized interface for accessing project volumes
 * by taskId, abstracting away file paths and backend specifics.
 */

import axios from 'axios';

// Backend configuration
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:4242/api/pm';

class DataReaderService {
  /**
   * Fetch all pooled volumes (with pagination handled internally if needed)
   * The frontend "pools" the list from the active metadata JSON.
   */
  async getPooledVolumes(params = {}) {
    try {
      const response = await axios.get(`${API_BASE}/volumes`, { params });
      return response.data; // { total, page, items, ... }
    } catch (error) {
      console.error('Error fetching pooled volumes:', error);
      throw error;
    }
  }

  /**
   * Get metadata for a specific volume by taskId
   */
  async getVolumeByTaskId(taskId) {
     try {
       // Since the backend uses id as taskId (e.g. vol_001_em.h5)
       // we can just use the volumes endpoint with filtering if supported,
       // or we could add a dedicated GET /volumes/{id} if needed.
       // For now, we'll assume the frontend already has the list or we fetch one.
       const response = await axios.get(`${API_BASE}/volumes`, { params: { id: taskId, page_size: 1 } });
       return response.data.items[0] || null;
     } catch (error) {
       console.error(`Error fetching volume ${taskId}:`, error);
       throw error;
     }
  }

  /**
   * Update volume status by taskId
   */
  async updateStatus(taskId, status) {
    try {
      const response = await axios.patch(`${API_BASE}/volumes/${taskId}`, { status });
      return response.data;
    } catch (error) {
       console.error(`Error updating volume ${taskId}:`, error);
       throw error;
    }
  }

  /**
   * Bulk link to an external metadata JSON
   */
  async linkExternalMetadata(path) {
    try {
      const response = await axios.post(`${API_BASE}/data/link`, { path });
      return response.data;
    } catch (error) {
      console.error('Error linking external metadata:', error);
      throw error;
    }
  }
}

export const dataReader = new DataReaderService();
export default dataReader;
